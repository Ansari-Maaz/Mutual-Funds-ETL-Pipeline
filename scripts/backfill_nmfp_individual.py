"""Import official money-market holdings from individual SEC N-MFP filings.

The SEC DERA monthly N-MFP archives do not cover every filing series.  Many
share classes with no N-PORT holdings have an individual Form N-MFP / N-MFP2 /
N-MFP3 filing whose XML contains a complete ``scheduleOfPortfolioSecurities``
and class-level daily NAV history.  This script reads the latest individual
filing for each relevant registrant, matches the filed ``seriesId`` and
``classesId`` to local US funds, and inserts only fields that are absent from
the database.  Existing holdings and NAV observations are never changed.

Usage::

    ./.venv/bin/python scripts/backfill_nmfp_individual.py --limit-ciks 5 --dry-run
    ./.venv/bin/python scripts/backfill_nmfp_individual.py --assign-usd-nav
"""
from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from app.config import database_url
from backfill_ncsr_nav import _submissions

RAW = ROOT / "data" / "raw" / "united_states" / "nmfp_individual"
SOURCE_ID = "sec_nmfp_individual"
NAV_SOURCE_ID = "sec_nmfp_individual"
FORM_PREFIXES = ("N-MFP",)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child_text(element: ET.Element, name: str) -> str | None:
    for child in element.iter():
        if _local(child.tag) == name and child.text and child.text.strip():
            return child.text.strip()
    return None


def _decimal(value: str | None) -> float | None:
    if not value:
        return None
    text = value.strip().replace(",", "").replace("$", "")
    if not text or text.lower() in {"n/a", "na", "-", "--"}:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    if number == 0 or abs(number) > 1e15:
        return None
    return number


def _filing_path(cik: str, accession: str, name: str, *, refresh: bool) -> Path:
    path = RAW / accession / name
    if path.exists() and not refresh:
        return path
    url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{name}"
    from app.holdings.sec_nport import _request
    payload = _request(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def _parse_filing(path: Path) -> dict[str, Any]:
    root = ET.parse(path).getroot()
    result: dict[str, Any] = {
        "series_id": _child_text(root, "seriesId"),
        "series_name": _child_text(root, "nameOfSeries"),
        "report_date": _child_text(root, "reportDate"),
        "holdings": [],
        "navs": [],
    }
    for element in root.iter():
        if _local(element.tag) not in {"scheduleOfPortfolioSecuritiesInfo", "scheduleOfPortfolioSecurities"}:
            continue
        name = (_child_text(element, "titleOfIssuer")
                or _child_text(element, "nameOfIssuer")
                or _child_text(element, "titleOfSecurity"))
        market_value = _decimal(_child_text(element, "includingValueOfAnySponsorSupport")
                                or _child_text(element, "excludingValueOfAnySponsorSupport"))
        if not name or market_value is None:
            continue
        percentage = _decimal(_child_text(element, "percentageOfMoneyMarketFundNetAssets"))
        result["holdings"].append({
            "security_name": name[:500],
            "cusip": (_child_text(element, "CUSIPMember") or None),
            "isin": (_child_text(element, "ISINId") or None),
            "market_value": market_value,
            "portfolio_weight": percentage * 100 if percentage is not None else None,
        })
    for element in root.iter():
        if _local(element.tag) != "classLevelInfo":
            continue
        class_id = _child_text(element, "classesId")
        if not class_id:
            continue
        nav_rows: list[tuple[date, float]] = []
        for child in element:
            if _local(child.tag) != "dailyNetAssetValuePerShareClass":
                continue
            value = None
            nav_date = None
            for grandchild in child:
                tag = _local(grandchild.tag)
                if tag == "dailyNetAssetValuePerShareClass" and grandchild.text:
                    value = _decimal(grandchild.text)
                elif tag == "dailyNetAssetValuePerShareDateClass" and grandchild.text:
                    try:
                        nav_date = date.fromisoformat(grandchild.text.strip()[:10])
                    except ValueError:
                        pass
            if value is not None and nav_date is not None:
                nav_rows.append((nav_date, value))
        if nav_rows:
            result["navs"].append({"class_id": class_id, "rows": nav_rows})
    return result


def _targets(connection: psycopg.Connection) -> tuple[set[int], set[int], list[str]]:
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT f.id,
                   NOT EXISTS (SELECT 1 FROM portfolio_holdings h WHERE h.fund_id=f.id) AS needs_holdings,
                   NOT EXISTS (SELECT 1 FROM nav_observations n WHERE n.fund_id=f.id AND n.nav>0) AS needs_nav
            FROM funds f
            WHERE f.domicile_country='US' AND f.sec_cik IS NOT NULL
              AND (NOT EXISTS (SELECT 1 FROM portfolio_holdings h WHERE h.fund_id=f.id)
                   OR NOT EXISTS (SELECT 1 FROM nav_observations n WHERE n.fund_id=f.id AND n.nav>0))
        """)
        rows = cursor.fetchall()
        cursor.execute("""
            SELECT DISTINCT f.sec_cik FROM funds f
            WHERE f.domicile_country='US' AND f.sec_cik IS NOT NULL
              AND (NOT EXISTS (SELECT 1 FROM portfolio_holdings h WHERE h.fund_id=f.id)
                   OR NOT EXISTS (SELECT 1 FROM nav_observations n WHERE n.fund_id=f.id AND n.nav>0))
            ORDER BY f.sec_cik
        """)
        ciks = [row[0] for row in cursor.fetchall()]
    holdings = {fund_id for fund_id, needs_holdings, _ in rows if needs_holdings}
    navs = {fund_id for fund_id, _, needs_nav in rows if needs_nav}
    return holdings, navs, ciks


def _local_funds(connection: psycopg.Connection, ciks: list[str]) -> tuple[dict[str, list[int]], dict[str, list[int]]]:
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT f.sec_cik, f.sec_series_id, f.source_fund_id, f.id
            FROM funds f
            WHERE f.domicile_country='US' AND f.sec_cik = ANY(%s)
        """, (ciks,))
        rows = cursor.fetchall()
    by_series: dict[str, list[int]] = defaultdict(list)
    by_class: dict[str, list[int]] = defaultdict(list)
    for cik, series_id, class_id, fund_id in rows:
        if series_id:
            by_series[series_id].append(fund_id)
        if class_id:
            by_class[class_id].append(fund_id)
    return by_series, by_class


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit-ciks", type=int)
    parser.add_argument("--cik", action="append")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--assign-usd-nav", action="store_true")
    parser.add_argument("--max-filings", type=int, default=12,
                        help="Newest individual filings to inspect per registrant")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db_url = database_url().replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(db_url) as connection, connection.cursor() as cursor:
        holdings_targets, nav_targets, ciks = _targets(connection)
        if args.cik:
            wanted = {cik.zfill(10) for cik in args.cik}
            ciks = [cik for cik in ciks if cik in wanted]
        if args.limit_ciks:
            ciks = ciks[:args.limit_ciks]
        print(json.dumps({"registrants_targeted": len(ciks),
                          "needs_holdings": len(holdings_targets),
                          "needs_nav": len(nav_targets)}), flush=True)
        by_series, by_class = _local_funds(connection, ciks)

        holdings: list[tuple[int, date, str, int, str, str | None, str | None, float, float | None, str, str]] = []
        navs: list[tuple[int, date, float, str, str, str]] = []
        stats: dict[str, int] = defaultdict(int)
        for index, cik in enumerate(ciks, 1):
            try:
                submissions = _submissions(cik, refresh=args.refresh)
            except Exception as error:  # noqa: BLE001
                stats["submission_errors"] += 1
                print(f"submission error {cik}: {error}", flush=True)
                continue
            recent = submissions.get("filings", {}).get("recent", {})
            forms = recent.get("form") or []
            filing_rows = [
                {"form": forms[i], "filingDate": (recent.get("filingDate") or [""])[i],
                 "reportDate": (recent.get("reportDate") or [""])[i],
                 "accessionNumber": (recent.get("accessionNumber") or [""])[i],
                 "primaryDocument": (recent.get("primaryDocument") or [""])[i]}
                for i in range(min(len(forms), len(recent.get("accessionNumber") or [])))
                if (forms[i] or "").upper().startswith(FORM_PREFIXES)
            ]
            if not filing_rows:
                stats["no_nmfp"] += 1
                continue
            best_by_series: dict[str, tuple[str, str, dict[str, Any]]] = {}
            for filing in filing_rows[:args.max_filings]:
                accession = filing["accessionNumber"]
                name = (filing.get("primaryDocument") or "primary_doc.xml").rsplit("/", 1)[-1]
                try:
                    path = _filing_path(cik, accession, name, refresh=args.refresh)
                    parsed = _parse_filing(path)
                except Exception as error:  # noqa: BLE001
                    stats["parse_errors"] += 1
                    print(f"parse error {cik} {accession}: {error}", flush=True)
                    continue
                series_id = parsed["series_id"]
                if not series_id or series_id not in by_series:
                    continue
                if series_id in best_by_series:
                    continue  # filings are newest first
                best_by_series[series_id] = (accession, name, parsed)
            for series_id, (accession, name, parsed) in best_by_series.items():
                report_date_text = parsed["report_date"] or ""
                try:
                    report_date = date.fromisoformat(report_date_text[:10])
                except ValueError:
                    continue
                source_url = (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
                              f"{accession.replace('-', '')}/{name}")
                fund_ids = [fund_id for fund_id in by_series.get(series_id, [])
                            if fund_id in holdings_targets]
                for fund_id in fund_ids:
                    for holding_index, holding in enumerate(parsed["holdings"], 1):
                        holdings.append((fund_id, report_date, source_url, holding_index,
                                         holding["security_name"], holding["cusip"], holding["isin"],
                                         holding["market_value"], holding["portfolio_weight"],
                                         accession, SOURCE_ID))
                        stats["holding_candidates"] += 1
                if args.assign_usd_nav:
                    for class_info in parsed["navs"]:
                        nav_fund_ids = [fund_id for fund_id in by_class.get(class_info["class_id"], [])
                                        if fund_id in nav_targets]
                        for fund_id in nav_fund_ids:
                            for nav_date, value in class_info["rows"]:
                                navs.append((fund_id, nav_date, value, "USD", NAV_SOURCE_ID,
                                             source_url, "single_daily_nav"))
                                stats["nav_candidates"] += 1
            if index % 10 == 0 or index == len(ciks):
                print(json.dumps({"processed": index, "total": len(ciks), **stats}), flush=True)

        print(json.dumps({**stats}, indent=2), flush=True)
        if args.dry_run or (not holdings and not navs):
            connection.rollback()
            return

        cursor.execute("""
            INSERT INTO sources (source_id, country_code, organization, source_name, endpoint_url,
                                 verification_status, integration_status, license_status)
            VALUES (%s, 'US', 'U.S. Securities and Exchange Commission',
                    'SEC Form N-MFP individual filing - portfolio securities and class NAV',
                    'https://www.sec.gov/edgar/search/', 'Usable Fund Data Confirmed', 'Integrated', 'Unknown')
            ON CONFLICT (source_id) DO UPDATE SET source_name = EXCLUDED.source_name,
                endpoint_url = EXCLUDED.endpoint_url
        """, (SOURCE_ID,))

        if holdings:
            cursor.execute("""
                CREATE TEMP TABLE stg_nmfp_holdings (
                    fund_id integer, reporting_date date, source_url text, holding_index integer,
                    security_name text, cusip text, isin text, market_value numeric,
                    portfolio_weight numeric, accession_number text, data_source text
                ) ON COMMIT DROP
            """)
            with cursor.copy("COPY stg_nmfp_holdings FROM STDIN") as copy:
                for row in holdings:
                    copy.write_row(row)
            cursor.execute("""
                INSERT INTO portfolio_holdings
                    (fund_id, reporting_date, source_url, holding_index, security_name, cusip, isin,
                     market_value, portfolio_weight, accession_number, data_source)
                SELECT fund_id, reporting_date, source_url, holding_index, security_name, cusip, isin,
                       market_value, portfolio_weight, accession_number, data_source
                FROM stg_nmfp_holdings
                ORDER BY fund_id, reporting_date, holding_index
                ON CONFLICT (fund_id, reporting_date, holding_index) DO NOTHING
            """)
            stats["holding_rows_written"] = cursor.rowcount

        if navs:
            cursor.execute("""
                CREATE TEMP TABLE stg_nmfp_nav (
                    fund_id integer, valuation_date date, nav numeric, currency text,
                    source_id text, source_url text, ohlc_basis text
                ) ON COMMIT DROP
            """)
            with cursor.copy("COPY stg_nmfp_nav FROM STDIN") as copy:
                for row in navs:
                    copy.write_row(row)
            cursor.execute("""
                INSERT INTO nav_observations
                    (fund_id, valuation_date, nav, currency, source_id, source_url, ohlc_basis)
                SELECT fund_id, valuation_date, nav, currency, source_id, source_url, ohlc_basis
                FROM stg_nmfp_nav
                ON CONFLICT (fund_id, valuation_date, currency) DO NOTHING
            """)
            stats["nav_rows_written"] = cursor.rowcount

        connection.commit()
        print(json.dumps({"holding_rows_written": stats.get("holding_rows_written", 0),
                          "nav_rows_written": stats.get("nav_rows_written", 0)}, indent=2))


if __name__ == "__main__":
    main()
