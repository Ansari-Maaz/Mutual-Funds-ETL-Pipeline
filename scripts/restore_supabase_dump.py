"""Restore the prepared FundFlow dump to a new, empty Supabase database.

The connection URL is requested with hidden input and never logged. Its password is held in a short-lived mode-0600 pgpass file for the Docker client and removed on exit.
PostgreSQL 16's official client image is used because the local pg_restore is
older than this archive format. The script refuses non-Supabase hosts and a
public schema that already has tables; it never drops existing objects.
"""
from __future__ import annotations

import getpass
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.parse import quote, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DUMP = ROOT / "FundFlow_supabase_compatible.dump"
IMAGE = "postgres:16-alpine"


def pgpass_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace(":", "\\:")


def parse_connection_url(value: str) -> tuple[str, int, str, str, str]:
    try:
        parsed = urlsplit(value.strip())
        host = parsed.hostname or ""
        username = unquote(parsed.username or "")
        password = unquote(parsed.password or "")
        database = unquote(parsed.path.lstrip("/"))
        port = parsed.port or 5432
    except ValueError:
        raise ValueError("That connection URL could not be parsed.") from None
    if parsed.scheme not in {"postgres", "postgresql"} or not host or not username or not password or not database:
        raise ValueError("Enter the complete Supabase PostgreSQL connection URL, including its password.")
    if not (host.endswith(".supabase.co") or host.endswith(".supabase.com")):
        raise ValueError("The host must be a Supabase database or Supavisor endpoint.")
    return host, port, username, database, password


def container_base(pgpass_path: Path, host: str, port: int, username: str, database: str) -> list[str]:
    return [
        "docker", "run", "--rm", "--network", "host",
        "--volume", f"{ROOT}:/project:ro",
        "--volume", f"{pgpass_path}:/run/secrets/pgpass:ro",
        "--env", "PGPASSFILE=/run/secrets/pgpass",
        "--env", f"PGHOST={host}",
        "--env", f"PGPORT={port}",
        "--env", f"PGUSER={username}",
        "--env", f"PGDATABASE={database}",
        "--env", "PGSSLMODE=require",
        IMAGE,
    ]


def main() -> int:
    if not DUMP.is_file():
        print(f"Prepared dump not found: {DUMP}", file=sys.stderr)
        return 2
    raw_url = getpass.getpass("Supabase PostgreSQL connection URL (hidden): ")
    try:
        host, port, username, database, password = parse_connection_url(raw_url)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2
    del raw_url

    with tempfile.TemporaryDirectory(prefix="fundflow-supabase-") as temp_dir:
        pgpass_path = Path(temp_dir) / "pgpass"
        pgpass_path.write_text(
            f"{pgpass_escape(host)}:{port}:{pgpass_escape(database)}:"
            f"{pgpass_escape(username)}:{pgpass_escape(password)}\n",
            encoding="utf-8",
        )
        pgpass_path.chmod(0o600)
        del password

        base = container_base(pgpass_path, host, port, username, database)
        preflight = subprocess.run(
            base + ["psql", "--no-psqlrc", "--set", "ON_ERROR_STOP=1", "--tuples-only", "--no-align",
                    "--command", "SELECT count(*) FROM pg_tables WHERE schemaname = 'public';"],
            text=True, capture_output=True,
        )
        if preflight.returncode:
            print("Could not connect to Supabase or inspect the target database.", file=sys.stderr)
            if preflight.stderr:
                print(preflight.stderr.strip(), file=sys.stderr)
            return preflight.returncode
        try:
            public_tables = int(preflight.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            print("Could not determine whether the Supabase public schema is empty.", file=sys.stderr)
            return 2
        if public_tables:
            print(f"Stopped safely: the target public schema already has {public_tables} table(s). No restore was run.", file=sys.stderr)
            return 2

        print(f"Restoring {DUMP.name} ({DUMP.stat().st_size:,} bytes) to the empty Supabase database at {host}:{port}/{database}.")
        restore_url = f"postgresql://{quote(username, safe='')}@{host}:{port}/{quote(database, safe='')}?sslmode=require"
        restore = subprocess.run(
            base + ["pg_restore", "--exit-on-error", "--no-owner", "--no-privileges",
                    f"--dbname={restore_url}", "/project/FundFlow_supabase_compatible.dump"],
            check=False,
        )
        if restore.returncode:
            print(f"Restore stopped with exit code {restore.returncode}; inspect the target before retrying.", file=sys.stderr)
            return restore.returncode

        counts = subprocess.run(
            base + ["psql", "--no-psqlrc", "--set", "ON_ERROR_STOP=1", "--tuples-only", "--no-align",
                    "--field-separator", "|", "--command",
                    "SELECT (SELECT count(*) FROM public.funds),"
                    "(SELECT count(*) FROM public.nav_observations),"
                    "(SELECT count(*) FROM public.portfolio_holdings);"],
            text=True, capture_output=True,
        )
        if counts.returncode:
            print("Restore completed, but post-restore row counts could not be read.", file=sys.stderr)
            if counts.stderr:
                print(counts.stderr.strip(), file=sys.stderr)
            return counts.returncode
        print("Restored rows (funds | NAV observations | portfolio holdings): " + counts.stdout.strip())
        print("The connection URL and password were not saved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
