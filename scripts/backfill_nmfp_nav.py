"""Backfill money-market NAVs for US classes with no stored NAV observation.

The N-MFP monthly archive files each class's daily NAV. This script reads only
cached archives, maps the filed class ID to local share classes, and inserts
positive NAVs with the official filing URL. Existing NAV rows are never changed.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import database_url

RAW = ROOT / "data" / "raw" / "united_states" / "nmfp_bulk"
SOURCE_ID = "sec_nmfp_money_market"


def _rows(path: Path):
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        yield from csv.DictReader(handle, delimiter="\t")


def _date(value: str | None) -> date | None:
    text = (value or "").strip()
    if not text:
        return None
    for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text[:11].strip(), fmt).date()
        except ValueError:
            continue
    return None


def collect() -> dict[tuple[str, date, str], Decimal]:
    result: dict[tuple[str, date, str], Decimal] = {}
    submissions: dict[str, str] = {}
    for archive_dir in sorted(p for p in RAW.iterdir() if p.is_dir()):
        sub = archive_dir / "NMFP_SUBMISSION.tsv"
        if sub.exists():
            for row in _rows(sub):
                accession = (row.get("ACCESSION_NUMBER") or "").strip()
                if not accession:
                    continue
                cik = "".join(ch for ch in (row.get("CIK") or "") if ch.isdigit())
                submissions[accession] = cik.zfill(10) if cik else ""
        daily = archive_dir / "NMFP_DLYNETASSETVALUEPERSHARC.tsv"
        if not daily.exists():
            continue
        for row in _rows(daily):
            accession = (row.get("ACCESSION_NUMBER") or "").strip()
            if accession not in submissions:
                continue
            class_id = (row.get("CLASSESID") or "").strip()
            valuation_date = _date(row.get("DLYNETASSETVALUEPERSHAREDATEC"))
            nav_text = (row.get("DLYNETASSETVALUEPERSHARECLASS") or "").strip().replace(",", "")
            if not class_id or valuation_date is None or not nav_text:
                continue
            try:
                nav = Decimal(nav_text)
            except InvalidOperation:
                continue
            if nav <= 0:
                continue
            cik = submissions[accession]
            accession_path = accession.replace("-", "")
            source_url = (
                f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_path}/{accession}.txt"
                if cik else
                f"https://www.sec.gov/Archives/edgar/data/{accession_path}/{accession}.txt")
            key = (class_id, valuation_date, source_url)
            if key not in result or nav > result[key]:
                result[key] = nav
    return result


def apply(navs: dict[tuple[str, date, str], Decimal], *, dry_run: bool) -> dict:
    url = database_url().replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(url) as connection, connection.cursor() as cursor:
        cursor.execute("""
            CREATE TEMP TABLE stg_nmfp_nav (
                class_id text, valuation_date date, nav numeric,
                source_url text, source_id text
            ) ON COMMIT DROP""")
        with cursor.copy("COPY stg_nmfp_nav (class_id, valuation_date, nav, source_url, source_id) FROM STDIN") as copy:
            for (class_id, valuation_date, source_url), nav in navs.items():
                copy.write_row((class_id, valuation_date, nav, source_url, SOURCE_ID))
        select_sql = """
            SELECT DISTINCT ON (f.id, s.valuation_date)
                   f.id, s.valuation_date, s.nav, 'USD', s.source_id, s.source_url,
                   'single_daily_nav', now()
            FROM stg_nmfp_nav s
            JOIN funds f ON f.source_fund_id = s.class_id AND f.domicile_country = 'US'
            WHERE NOT EXISTS (
                SELECT 1 FROM nav_observations n
                WHERE n.fund_id = f.id AND n.valuation_date = s.valuation_date
                  AND n.currency = 'USD')
            ORDER BY f.id, s.valuation_date, s.nav DESC
        """
        if dry_run:
            cursor.execute("SELECT count(*) FROM (" + select_sql + ") q")
            count = cursor.fetchone()[0]
            connection.rollback()
            return {"candidate_nav_rows": count, "filed_nav_facts": len(navs), "dry_run": True}
        cursor.execute("""
            INSERT INTO nav_observations
                (fund_id, valuation_date, nav, currency, source_id, source_url, ohlc_basis, retrieved_at)
            """ + select_sql)
        written = cursor.rowcount
        connection.commit()
    return {"nav_rows_written": written, "filed_nav_facts": len(navs), "dry_run": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(apply(collect(), dry_run=args.dry_run), indent=2))


if __name__ == "__main__":
    main()
