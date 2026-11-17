"""Load official SEC Form N-PORT bulk data sets for US fund series.

The quarterly SEC DERA N-PORT data set contains every N-PORT-P filing whose
acceptance date falls in the quarter, including registrants whose individual
EDGAR submissions endpoint was unavailable during a per-CIK sweep. This module
imports filed positions, reported net assets, and reported security identifiers
without inventing values. Holdings are stored per local share class because
FundFlow's holdings API is class-oriented; N-PORT reports them at series scope.

Implementation notes
--------------------
* The holding file is roughly 1 GB. It is streamed into a temporary PostgreSQL
  staging table with ``COPY`` instead of being loaded into Python memory.
* The bulk file is not ordered by accession, so the staging table keeps an
  insertion sequence and ``row_number()`` restores a stable per-filing order.
* DERA stores ``PERCENTAGE`` as a percentage of net assets, matching FundFlow's
  ``portfolio_weight`` convention, so the value is stored as filed without
  rescaling.
* A holding can have more than one identifier row (for example an ISIN row and a
  separate ticker row), so identifiers are aggregated per ``HOLDING_ID`` before
  joining; a plain join would duplicate every affected position.
* Existing EDGAR-sourced rows for the same fund/report date are replaced by the
  bulk import for idempotency, then new rows are inserted in one set-based
  statement.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import urllib.request
import zipfile
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterator

import psycopg

from app.config import database_url, timeout_seconds, user_agent
from app.db.session import SessionLocal
from app.models.schema import Fund, Source
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

import logging

_LOG = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "united_states" / "nport_bulk"
REPORTS = ROOT / "reports"
BASE_URL = "https://www.sec.gov/files/dera/data/form-n-port-data-sets/{quarter}_nport.zip"
DATASET_PAGE = "https://www.sec.gov/data-research/sec-markets-data/form-n-port-data-sets"
REQUIRED_FILES = (
    "SUBMISSION.tsv",
    "REGISTRANT.tsv",
    "FUND_REPORTED_INFO.tsv",
    "FUND_REPORTED_HOLDING.tsv",
    "IDENTIFIERS.tsv",
)
MONTHS = {name: index for index, name in enumerate(
    ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"), 1)}

# N-PORT Item C.4 asset categories (ASSET_CAT in the DERA holding file). The
# category is filed by the fund for every position, so summing the reported
# percentage of net assets per category yields a source-backed allocation.
ASSET_CATEGORY_LABELS = {
    "EC": "Common equity",
    "EP": "Preferred equity",
    "DBT": "Debt",
    "ABS-MBS": "Mortgage-backed securities",
    "ABS-O": "Asset-backed securities",
    "ABS-CBDO": "Collateralized debt obligations",
    "ABS-APCP": "Asset-backed commercial paper",
    "LON": "Loans",
    "SN": "Structured notes",
    "STIV": "Short-term investments",
    "RA": "Repurchase agreements",
    "RE": "Real estate",
    "COMM": "Commodities",
    "DE": "Derivatives (other)",
    "DFE": "Derivatives (foreign exchange)",
    "DIR": "Derivatives (interest rate)",
    "DCR": "Derivatives (commodity)",
    "DCO": "Derivatives (credit)",
    "DO": "Derivatives (other)",
    "OTHER": "Other",
}


def _asset_label_sql() -> str:
    """Build the CASE expression that maps filed asset categories to labels."""
    branches = " ".join(
        f"WHEN '{code}' THEN '{label}'" for code, label in ASSET_CATEGORY_LABELS.items())
    return f"CASE c.code {branches} ELSE c.code END"


def _decimal(value: str | None) -> Decimal | None:
    if not value or not value.strip():
        return None
    try:
        return Decimal(value.strip())
    except InvalidOperation:
        _LOG.warning("Ignoring malformed numeric value %r", value[:40])
        return None


def _int(value: str | None) -> int | None:
    try:
        return int(value) if value is not None and value.strip() else None
    except ValueError:
        return None


def _parse_sec_date(value: str | None) -> date | None:
    """Parse the bulk set's DD-MON-YYYY dates without locale dependence."""
    if not value or not value.strip():
        return None
    token = value.strip().upper()
    parts = token.split("-")
    if len(parts) == 3 and parts[1] in MONTHS and parts[0].isdigit() and parts[2].isdigit():
        return date(int(parts[2]), MONTHS[parts[1]], int(parts[0]))
    for fmt in ("%Y-%m-%d", "%d-%b-%Y"):
        try:
            return datetime.strptime(token, fmt).date()
        except ValueError:
            continue
    return None


def _min_replacement_ratio() -> float:
    """Minimum inserted/replaced row ratio tolerated before a re-import is rolled back."""
    try:
        return float(os.getenv("NPORT_MIN_REPLACEMENT_RATIO", "0.5"))
    except ValueError:
        return 0.5


def latest_quarter(today: date | None = None) -> str:
    """Return the newest data set safely expected to be published.

    SEC publishes each quarter's N-PORT data set roughly three to four weeks
    after quarter end. A 45-day lag avoids requesting a 404 at a quarter edge.
    """
    today = today or date.today()
    shifted = date.fromordinal(today.toordinal() - 45)
    year, quarter = shifted.year, (shifted.month - 1) // 3 + 1
    # The 45-day shift can land inside the quarter that has not finished yet
    # (for example, mid-November shifts to October, which is in Q4 even though
    # Q4 data cannot exist). Step back until the selected quarter has ended.
    quarter_end_month = quarter * 3
    while (year, quarter_end_month) >= (today.year, today.month):
        quarter -= 1
        if quarter == 0:
            year, quarter = year - 1, 4
        quarter_end_month = quarter * 3
    return f"{year}q{quarter}"


def download_dataset(quarter: str, *, refresh: bool = False) -> dict[str, Any]:
    RAW.mkdir(parents=True, exist_ok=True)
    archive = RAW / f"{quarter}_nport.zip"
    target_dir = RAW / quarter
    url = BASE_URL.format(quarter=quarter)
    downloaded = refresh or not archive.exists()
    if downloaded:
        request = urllib.request.Request(
            url, headers={"User-Agent": user_agent(), "Accept": "application/zip,*/*"})
        # Stream to a temporary file and rename atomically so an interrupted
        # download can never leave a truncated archive that is later trusted.
        partial = archive.with_suffix(archive.suffix + ".part")
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds()) as response, partial.open("wb") as out:
                shutil.copyfileobj(response, out, length=1024 * 1024)
            if not zipfile.is_zipfile(partial):
                raise ValueError(f"SEC data set {quarter} download is not a valid zip archive")
            os.replace(partial, archive)
        finally:
            partial.unlink(missing_ok=True)
    if not archive.exists():
        raise FileNotFoundError(f"SEC N-PORT data set archive is missing: {archive}")
    target_dir.mkdir(parents=True, exist_ok=True)
    missing = [name for name in REQUIRED_FILES if not (target_dir / name).exists()]
    if missing:
        with zipfile.ZipFile(archive) as bundle:
            for name in missing:
                if name not in bundle.namelist():
                    raise ValueError(f"SEC data set {quarter} does not contain {name}")
                with bundle.open(name) as source, (target_dir / name).open("wb") as destination:
                    shutil.copyfileobj(source, destination, length=1024 * 1024)
    hasher = hashlib.sha256()
    with archive.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    digest = hasher.hexdigest()
    manifest = {
        "source_id": "sec_nport_bulk", "dataset": quarter, "url": url,
        "archive": str(archive.relative_to(ROOT)), "directory": str(target_dir.relative_to(ROOT)),
        "bytes": archive.stat().st_size, "sha256": digest, "downloaded": downloaded,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "sec_nport_bulk_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def _rows(path: Path) -> Iterator[dict[str, str]]:
    with path.open("r", encoding="utf-8", errors="replace", newline="") as stream:
        yield from csv.DictReader(stream, delimiter="\t")


def _submissions(quarter_dir: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in _rows(quarter_dir / "SUBMISSION.tsv"):
        accession = (row.get("ACCESSION_NUMBER") or "").strip()
        report_date = _parse_sec_date(row.get("REPORT_DATE"))
        if not accession or report_date is None:
            continue
        result[accession] = {
            "accession": accession, "report_date": report_date,
            "filing_date": _parse_sec_date(row.get("FILING_DATE")),
            "is_last_filing": (row.get("IS_LAST_FILING") or "").strip().upper(),
        }
    return result


def _reported_funds(quarter_dir: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in _rows(quarter_dir / "FUND_REPORTED_INFO.tsv"):
        accession = (row.get("ACCESSION_NUMBER") or "").strip()
        series_id = (row.get("SERIES_ID") or "").strip()
        if not accession or not series_id:
            continue
        result[accession] = {
            "series_id": series_id,
            "series_name": (row.get("SERIES_NAME") or "").strip() or None,
            "net_assets": _decimal(row.get("NET_ASSETS")),
        }
    return result


def _registrants(quarter_dir: Path) -> dict[str, dict[str, str | None]]:
    result: dict[str, dict[str, str | None]] = {}
    for row in _rows(quarter_dir / "REGISTRANT.tsv"):
        accession = (row.get("ACCESSION_NUMBER") or "").strip()
        if not accession:
            continue
        cik_raw = "".join(ch for ch in (row.get("CIK") or "") if ch.isdigit())
        result[accession] = {
            "cik": cik_raw.zfill(10) if cik_raw else None,
            "registrant_name": (row.get("REGISTRANT_NAME") or "").strip() or None,
        }
    return result


def _local_series(only_missing: bool) -> dict[str, list[int]]:
    with SessionLocal() as session:
        rows = session.execute(select(Fund.id, Fund.sec_series_id).where(
            Fund.domicile_country == "US", Fund.sec_series_id.is_not(None))).all()
        result: dict[str, list[int]] = defaultdict(list)
        for fund_id, series_id in rows:
            result[series_id].append(fund_id)
        if only_missing:
            covered = set(session.execute(text(
                "SELECT DISTINCT fund_id FROM portfolio_holdings")).scalars().all())
            result = {
                series_id: [fund_id for fund_id in ids if fund_id not in covered]
                for series_id, ids in result.items()
                if any(fund_id not in covered for fund_id in ids)
            }
    return result


def _target_accessions(
    submissions: dict[str, dict[str, Any]],
    reported: dict[str, dict[str, Any]],
    local_series: dict[str, list[int]],
) -> dict[str, dict[str, Any]]:
    """Keep one latest filing per local series/report period."""
    chosen: dict[tuple[str, date], dict[str, Any]] = {}
    for accession, info in reported.items():
        series_id = info["series_id"]
        if series_id not in local_series or accession not in submissions:
            continue
        submission = submissions[accession]
        key = (series_id, submission["report_date"])
        order = (submission.get("filing_date") or date.min,
                 submission["is_last_filing"] == "Y", accession)
        current = chosen.get(key)
        if current is None or order > current["order"]:
            chosen[key] = {**submission, **info, "order": order, "series_id": series_id}
    return {item["accession"]: item for item in chosen.values()}


def _copy_holdings(
    cursor: psycopg.Cursor, quarter_dir: Path, targets: dict[str, dict[str, Any]]
) -> int:
    """Stream matching positions into a staging table preserving file order."""
    count = 0
    with cursor.copy(
        "COPY stg_bulk_holdings (accession, holding_id, issuer_name, cusip, balance, "
        "currency_code, currency_value, percentage, asset_cat) FROM STDIN"
    ) as copy:
        for row in _rows(quarter_dir / "FUND_REPORTED_HOLDING.tsv"):
            accession = (row.get("ACCESSION_NUMBER") or "").strip()
            if accession not in targets:
                continue
            copy.write_row((
                accession,
                _int(row.get("HOLDING_ID")),
                (row.get("ISSUER_NAME") or row.get("ISSUER_TITLE") or "").strip() or None,
                (row.get("ISSUER_CUSIP") or "").strip()[:12] or None,
                _decimal(row.get("BALANCE")),
                (row.get("CURRENCY_CODE") or "").strip() or None,
                _decimal(row.get("CURRENCY_VALUE")),
                _decimal(row.get("PERCENTAGE")),
                (row.get("ASSET_CAT") or "").strip().upper() or None,
            ))
            count += 1
    return count


def _copy_identifiers(cursor: psycopg.Cursor, quarter_dir: Path) -> int:
    """Stream reported security identifiers for later joining by holding ID."""
    count = 0
    with cursor.copy(
        "COPY stg_bulk_identifiers (holding_id, isin, ticker) FROM STDIN"
    ) as copy:
        for row in _rows(quarter_dir / "IDENTIFIERS.tsv"):
            isin = (row.get("IDENTIFIER_ISIN") or "").strip() or None
            ticker = (row.get("IDENTIFIER_TICKER") or "").strip() or None
            if not isin and not ticker:
                continue
            holding_id = _int(row.get("HOLDING_ID"))
            if holding_id is None:
                continue
            copy.write_row((holding_id, isin[:12] if isin else None,
                            ticker[:50] if ticker else None))
            count += 1
    return count


def import_nport_bulk(
    quarter: str | None = None,
    *,
    only_missing: bool = False,
    refresh: bool = False,
    include_identifiers: bool = True,
    limit_filings: int | None = None,
) -> dict[str, Any]:
    """Import one SEC N-PORT quarterly data set into PostgreSQL.

    ``only_missing`` limits work to local funds that currently have no stored
    holdings. The operation is idempotent: rows for the same fund/report date
    are replaced by this official filing.
    """
    quarter = quarter or latest_quarter()
    manifest = download_dataset(quarter, refresh=refresh)
    quarter_dir = RAW / quarter
    submissions = _submissions(quarter_dir)
    reported = _reported_funds(quarter_dir)
    registrants = _registrants(quarter_dir)
    local_series = _local_series(only_missing)
    targets = _target_accessions(submissions, reported, local_series)
    if limit_filings is not None:
        targets = dict(list(targets.items())[:max(0, limit_filings)])
    if not targets:
        return {"dataset": quarter, "filings_imported": 0, "note": "No local series matched the data set"}

    # Register the source before writing snapshots so the foreign key on
    # fund_profile_snapshots.source_id is satisfiable on a fresh database.
    with SessionLocal() as session:
        source = {
            "source_id": "sec_nport_bulk", "country_code": "US",
            "organization": "U.S. Securities and Exchange Commission",
            "source_name": "Form N-PORT structured data sets",
            "endpoint_url": DATASET_PAGE,
            "verification_status": "Usable Fund Data Confirmed",
            "integration_status": "Integrated",
            "license_status": "Unknown",
        }
        statement = pg_insert(Source).values(**source)
        session.execute(statement.on_conflict_do_update(
            index_elements=[Source.source_id],
            set_={key: value for key, value in source.items() if key != "source_id"}))
        session.commit()

    raw_url = database_url().replace("postgresql+psycopg://", "postgresql://", 1)
    counts: dict[str, int] = {}
    with psycopg.connect(raw_url, autocommit=False) as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TEMP TABLE stg_bulk_holdings (
                    seq bigserial PRIMARY KEY,
                    accession text NOT NULL,
                    holding_id bigint,
                    issuer_name text,
                    cusip text,
                    balance numeric,
                    currency_code text,
                    currency_value numeric,
                    percentage numeric,
                    asset_cat text
                ) ON COMMIT DROP;
                CREATE TEMP TABLE stg_bulk_identifiers (
                    holding_id bigint,
                    isin text,
                    ticker text
                ) ON COMMIT DROP;
                CREATE TEMP TABLE stg_bulk_accessions (
                    accession text PRIMARY KEY,
                    series_id text NOT NULL,
                    report_date date NOT NULL,
                    cik text,
                    net_assets numeric,
                    source_url text NOT NULL
                ) ON COMMIT DROP;
            """)
            counts["holding_rows_read"] = _copy_holdings(cursor, quarter_dir, targets)
            if include_identifiers:
                counts["identifier_rows_read"] = _copy_identifiers(cursor, quarter_dir)
            accessions = []
            for accession, target in targets.items():
                cik = (registrants.get(accession) or {}).get("cik")
                source_url = (
                    f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{accession}.txt"
                    if cik else
                    f"https://www.sec.gov/Archives/edgar/data/{accession.replace('-', '')}/{accession}.txt"
                )
                accessions.append((accession, target["series_id"], target["report_date"],
                                   cik, target.get("net_assets"), source_url))
            with cursor.copy(
                "COPY stg_bulk_accessions (accession, series_id, report_date, cik, net_assets, source_url) FROM STDIN"
            ) as copy:
                for row in accessions:
                    copy.write_row(row)
            cursor.execute("""
                CREATE INDEX ON stg_bulk_holdings (accession);
                CREATE INDEX ON stg_bulk_holdings (holding_id);
                CREATE INDEX ON stg_bulk_identifiers (holding_id);
                ANALYZE stg_bulk_holdings;
                ANALYZE stg_bulk_identifiers;
            """)
            # Replace any earlier rows for the same official report period.
            cursor.execute("""
                DELETE FROM portfolio_holdings ph
                USING funds f, stg_bulk_accessions a
                WHERE ph.fund_id = f.id
                  AND f.sec_series_id = a.series_id
                  AND ph.reporting_date = a.report_date
                  AND ph.data_source IN ('sec_edgar_nport', 'sec_edgar_nport_bulk')
            """)
            counts["replaced_rows"] = cursor.rowcount
            cursor.execute("""
                INSERT INTO portfolio_holdings (
                    fund_id, reporting_date, accession_number, holding_index,
                    security_name, ticker, isin, cusip, quantity, market_value,
                    market_value_currency, portfolio_weight, data_source,
                    source_url, retrieved_at
                )
                SELECT f.id, a.report_date, a.accession,
                       (row_number() OVER (PARTITION BY a.accession, f.id ORDER BY h.holding_id NULLS LAST, h.seq) - 1)::int,
                       h.issuer_name, i.ticker, i.isin, h.cusip, h.balance,
                       h.currency_value, h.currency_code, h.percentage,
                       'sec_edgar_nport_bulk', a.source_url, now()
                FROM stg_bulk_holdings h
                JOIN stg_bulk_accessions a ON a.accession = h.accession
                JOIN funds f ON f.sec_series_id = a.series_id AND f.domicile_country = 'US'
                LEFT JOIN (
                    SELECT holding_id, max(isin) AS isin, max(ticker) AS ticker
                    FROM stg_bulk_identifiers GROUP BY holding_id
                ) i ON i.holding_id = h.holding_id
            """)
            counts["holding_rows_inserted"] = cursor.rowcount
            # Guard against a truncated/partial data set silently shrinking
            # stored holdings. Raising here rolls back the delete above.
            min_ratio = _min_replacement_ratio()
            if counts["replaced_rows"] and counts["holding_rows_inserted"] < counts["replaced_rows"] * min_ratio:
                raise RuntimeError(
                    f"N-PORT {quarter}: inserted {counts['holding_rows_inserted']} rows but would replace "
                    f"{counts['replaced_rows']} (minimum ratio {min_ratio}); transaction rolled back")
            cursor.execute("""
                INSERT INTO fund_profile_snapshots (
                    fund_id, source_id, dataset, source_report_date, snapshot_key,
                    payload, source_url, retrieved_at
                )
                SELECT f.id, 'sec_open_end_fund_classes', 'aum_history', a.report_date,
                       'sec-nport-aum:' || a.series_id || ':' || a.report_date,
                       jsonb_build_object(
                           'net_assets', a.net_assets::text,
                           'currency', 'USD',
                           'scope', 'SEC series / fund level; not share-class assets',
                           'series_id', a.series_id,
                           'form', 'N-PORT',
                           'accession_number', a.accession,
                           'dataset', 'SEC DERA bulk N-PORT'
                       ),
                       a.source_url, now()
                FROM stg_bulk_accessions a
                JOIN funds f ON f.sec_series_id = a.series_id AND f.domicile_country = 'US'
                WHERE a.net_assets IS NOT NULL
                ON CONFLICT ON CONSTRAINT uq_fund_profile_source_snapshot
                DO UPDATE SET payload = EXCLUDED.payload, source_url = EXCLUDED.source_url,
                              retrieved_at = EXCLUDED.retrieved_at
            """)
            counts["aum_snapshots"] = cursor.rowcount
            # Asset allocation is the filed ASSET_CAT percentage summed per
            # category. Derivative positions can be reported above 100% of net
            # assets (notional), so the sums are stored exactly as filed.
            cursor.execute("""
                CREATE TEMP TABLE stg_bulk_asset_allocation ON COMMIT DROP AS
                SELECT h.accession,
                       COALESCE(NULLIF(h.asset_cat, ''), 'OTHER') AS code,
                       SUM(h.percentage) AS weight_pct
                FROM stg_bulk_holdings h
                WHERE h.percentage IS NOT NULL
                GROUP BY 1, 2;
                ANALYZE stg_bulk_asset_allocation;
            """)
            cursor.execute(f"""
                INSERT INTO fund_profile_snapshots (
                    fund_id, source_id, dataset, source_report_date, snapshot_key,
                    payload, source_url, retrieved_at
                )
                SELECT f.id, 'sec_nport_bulk', 'asset_allocation', a.report_date,
                       'sec-nport-asset-allocation:' || a.series_id || ':' || a.report_date,
                       jsonb_build_object(
                           'allocation', agg.items,
                           'report_date', a.report_date,
                           'series_id', a.series_id,
                           'accession_number', a.accession,
                           'scope', 'All positions in this N-PORT filing, summed by filed asset category',
                           'basis', 'Sum of SEC Form N-PORT reported percentage of net assets per asset category; derivative percentages are as filed and can exceed 100%',
                           'form', 'N-PORT',
                           'dataset', 'SEC DERA bulk N-PORT'
                       ),
                       a.source_url, now()
                FROM stg_bulk_accessions a
                JOIN funds f ON f.sec_series_id = a.series_id AND f.domicile_country = 'US'
                JOIN LATERAL (
                    SELECT jsonb_agg(jsonb_build_object(
                               'code', c.code,
                               'asset_class', {_asset_label_sql()},
                               'weight_pct', round(c.weight_pct, 4)
                           ) ORDER BY c.weight_pct DESC) AS items
                    FROM stg_bulk_asset_allocation c
                    WHERE c.accession = a.accession
                ) agg ON agg.items IS NOT NULL
                ON CONFLICT ON CONSTRAINT uq_fund_profile_source_snapshot
                DO UPDATE SET payload = EXCLUDED.payload, source_url = EXCLUDED.source_url,
                              retrieved_at = EXCLUDED.retrieved_at
            """)
            counts["asset_allocation_snapshots"] = cursor.rowcount
            cursor.execute("""
                UPDATE funds f
                SET holdings_status = 'available', holdings_report_date = x.max_date
                FROM (
                    SELECT f2.id, max(a.report_date) AS max_date
                    FROM funds f2
                    JOIN stg_bulk_accessions a ON a.series_id = f2.sec_series_id
                    WHERE f2.domicile_country = 'US'
                    GROUP BY f2.id
                ) x
                WHERE f.id = x.id
                  AND (f.holdings_report_date IS NULL OR f.holdings_report_date <= x.max_date)
            """)
            counts["funds_marked_available"] = cursor.rowcount
        connection.commit()

    result = {
        "dataset": quarter, "url": manifest["url"],
        "filings_in_dataset": len(submissions), "series_in_dataset": len(reported),
        "local_series_matched": len({item["series_id"] for item in targets.values()}),
        "filings_selected": len(targets),
        **counts,
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / f"sec_nport_bulk_import_{quarter}.json").write_text(
        json.dumps(result, indent=2) + "\n")
    return result
