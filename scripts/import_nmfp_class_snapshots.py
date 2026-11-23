"""Import class-level Form N-MFP financial facts as snapshots.

The N-MFP importer stores holdings, adviser/administrator, and daily NAV
observations.  The same monthly archive has a class-level table with minimum
investment, class net assets, shares outstanding, weekly subscriptions and
redemptions, seven-day yield, and shareholder composition.  This script reads
the cached archives only and stores the newest filing per class as an
``nmfp_class_financials`` snapshot.  It does not derive NAV from net assets and
shares and never rewrites core fund columns.
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

RAW = ROOT / "data" / "raw" / "united_states" / "nmfp_bulk"
SOURCE_ID = "sec_nmfp_money_market"

FIELDS = {
    "MININITIALINVESTMENT": "minimum_initial_investment",
    "NETASSETSOFCLASS": "net_assets_of_class",
    "NUMBEROFSHARESOUTSTANDING": "number_of_shares_outstanding",
    "NETASSETPERSHAREFRIDAYWEEK1": "nav_per_share_friday_week_1",
    "NETASSETPERSHAREFRIDAYWEEK2": "nav_per_share_friday_week_2",
    "NETASSETPERSHAREFRIDAYWEEK3": "nav_per_share_friday_week_3",
    "NETASSETPERSHAREFRIDAYWEEK4": "nav_per_share_friday_week_4",
    "NETASSETPERSHAREFRIDAYWEEK5": "nav_per_share_friday_week_5",
    "GROSSSUBSCRIPTIONFRIDAYWEEK1": "gross_subscription_friday_week_1",
    "GROSSREDEMPTIONFRIDAYWEEK1": "gross_redemption_friday_week_1",
    "GROSSSUBSCRIPTIONFRIDAYWEEK2": "gross_subscription_friday_week_2",
    "GROSSREDEMPTIONFRIDAYWEEK2": "gross_redemption_friday_week_2",
    "GROSSSUBSCRIPTIONFRIDAYWEEK3": "gross_subscription_friday_week_3",
    "GROSSREDEMPTIONFRIDAYWEEK3": "gross_redemption_friday_week_3",
    "GROSSSUBSCRIPTIONFRIDAYWEEK4": "gross_subscription_friday_week_4",
    "GROSSREDEMPTIONFRIDAYWEEK4": "gross_redemption_friday_week_4",
    "GROSSSUBSCRIPTIONFRIDAYWEEK5": "gross_subscription_friday_week_5",
    "GROSSREDEMPTIONFRIDAYWEEK5": "gross_redemption_friday_week_5",
    "TOTFORMNTHWLYGROSSSUBSCRIPTION": "total_monthly_gross_subscriptions",
    "TOTALGROSSSUBSCRIPTIONS": "total_gross_subscriptions",
    "TOTFORMNTHWLYGROSSREDEMPTION": "total_monthly_gross_redemptions",
    "TOTALGROSSREDEMPTIONS": "total_gross_redemptions",
    "NETASSETVALUEPERSHARE_L": "net_asset_value_per_share_as_filed",
    "NETSHAREHOLDERFLOWACTIVITYFO_L": "net_shareholder_flow_as_filed",
    "SEVENDAYNETYIELD": "seven_day_net_yield",
    "PCTSHAREHOLDERCOMPNONFINANCIA": "pct_shareholder_nonfinancial_business",
    "PCTSHAREHOLDERCOMPPENSIONPLAN": "pct_shareholder_pension_plan",
    "PCTSHAREHOLDERCOMPNONPROFIT": "pct_shareholder_nonprofit",
    "PCTSHAREHOLDERCOMPMUNICIPAL": "pct_shareholder_municipal",
    "PCTSHAREHOLDERCOMPREGINVESTME": "pct_shareholder_regulated_investment_company",
    "PCTSHAREHOLDERCOMPPRIVATEFUND": "pct_shareholder_private_fund",
    "PCTSHAREHOLDERCOMPDEPOSITORYI": "pct_shareholder_depository_institution",
    "PCTSHAREHOLDERCOMPSOVEREIGNFU": "pct_shareholder_sovereign_fund",
    "PCTSHAREHOLDERCOMPBROKERDEALE": "pct_shareholder_broker_dealer",
    "PCTSHAREHOLDERCOMPINSURANCE": "pct_shareholder_insurance_company",
    "PCTSHAREHOLDERCOMPOTHER": "pct_shareholder_other",
    "SHARECANCELLATIONREPORTPERIOD": "share_cancellation_report_period",
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
    try:
        return str(Decimal(text))
    except InvalidOperation:
        return text[:200]


def collect() -> dict[str, dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for archive_dir in sorted(p for p in RAW.iterdir() if p.is_dir()):
        submissions = archive_dir / "NMFP_SUBMISSION.tsv"
        classes = archive_dir / "NMFP_CLASSLEVELINFO.tsv"
        if not (submissions.exists() and classes.exists()):
            continue
        filed: dict[str, dict[str, Any]] = {}
        for row in _rows(submissions):
            accession = (row.get("ACCESSION_NUMBER") or "").strip()
            report_date = _date(row.get("REPORTDATE"))
            if not accession or report_date is None:
                continue
            cik = "".join(ch for ch in (row.get("CIK") or "") if ch.isdigit())
            filed[accession] = {"report_date": report_date, "cik": cik.zfill(10) if cik else None}
        for row in _rows(classes):
            accession = (row.get("ACCESSION_NUMBER") or "").strip()
            class_id = (row.get("CLASSESID") or "").strip()
            info = filed.get(accession)
            if not class_id or info is None:
                continue
            key = (info["report_date"], accession)
            current = best.get(class_id)
            if current is not None and key <= (current["report_date"], current["accession"]):
                continue
            payload = {}
            for column, label in FIELDS.items():
                value = _value(row.get(column))
                if value is not None:
                    payload[label] = value
            if not payload:
                continue
            best[class_id] = {
                "class_id": class_id, "accession": accession,
                "report_date": info["report_date"], "cik": info["cik"],
                "payload": payload,
            }
    return best


def apply(best: dict[str, dict[str, Any]], *, dry_run: bool) -> dict[str, Any]:
    url = database_url().replace("postgresql+psycopg://", "postgresql://", 1)
    result: dict[str, Any] = {"classes_in_cache": len(best), "dry_run": dry_run}
    with psycopg.connect(url) as connection, connection.cursor() as cursor:
        cursor.execute("""
            CREATE TEMP TABLE stg_nmfp_classes (
                class_id text PRIMARY KEY, report_date date, accession text,
                cik text, payload jsonb, source_url text
            ) ON COMMIT DROP""")
        with cursor.copy("""COPY stg_nmfp_classes
                (class_id, report_date, accession, cik, payload, source_url) FROM STDIN""") as copy:
            for item in best.values():
                source_url = (
                    f"https://www.sec.gov/Archives/edgar/data/{int(item['cik'])}/"
                    f"{item['accession'].replace('-', '')}/{item['accession']}.txt"
                    if item["cik"] else
                    f"https://www.sec.gov/Archives/edgar/data/"
                    f"{item['accession'].replace('-', '')}/{item['accession']}.txt")
                copy.write_row((item["class_id"], item["report_date"], item["accession"],
                                item["cik"], json.dumps(item["payload"]), source_url))
        cursor.execute("""
            SELECT count(*) FROM funds f JOIN stg_nmfp_classes s
              ON s.class_id = f.source_fund_id AND f.domicile_country = 'US'
            WHERE s.payload <> '{}'::jsonb
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
            SELECT f.id, %s, 'nmfp_class_financials', s.report_date,
                   'sec-nmfp-class:' || s.class_id || ':' || s.accession,
                   s.payload || jsonb_build_object(
                       'scope', 'class-level financial facts as filed in Form N-MFP',
                       'class_id', s.class_id,
                       'form', 'N-MFP',
                       'accession_number', s.accession,
                       'currency', 'USD'),
                   s.source_url, now()
            FROM stg_nmfp_classes s
            JOIN funds f ON f.source_fund_id = s.class_id AND f.domicile_country = 'US'
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
