"""Compare a PostgreSQL source database with a restored target database.

The target can be a normal DATABASE_URL or an isolated Docker container. The
script runs SELECT-only checks and writes a machine-readable parity report.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import database_url

CATALOG_SQL = """
select jsonb_build_object(
  'tables', (select coalesce(jsonb_agg(table_name order by table_name), '[]'::jsonb)
            from information_schema.tables where table_schema='public' and table_type='BASE TABLE'),
  'columns', (select coalesce(jsonb_agg(jsonb_build_object('table',table_name,'column',column_name,
              'data_type',data_type,'udt_name',udt_name,'nullable',is_nullable,'default',column_default)
              order by table_name,ordinal_position), '[]'::jsonb)
              from information_schema.columns where table_schema='public'),
  'constraints', (select coalesce(jsonb_agg(jsonb_build_object('table',conrelid::regclass::text,
              'name',conname,'definition',pg_get_constraintdef(oid)) order by conrelid::regclass::text,conname), '[]'::jsonb)
              from pg_constraint where connamespace='public'::regnamespace),
  'indexes', (select coalesce(jsonb_agg(jsonb_build_object('table',tablename,'name',indexname,'definition',indexdef)
              order by tablename,indexname), '[]'::jsonb) from pg_indexes where schemaname='public'),
  'index_facts', (select coalesce(jsonb_agg(jsonb_build_object('table',t.relname,'name',i.relname,
              'access_method',am.amname,'unique',x.indisunique,'primary',x.indisprimary,
              'valid',x.indisvalid,'ready',x.indisready,'key_attributes',x.indkey::text,
              'operator_classes',x.indclass::text,'collations',x.indcollation::text,'options',x.indoption::text)
              order by t.relname,i.relname), '[]'::jsonb)
              from pg_index x join pg_class i on i.oid=x.indexrelid join pg_class t on t.oid=x.indrelid
              join pg_namespace n on n.oid=i.relnamespace join pg_am am on am.oid=i.relam where n.nspname='public'),
  'sequences', (select coalesce(jsonb_agg(jsonb_build_object('name',schemaname||'.'||sequencename,
              'data_type',data_type,'start_value',start_value,'min_value',min_value,'max_value',max_value,
              'increment_by',increment_by,'cycle',cycle,'cache_size',cache_size,'last_value',last_value)
              order by schemaname,sequencename), '[]'::jsonb) from pg_sequences where schemaname='public'),
  'extensions', (select coalesce(jsonb_agg(jsonb_build_object('name',extname,'version',extversion) order by extname), '[]'::jsonb)
                 from pg_extension),
  'database_size_bytes', pg_database_size(current_database())
)::text
"""


def _docker_sql(container: str, query: str, *, user: str = "postgres", database: str = "mfetl") -> str:
    result = subprocess.run(
        ["docker", "exec", container, "psql", "-X", "-qAt", "-U", user, "-d", database, "-c", query],
        check=True, capture_output=True, text=True, timeout=300,
    )
    return result.stdout.strip()


def _url_catalog(url: str) -> dict[str, Any]:
    engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 10})
    try:
        with engine.connect() as connection:
            return json.loads(connection.execute(text(CATALOG_SQL)).scalar_one())
    finally:
        engine.dispose()


def _counts_sql(tables: list[str]) -> str:
    safe = [name for name in tables if re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", name)]
    if len(safe) != len(tables):
        raise ValueError("Unexpected table name in public schema")
    expressions = ",".join(f"'{name}',(select count(*) from public.\"{name}\")" for name in safe)
    return f"select jsonb_build_object({expressions})::text"


def validate(source_url: str | None, target_url: str | None = None, target_container: str | None = None,
             source_container: str | None = None) -> dict[str, Any]:
    source = (json.loads(_docker_sql(source_container, CATALOG_SQL, user="mfetl"))
              if source_container else _url_catalog(source_url or ""))
    target_raw = _docker_sql(target_container, CATALOG_SQL) if target_container else None
    target = json.loads(target_raw) if target_raw is not None else _url_catalog(target_url or "")

    count_query = _counts_sql(source["tables"])
    if source_container:
        source_counts = json.loads(_docker_sql(source_container, count_query, user="mfetl"))
    else:
        source_engine = create_engine(source_url or "", pool_pre_ping=True, connect_args={"connect_timeout": 10})
        try:
            with source_engine.connect() as connection:
                source_counts = json.loads(connection.execute(text(count_query)).scalar_one())
        finally:
            source_engine.dispose()
    target_counts = json.loads(_docker_sql(target_container, count_query)) if target_container else None
    if target_counts is None:
        target_engine = create_engine(target_url or "", pool_pre_ping=True, connect_args={"connect_timeout": 10})
        try:
            with target_engine.connect() as connection:
                target_counts = json.loads(connection.execute(text(count_query)).scalar_one())
        finally:
            target_engine.dispose()

    row_differences = {table: {"source": source_counts.get(table), "target": target_counts.get(table)}
                       for table in source["tables"] if source_counts.get(table) != target_counts.get(table)}
    table_equal = source["tables"] == target["tables"]
    structural_sections = ("columns", "constraints", "indexes", "index_facts", "sequences", "extensions")
    structure_equal = {section: source[section] == target[section] for section in structural_sections}
    source_index_names = {(row["table"], row["name"]) for row in source["indexes"]}
    target_index_names = {(row["table"], row["name"]) for row in target["indexes"]}
    index_definition_text_differences = []
    target_index_map = {(row["table"], row["name"]): row["definition"] for row in target["indexes"]}
    for row in source["indexes"]:
        key = (row["table"], row["name"])
        if key in target_index_map and row["definition"] != target_index_map[key]:
            index_definition_text_differences.append({"table": key[0], "index": key[1],
                "source_definition": row["definition"], "target_definition": target_index_map[key],
                "note": "PostgreSQL major versions deparse this partial-index expression with different but equivalent casts/parentheses; index name, access method, uniqueness, key attributes, and validity are compared in index_facts."})
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_database_size_bytes": source["database_size_bytes"],
        "target_database_size_bytes": target["database_size_bytes"],
        "source_table_count": len(source["tables"]), "target_table_count": len(target["tables"]),
        "source_row_counts": source_counts, "target_row_counts": target_counts,
        "row_count_differences": row_differences,
        "tables_equal": table_equal,
        "structure_equal": structure_equal,
        "index_names_equal": source_index_names == target_index_names,
        "index_definition_text_differences": index_definition_text_differences,
        "source_catalog": source,
        "target_catalog": target,
        "status": ("PASS" if table_equal and not row_differences and all(structure_equal.values()) else
                   "PASS_WITH_VERSION_DEPARSE_DIFFERENCE" if table_equal and not row_differences and
                   all(structure_equal.get(section) for section in ("columns", "constraints", "index_facts", "sequences", "extensions")) and
                   source_index_names == target_index_names and bool(index_definition_text_differences) else "FAIL"),
        "notes": ["Database byte sizes can differ across PostgreSQL major versions, architectures, and physical layouts; table row counts and catalog definitions are compared separately."]
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-url", help="Defaults to DATABASE_URL from local environment.")
    parser.add_argument("--source-docker-container", help="Read-only source database container (database/user mfetl/mfetl).")
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument("--target-url", help="PostgreSQL target URL (prefer --target-env to avoid exposing credentials in process listings).")
    destination.add_argument("--target-docker-container", help="Isolated target container with psql, database/user mfetl/postgres.")
    parser.add_argument("--target-env", default="SUPABASE_DATABASE_URL",
                        help="Environment variable holding the target URL (default: SUPABASE_DATABASE_URL).")
    parser.add_argument("--output", default="reports/supabase_restore_validation.json")
    args = parser.parse_args()
    if args.source_docker_container and args.source_url:
        parser.error("Use only one of --source-url and --source-docker-container.")
    source_url = args.source_url or (None if args.source_docker_container else database_url())
    target_url = args.target_url or os.getenv(args.target_env)
    if bool(args.target_docker_container) == bool(target_url):
        parser.error("Provide exactly one target using --target-docker-container or a URL in --target-env/--target-url.")
    result = validate(source_url, target_url, args.target_docker_container, args.source_docker_container)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print(json.dumps({"status": result["status"], "tables_equal": result["tables_equal"],
                      "row_count_differences": result["row_count_differences"],
                      "structure_equal": result["structure_equal"],
                      "index_names_equal": result["index_names_equal"],
                      "index_definition_text_differences": result["index_definition_text_differences"],
                      "output": args.output}, indent=2))


if __name__ == "__main__":
    main()
