"""Import SEC series/class master fields as source-linked fund profile snapshots."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.connectors.sec import RAW, URL, _fund_record_from_row
from app.db.session import SessionLocal
from app.models.schema import Fund, FundProfileSnapshot, Source

SOURCE_ID = "sec_open_end_fund_classes"


def _snapshot_key(payload: dict[str, Any]) -> str:
    identity = json.dumps([SOURCE_ID, "summary", None, payload], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def sync_sec_class_profiles(fund_ids: set[int] | None = None, *, dry_run: bool = False) -> dict[str, Any]:
    """Import locally cached SEC class rows by exact SEC class ID.

    No fund core fields are overwritten. The source file is refreshed by the
    regular SEC connector; this command uses the existing local snapshot only.
    """
    source_file: Path = RAW / "sec_series_classes.csv"
    if not source_file.exists():
        raise FileNotFoundError(f"SEC series/class snapshot is missing: {source_file}; run the SEC fund ETL first")

    profiles: dict[str, dict[str, Any]] = {}
    with source_file.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"Entity Org Type", "Series ID", "Series Name", "Class ID", "Class Name"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"Unexpected SEC class master columns: {reader.fieldnames}")
        for row in reader:
            record = _fund_record_from_row(row)
            if record:
                profiles[record["source_fund_id"]] = record["profile_data"]["summary"]

    source = {
        "source_id": SOURCE_ID, "country_code": "US",
        "organization": "U.S. Securities and Exchange Commission",
        "source_name": "Investment Company Series and Class Information",
        "endpoint_url": URL, "verification_status": "Usable Fund Data Confirmed",
        "integration_status": "Integrated", "license_status": "Unknown",
    }
    inserted = matched = 0
    skipped = Counter()
    with SessionLocal() as session:
        query = select(Fund.id, Fund.source_fund_id).where(
            Fund.source_id == SOURCE_ID, Fund.domicile_country == "US")
        if fund_ids:
            query = query.where(Fund.id.in_(fund_ids))
        funds = session.execute(query).all()
        values = []
        now_source = insert(Source).values(**source).on_conflict_do_update(
            index_elements=[Source.source_id],
            set_={key: value for key, value in source.items() if key != "source_id"},
        )
        if not dry_run:
            session.execute(now_source)
        for fund_id, class_id in funds:
            payload = profiles.get(class_id)
            if not payload:
                skipped["no_exact_SEC_class_match"] += 1
                continue
            matched += 1
            values.append({
                "fund_id": fund_id, "source_id": SOURCE_ID, "dataset": "summary",
                "source_report_date": None, "snapshot_key": _snapshot_key(payload),
                "payload": payload, "source_url": URL,
            })
        if not dry_run:
            table = FundProfileSnapshot.__table__
            for offset in range(0, len(values), 1000):
                statement = insert(table).values(values[offset:offset + 1000])
                result = session.execute(statement.on_conflict_do_nothing(
                    constraint="uq_fund_profile_source_snapshot").returning(table.c.id))
                inserted += len(result.scalars().all())
            session.commit()
    return {
        "funds_examined": len(funds), "exact_SEC_class_matches": matched,
        "snapshots_inserted": inserted,
        "already_present_or_unchanged": matched - inserted if not dry_run else None,
        "skipped": dict(skipped), "source_url": URL, "dry_run": dry_run,
    }
