"""Backfill US fund-series LEIs from cached SEC Form N-CEN bulk archives.

Form N-CEN Item B publishes a Legal Entity Identifier for the reporting series.
This read-only-on-the-network script reuses the bulk importer's parsers, keeps
the newest filing per series across the cached quarters, and writes the identifier
plus an auditable `identity` profile snapshot. Existing identifiers are never
changed. The normal `sync-sec-ncen-bulk` command performs the same import on
every scheduled run.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert as pg_insert

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal
from app.enrichment.sec_ncen_bulk import (
    SOURCE_ID, RAW, _archive_rows, _clean, _ensure_source,
    _local_series, _source_url, _submissions,
)
from app.models.schema import FundIdentifier, FundProfileSnapshot

DATASETS = sorted(path for path in RAW.glob("*_ncen*") if path.is_dir())


def run() -> dict:
    local = _local_series()
    chosen: dict[str, tuple[object, str, str, str, str]] = {}
    for extract_dir in DATASETS:
        submissions = _submissions(extract_dir)
        for row in _archive_rows(extract_dir, set(local)):
            accession = _clean(row.get("ACCESSION_NUMBER")) or ""
            series_id = _clean(row.get("SERIES_ID")) or ""
            lei = _clean(row.get("LEI"))
            submission = submissions.get(accession)
            if not (series_id and lei and submission and submission["report_date"]):
                continue
            current = chosen.get(series_id)
            if current is None or submission["report_date"] > current[0]:
                chosen[series_id] = (
                    submission["report_date"], lei, accession,
                    submission["cik"], extract_dir.name,
                )

    identifiers: dict[tuple[int, str], dict] = {}
    snapshots: dict[tuple[int, str], dict] = {}
    for series_id, (report_date, lei, accession, cik, archive) in chosen.items():
        source_url = _source_url(cik, accession)
        for fund_id in local[series_id]:
            key = (fund_id, lei)
            identifiers[key] = {
                "fund_id": fund_id, "id_type": "LEI", "value": lei,
                "source_id": SOURCE_ID,
                "attributes": {
                    "scope": "SEC series-level LEI; shared by all share classes of the series",
                    "series_id": series_id, "accession_number": accession,
                    "archive": archive,
                },
                "source_url": source_url,
            }
            snapshot_key = f"sec-ncen-lei:{series_id}:{lei}"
            snapshots[(fund_id, snapshot_key)] = {
                "fund_id": fund_id, "source_id": SOURCE_ID, "dataset": "identity",
                "source_report_date": report_date, "snapshot_key": snapshot_key,
                "payload": {
                    "lei": lei, "identifier_type": "LEI",
                    "scope": "SEC series-level Legal Entity Identifier filed in Form N-CEN Item B",
                    "series_id": series_id, "accession_number": accession,
                    "archive": archive, "source_url": source_url,
                },
                "source_url": source_url, "retrieved_at": datetime.now().astimezone(),
            }

    with SessionLocal() as session:
        _ensure_source(session)
        identifier_rows = list(identifiers.values())
        for offset in range(0, len(identifier_rows), 400):
            chunk = identifier_rows[offset:offset + 400]
            statement = pg_insert(FundIdentifier.__table__).values(chunk)
            session.execute(statement.on_conflict_do_nothing(
                constraint="uq_fund_identifier"))
        snapshot_rows = list(snapshots.values())
        for offset in range(0, len(snapshot_rows), 400):
            chunk = snapshot_rows[offset:offset + 400]
            statement = pg_insert(FundProfileSnapshot.__table__).values(chunk)
            session.execute(statement.on_conflict_do_update(
                constraint="uq_fund_profile_source_snapshot",
                set_={"payload": statement.excluded.payload,
                      "source_report_date": statement.excluded.source_report_date,
                      "source_url": statement.excluded.source_url,
                      "retrieved_at": statement.excluded.retrieved_at}))
        session.commit()
    result = {
        "source_id": SOURCE_ID, "archives": [path.name for path in DATASETS],
        "series_with_lei": len(chosen), "identifiers_written": len(identifiers),
        "snapshots_written": len(snapshots),
    }
    (ROOT / "reports" / "sec_ncen_series_lei.json").write_text(
        json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
