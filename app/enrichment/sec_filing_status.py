"""Record whether an SEC series still reports, so stale registrations are not
counted as data gaps.

The SEC series/class master lists every registered series, including series the
registrant stopped reporting on (merged, liquidated or simply dropped from later
filings). Those series can never have a current NAV or adviser, so treating them
as missing data overstates every gap in the U.S. universe.

This module reads the official DERA bulk archives already on disk (Form N-CEN
annual census, Form N-PORT quarterly portfolio, Form N-MFP monthly money-market
report) and writes one ``filing_status`` snapshot per fund with the newest report
date seen for its series in each archive. A series counts as reporting when any
of those filings lands inside the observation window; a money-market final filing
flag is kept as explicit termination evidence.

Nothing is inferred beyond archive membership: a fund with no filing is recorded
as "not reported in the window", not asserted terminated.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.session import SessionLocal
from app.models.schema import Fund, FundProfileSnapshot, Source

SOURCE_ID = "sec_filing_status"
DATASET_PAGE = "https://www.sec.gov/data-research/sec-markets-data/form-n-cen-data-sets"
ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/united_states"
NCEN_RAW = RAW / "ncen_bulk"
NPORT_RAW = RAW / "nport_bulk"
NMFP_RAW = RAW / "nmfp_bulk"


def _months_before(value: date, months: int) -> date:
    year, month = value.year, value.month - months
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, min(value.day, 28))


def _rows(path: Path) -> Iterator[dict[str, str]]:
    if not path.exists():
        return iter(())
    with path.open(newline="", encoding="utf-8", errors="replace") as stream:
        yield from csv.DictReader(stream, delimiter="\t")


def _date(value: str | None) -> date | None:
    text = (value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%m/%d/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _archive_dirs(root: Path) -> list[Path]:
    return sorted((p for p in root.glob("*") if p.is_dir()), key=lambda p: p.name)


def _ncen_dates() -> dict[str, date]:
    """series id -> newest N-CEN period-end reported for that series."""
    newest: dict[str, date] = {}
    for directory in _archive_dirs(NCEN_RAW):
        reports: dict[str, date] = {}
        for row in _rows(directory / "SUBMISSION.tsv"):
            accession = (row.get("ACCESSION_NUMBER") or "").strip()
            period = _date(row.get("REPORT_ENDING_PERIOD"))
            if accession and period:
                reports[accession] = period
        for row in _rows(directory / "FUND_REPORTED_INFO.tsv"):
            series = (row.get("SERIES_ID") or "").strip()
            period = reports.get((row.get("ACCESSION_NUMBER") or "").strip())
            if series and period and period > newest.get(series, date.min):
                newest[series] = period
    return newest


def _nport_dates() -> dict[str, date]:
    """series id -> newest N-PORT period-end reported for that series."""
    newest: dict[str, date] = {}
    for directory in _archive_dirs(NPORT_RAW):
        reports: dict[str, date] = {}
        for row in _rows(directory / "SUBMISSION.tsv"):
            accession = (row.get("ACCESSION_NUMBER") or "").strip()
            period = _date(row.get("REPORT_DATE")) or _date(row.get("REPORT_ENDING_PERIOD"))
            if accession and period:
                reports[accession] = period
        for row in _rows(directory / "FUND_REPORTED_INFO.tsv"):
            series = (row.get("SERIES_ID") or "").strip()
            period = reports.get((row.get("ACCESSION_NUMBER") or "").strip())
            if series and period and period > newest.get(series, date.min):
                newest[series] = period
    return newest


def _nmfp_dates() -> tuple[dict[str, date], dict[str, bool]]:
    """series id -> newest N-MFP report date, and series id -> final-filing flag."""
    newest: dict[str, date] = {}
    final: dict[str, bool] = defaultdict(bool)
    for directory in _archive_dirs(NMFP_RAW):
        for row in _rows(directory / "NMFP_SUBMISSION.tsv"):
            series = (row.get("SERIESID") or "").strip()
            report = _date(row.get("REPORTDATE")) or _date(row.get("FILING_DATE"))
            if not series or not report:
                continue
            if report > newest.get(series, date.min):
                newest[series] = report
                final[series] = (row.get("FINALFILINGFLAG") or "").strip().upper() == "Y"
    return newest, final


def _ensure_source(session) -> None:
    source = {"source_id": SOURCE_ID, "country_code": "US",
              "organization": "U.S. Securities and Exchange Commission",
              "source_name": "Form N-CEN / N-PORT / N-MFP reporting-status evidence",
              "endpoint_url": DATASET_PAGE,
              "verification_status": "Usable Fund Data Confirmed",
              "integration_status": "Integrated", "license_status": "Public domain"}
    session.execute(pg_insert(Source).values(**source).on_conflict_do_update(
        index_elements=[Source.source_id],
        set_={key: value for key, value in source.items() if key != "source_id"}))


def sync_sec_filing_status(*, months: int = 12, dry_run: bool = False) -> dict[str, Any]:
    """Write a ``filing_status`` snapshot for every U.S. fund.

    ``months`` is the observation window measured back from the newest report
    date present on disk, not from the wall clock, because the archives lag
    publication.
    """
    ncen = _ncen_dates()
    nport = _nport_dates()
    nmfp, nmfp_final = _nmfp_dates()
    all_dates = [d for d in (*ncen.values(), *nport.values(), *nmfp.values())]
    if not all_dates:
        raise RuntimeError("No SEC bulk archives found; run the N-CEN/N-PORT/N-MFP sync first")
    newest_report = max(all_dates)
    cutoff = _months_before(newest_report, months)

    with SessionLocal() as session:
        funds = session.execute(select(Fund.id, Fund.sec_series_id).where(
            Fund.domicile_country == "US")).all()

    snapshots: list[dict[str, Any]] = []
    reporting = 0
    for fund_id, series in funds:
        series = (series or "").strip()
        ncen_date = ncen.get(series)
        nport_date = nport.get(series)
        nmfp_date = nmfp.get(series)
        latest = max((d for d in (ncen_date, nport_date, nmfp_date) if d), default=None)
        active = bool(latest and latest >= cutoff)
        reporting += int(active)
        payload = {
            "series_id": series or None,
            "reported_in_window": active,
            "window_months": months,
            "window_start": cutoff.isoformat(),
            "newest_archive_report_date": newest_report.isoformat(),
            "latest_report_date": latest.isoformat() if latest else None,
            "ncen_last_report_date": ncen_date.isoformat() if ncen_date else None,
            "nport_last_report_date": nport_date.isoformat() if nport_date else None,
            "nmfp_last_report_date": nmfp_date.isoformat() if nmfp_date else None,
            "money_market_final_filing": bool(nmfp_final.get(series)),
            "basis": "series appears in the SEC DERA N-CEN, N-PORT or N-MFP bulk archives inside the window",
            "note": "absence is not proof of termination; it means no filing was published in the window",
        }
        snapshots.append({
            "fund_id": fund_id, "source_id": SOURCE_ID, "dataset": "filing_status",
            "source_report_date": latest, "snapshot_key": f"{series or fund_id}:filing_status"[:64],
            "payload": payload, "source_url": "https://www.sec.gov/data-research/sec-markets-data/form-n-cen-data-sets",
        })

    result = {
        "source_id": SOURCE_ID, "funds": len(funds), "reported_in_window": reporting,
        "not_reported": len(funds) - reporting, "window_months": months,
        "window_start": cutoff.isoformat(), "newest_archive_report_date": newest_report.isoformat(),
        "ncen_series": len(ncen), "nport_series": len(nport), "nmfp_series": len(nmfp),
        "dry_run": dry_run,
    }
    if dry_run:
        return result

    with SessionLocal() as session:
        _ensure_source(session)
        table = FundProfileSnapshot.__table__
        for offset in range(0, len(snapshots), 500):
            chunk = snapshots[offset:offset + 500]
            statement = pg_insert(table).values(chunk)
            session.execute(statement.on_conflict_do_update(
                constraint="uq_fund_profile_source_snapshot",
                set_={"source_report_date": statement.excluded.source_report_date,
                      "payload": statement.excluded.payload,
                      "source_url": statement.excluded.source_url,
                      "retrieved_at": datetime.now(timezone.utc)}))
        session.commit()
    result["snapshots_written"] = len(snapshots)
    return result
