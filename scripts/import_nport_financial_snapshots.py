"""Import unused official N-PORT financial statement facts as snapshots.

The N-PORT bulk importer already stores series net assets as ``aum_history``.
The same filed table carries total assets/liabilities, borrowings, cash,
credit-spread ranges, three months of realized/unrealized gains and sales,
reinvestment and redemption flows.  This script reads the cached archives only
(it makes no network requests) and stores the newest report per SEC series as a
``nport_financials`` snapshot.  It never rewrites holdings or core fund columns.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import database_url

BULK_ROOT = ROOT / "data" / "raw" / "united_states" / "nport_bulk"
SOURCE_ID = "sec_open_end_fund_classes"

FIELDS = {
    "TOTAL_ASSETS": "total_assets",
    "TOTAL_LIABILITIES": "total_liabilities",
    "NET_ASSETS": "net_assets",
    "ASSETS_ATTRBT_TO_MISC_SECURITY": "assets_attributed_to_miscellaneous_securities",
    "ASSETS_INVESTED": "assets_invested",
    "BORROWING_PAY_WITHIN_1YR": "borrowings_payable_within_1yr",
    "CTRLD_COMPANIES_PAY_WITHIN_1YR": "payables_to_controlled_companies_within_1yr",
    "OTHER_AFFILIA_PAY_WITHIN_1YR": "payables_to_other_affiliates_within_1yr",
    "OTHER_PAY_WITHIN_1YR": "other_payables_within_1yr",
    "BORROWING_PAY_AFTER_1YR": "borrowings_payable_after_1yr",
    "CTRLD_COMPANIES_PAY_AFTER_1YR": "payables_to_controlled_companies_after_1yr",
    "OTHER_AFFILIA_PAY_AFTER_1YR": "payables_to_other_affiliates_after_1yr",
    "OTHER_PAY_AFTER_1YR": "other_payables_after_1yr",
    "DELAYED_DELIVERY": "delayed_delivery",
    "STANDBY_COMMITMENT": "standby_commitment",
    "LIQUIDATION_PREFERENCE": "liquidation_preference",
    "CASH_NOT_RPTD_IN_C_OR_D": "cash_not_reported_in_item_c_or_d",
    "CREDIT_SPREAD_3MON_INVEST": "credit_spread_3month_investment_grade",
    "CREDIT_SPREAD_1YR_INVEST": "credit_spread_1year_investment_grade",
    "CREDIT_SPREAD_5YR_INVEST": "credit_spread_5year_investment_grade",
    "CREDIT_SPREAD_10YR_INVEST": "credit_spread_10year_investment_grade",
    "CREDIT_SPREAD_30YR_INVEST": "credit_spread_30year_investment_grade",
    "CREDIT_SPREAD_3MON_NONINVEST": "credit_spread_3month_noninvestment_grade",
    "CREDIT_SPREAD_1YR_NONINVEST": "credit_spread_1year_noninvestment_grade",
    "CREDIT_SPREAD_5YR_NONINVEST": "credit_spread_5year_noninvestment_grade",
    "CREDIT_SPREAD_10YR_NONINVEST": "credit_spread_10year_noninvestment_grade",
    "CREDIT_SPREAD_30YR_NONINVEST": "credit_spread_30year_noninvestment_grade",
    "IS_NON_CASH_COLLATERAL": "is_non_cash_collateral",
    "NET_REALIZE_GAIN_NONDERIV_MON1": "net_realized_gain_nonderivative_month1",
    "NET_UNREALIZE_AP_NONDERIV_MON1": "net_unrealized_appreciation_nonderivative_month1",
    "NET_REALIZE_GAIN_NONDERIV_MON2": "net_realized_gain_nonderivative_month2",
    "NET_UNREALIZE_AP_NONDERIV_MON2": "net_unrealized_appreciation_nonderivative_month2",
    "NET_REALIZE_GAIN_NONDERIV_MON3": "net_realized_gain_nonderivative_month3",
    "NET_UNREALIZE_AP_NONDERIV_MON3": "net_unrealized_appreciation_nonderivative_month3",
    "SALES_FLOW_MON1": "sales_flow_month1",
    "REINVESTMENT_FLOW_MON1": "reinvestment_flow_month1",
    "REDEMPTION_FLOW_MON1": "redemption_flow_month1",
    "SALES_FLOW_MON2": "sales_flow_month2",
    "REINVESTMENT_FLOW_MON2": "reinvestment_flow_month2",
    "REDEMPTION_FLOW_MON2": "redemption_flow_month2",
    "SALES_FLOW_MON3": "sales_flow_month3",
    "REINVESTMENT_FLOW_MON3": "reinvestment_flow_month3",
    "REDEMPTION_FLOW_MON3": "redemption_flow_month3",
}


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


def _value(value: str | None) -> str | None:
    text = (value or "").strip().replace(",", "")
    if not text or text.upper() in {"N/A", "NA", "NONE", "-", "--"}:
        return None
    if text.upper() in {"Y", "YES", "TRUE", "1", "N", "NO", "FALSE", "0"}:
        return text.upper() in {"Y", "YES", "TRUE", "1"}
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    return str(number)


def _flags(row: dict[str, str]) -> dict[str, bool]:
    text = (row.get("IS_NON_CASH_COLLATERAL") or "").strip().upper()
    if text in {"Y", "YES", "TRUE", "1", "N", "NO", "FALSE", "0"}:
        return {"is_non_cash_collateral": text in {"Y", "YES", "TRUE", "1"}}
    return {}


def collect() -> dict[str, dict[str, Any]]:
    """Newest filed financial statement per SEC series across cached archives."""
    best: dict[str, dict[str, Any]] = {}
    for quarter_dir in sorted(p for p in BULK_ROOT.iterdir() if p.is_dir()):
        submissions = quarter_dir / "SUBMISSION.tsv"
        registrants = quarter_dir / "REGISTRANT.tsv"
        info = quarter_dir / "FUND_REPORTED_INFO.tsv"
        if not (submissions.exists() and info.exists()):
            continue
        filed: dict[str, date] = {}
        for row in _rows(submissions):
            parsed = _date(row.get("REPORT_DATE"))
            if parsed:
                filed[(row.get("ACCESSION_NUMBER") or "").strip()] = parsed
        ciks: dict[str, str] = {}
        if registrants.exists():
            for row in _rows(registrants):
                raw = "".join(ch for ch in (row.get("CIK") or "") if ch.isdigit())
                accession = (row.get("ACCESSION_NUMBER") or "").strip()
                if raw and accession:
                    ciks[accession] = raw.zfill(10)
        for row in _rows(info):
            accession = (row.get("ACCESSION_NUMBER") or "").strip()
            series_id = (row.get("SERIES_ID") or "").strip()
            report_date = filed.get(accession)
            if not series_id or not accession or report_date is None:
                continue
            payload: dict[str, Any] = {}
            for column, label in FIELDS.items():
                value = _value(row.get(column))
                if value is not None:
                    payload[label] = value
            payload.update(_flags(row))
            if not payload:
                continue
            current = best.get(series_id)
            key = (report_date, accession)
            if current is None or key > (current["report_date"], current["accession"]):
                best[series_id] = {
                    "series_id": series_id, "report_date": report_date,
                    "accession": accession, "cik": ciks.get(accession),
                    "payload": payload,
                }
    return best


def apply(best: dict[str, dict[str, Any]], *, dry_run: bool) -> dict[str, Any]:
    url = database_url().replace("postgresql+psycopg://", "postgresql://", 1)
    result: dict[str, Any] = {"series_in_cache": len(best), "dry_run": dry_run}
    with psycopg.connect(url) as connection, connection.cursor() as cursor:
        cursor.execute("""
            CREATE TEMP TABLE stg_nport_financials (
                series_id text PRIMARY KEY, report_date date, accession text,
                cik text, payload jsonb, source_url text
            ) ON COMMIT DROP""")
        with cursor.copy("""COPY stg_nport_financials
                (series_id, report_date, accession, cik, payload, source_url) FROM STDIN""") as copy:
            for item in best.values():
                cik = item["cik"]
                source_url = (
                    f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
                    f"{item['accession'].replace('-', '')}/{item['accession']}.txt"
                    if cik else
                    f"https://www.sec.gov/Archives/edgar/data/"
                    f"{item['accession'].replace('-', '')}/{item['accession']}.txt")
                copy.write_row((item["series_id"], item["report_date"], item["accession"],
                                cik, json.dumps(item["payload"]), source_url))
        cursor.execute("""
            SELECT count(*) FROM funds f JOIN stg_nport_financials s
              ON s.series_id = f.sec_series_id AND f.domicile_country = 'US'
            WHERE EXISTS (SELECT 1 FROM jsonb_object_keys(s.payload) k
                          WHERE k <> 'is_non_cash_collateral')
        """)
        result["local_fund_snapshots"] = cursor.fetchone()[0]
        if dry_run:
            connection.rollback()
            return result
        cursor.execute("""
            INSERT INTO fund_profile_snapshots (
                fund_id, source_id, dataset, source_report_date, snapshot_key,
                payload, source_url, retrieved_at
            )
            SELECT f.id, %s, 'nport_financials', s.report_date,
                   'sec-nport-financials:' || s.series_id || ':' || s.accession,
                   s.payload || jsonb_build_object(
                       'scope', 'SEC series / fund level statement values as filed in Form N-PORT',
                       'series_id', s.series_id,
                       'form', 'N-PORT',
                       'accession_number', s.accession,
                       'currency', 'USD'),
                   s.source_url, now()
            FROM stg_nport_financials s
            JOIN funds f ON f.sec_series_id = s.series_id AND f.domicile_country = 'US'
            ON CONFLICT ON CONSTRAINT uq_fund_profile_source_snapshot
            DO UPDATE SET source_report_date = EXCLUDED.source_report_date,
                          payload = EXCLUDED.payload,
                          source_url = EXCLUDED.source_url,
                          retrieved_at = now()
        """, (SOURCE_ID,))
        result["snapshots_written"] = cursor.rowcount
        connection.commit()
    result["finished_at"] = datetime.now().isoformat(timespec="seconds")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(apply(collect(), dry_run=args.dry_run), indent=2))


if __name__ == "__main__":
    main()
