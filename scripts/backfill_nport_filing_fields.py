"""Backfill official N-PORT Item C.4 fields on cached individual filings.

The bulk importer already stores every filed holding attribute.  Rows created by
the older ``sync-sec-holdings`` path predate those columns.  This script
re-parses the SEC submission text (cached on disk, downloaded once when needed)
and fills the ten official columns by the fund/report/holding key.

The original importer replicated one SEC series' positions to each local share
class.  We therefore expand each parsed position across the fund IDs mapped to
that accession and validate that the filing's series ID matches those funds.
Run with ``--apply`` to write; the default is a dry run.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import database_url
from app.holdings.sec_nport import FILINGS_CACHE, _request, parse_nport_xml

ACCESSION_RE = re.compile(r"(\d{10}-\d{2}-\d{6})\.txt$")
EMBEDDED_XML = re.compile(rb"<XML>\s*(.*?)\s*</XML>", flags=re.IGNORECASE | re.DOTALL)
COLUMNS = (
    "unit", "issuer_lei", "issuer_type", "asset_category", "investment_country",
    "is_restricted", "fair_value_level", "derivative_category", "payoff_profile",
    "exchange_rate",
)
UPDATE_COLUMNS = ", ".join(f"{name} = s.{name}" for name in COLUMNS)


def _raw_url() -> str:
    return database_url().replace("postgresql+psycopg://", "postgresql://", 1)


def _cache_path(accession: str, url: str) -> Path:
    """Place the filing in the same CIK directory used by the N-PORT importer."""
    parts = url.rstrip("/").split("/")
    cik = parts[-3].zfill(10)
    return FILINGS_CACHE / cik / parts[-1]


def _cache_index() -> dict[str, Path]:
    index: dict[str, Path] = {}
    for path in FILINGS_CACHE.glob("*/*.txt"):
        match = ACCESSION_RE.search(path.name)
        if match:
            index[match.group(1)] = path
    return index


def _download(accession: str, url: str) -> Path | None:
    path = _cache_path(accession, url)
    if path.exists():
        return path
    try:
        payload = _request(url)
    except Exception as error:  # noqa: BLE001 - report, do not abort the whole run
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def _parse(path: Path, accession: str) -> dict | None:
    payload = path.read_bytes()
    embedded = EMBEDDED_XML.search(payload)
    if not embedded:
        return None
    try:
        return parse_nport_xml(
            embedded.group(1), accession_number=accession,
            source_url=f"https://www.sec.gov/Archives/edgar/data/cached/{accession}.txt")
    except Exception:  # noqa: BLE001 - one bad cache file must not stop the run
        return None


def run(*, apply: bool, limit: int | None, download: bool) -> dict:
    with psycopg.connect(_raw_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT accession_number, count(*) AS rows, min(source_url) AS url
                FROM portfolio_holdings
                WHERE data_source = 'sec_edgar_nport' AND unit IS NULL
                GROUP BY 1 ORDER BY 1
            """)
            pending = cursor.fetchall()
    if limit:
        pending = pending[:limit]
    result = {"pending_accessions": len(pending), "rows_to_fill": sum(row[1] for row in pending),
              "downloaded": 0, "parse_failures": 0, "series_mismatch": 0,
              "accessions_parsed": 0, "rows_updated": 0, "apply": apply}

    index = _cache_index()
    missing = [row for row in pending if row[0] not in index]
    if download:
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(_download, row[0], row[2]): row[0] for row in missing}
            for future, accession in [(f, futures[f]) for f in futures]:
                path = future.result()
                if path is not None:
                    index[accession] = path
                    result["downloaded"] += 1
    selected = [(row[0], row[1], index[row[0]]) for row in pending if row[0] in index]
    result["cached_accessions"] = len(selected)

    with psycopg.connect(_raw_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT DISTINCT accession_number, fund_id, reporting_date
                FROM portfolio_holdings
                WHERE data_source = 'sec_edgar_nport' AND unit IS NULL
            """)
            mapping: dict[str, list[tuple[int, object]]] = defaultdict(list)
            series_of: dict[int, str | None] = {}
            for accession, fund_id, report_date in cursor.fetchall():
                mapping[accession].append((fund_id, report_date))
            cursor.execute("SELECT id, sec_series_id FROM funds")
            series_of = dict(cursor.fetchall())

    parsed_reports: list[tuple[str, dict]] = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(_parse, path, accession): accession
                   for accession, _, path in selected}
        for future in futures:
            report = future.result()
            accession = futures[future]
            if not report or not report.get("holdings"):
                result["parse_failures"] += 1
                continue
            fund_series = {series_of.get(fund_id) for fund_id, _ in mapping[accession]}
            if fund_series != {report["series_id"]}:
                result["series_mismatch"] += 1
                continue
            parsed_reports.append((accession, report))
    result["accessions_parsed"] = len(parsed_reports)

    if apply and parsed_reports:
        with psycopg.connect(_raw_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    CREATE TEMP TABLE stg_nport_fields (
                        fund_id integer, reporting_date date, holding_index integer,
                        unit varchar(4), issuer_lei varchar(20), issuer_type varchar(16),
                        asset_category varchar(16), investment_country varchar(3),
                        is_restricted boolean, fair_value_level smallint,
                        derivative_category varchar(8), payoff_profile varchar(200),
                        exchange_rate numeric(24,10)
                    ) ON COMMIT DROP
                """)
                with cursor.copy(
                    "COPY stg_nport_fields (fund_id, reporting_date, holding_index, "
                    + ", ".join(COLUMNS) + ") FROM STDIN"
                ) as copy:
                    for accession, report in parsed_reports:
                        for fund_id, report_date in mapping[accession]:
                            for position in report["holdings"]:
                                copy.write_row(
                                    (fund_id, report_date, position["holding_index"])
                                    + tuple(position.get(column) for column in COLUMNS))
                cursor.execute("CREATE INDEX ON stg_nport_fields (fund_id, reporting_date, holding_index)")
                cursor.execute("ANALYZE stg_nport_fields")
                cursor.execute(f"""
                    UPDATE portfolio_holdings h SET {UPDATE_COLUMNS}
                    FROM stg_nport_fields s
                    WHERE h.fund_id = s.fund_id
                      AND h.reporting_date = s.reporting_date
                      AND h.holding_index = s.holding_index
                      AND h.data_source = 'sec_edgar_nport'
                """)
                result["rows_updated"] = cursor.rowcount
            connection.commit()
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "sec_nport_filing_backfill.json").write_text(
        json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--download", action="store_true",
                        help="Download and cache SEC filings that are missing locally")
    args = parser.parse_args()
    print(json.dumps(run(apply=args.apply, limit=args.limit, download=args.download), indent=2))
