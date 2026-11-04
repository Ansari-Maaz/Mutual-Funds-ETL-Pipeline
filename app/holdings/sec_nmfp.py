"""Import class-level money-market NAV observations from SEC Form N-MFP."""
from __future__ import annotations

import json
import re
import urllib.error
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
import xml.etree.ElementTree as ET
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db.session import SessionLocal
from app.holdings.sec_nport import _request
from app.models.schema import Fund, FundProfileSnapshot, Source

SOURCE_ID = "sec_nmfp_money_market"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/primary_doc.xml"
SUPPORTED_FORMS = {"N-MFP", "N-MFP/A", "N-MFP3", "N-MFP3/A"}
DATASET_URL = "https://www.sec.gov/data-research/sec-markets-data/dera-form-n-mfp-data-sets"


def _tag(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _text(parent: ET.Element, name: str) -> str | None:
    for element in parent.iter():
        if _tag(element) == name and element.text and element.text.strip():
            return element.text.strip()
    return None


def _amount(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(Decimal(value.strip()))
    except (InvalidOperation, ValueError):
        return None


def parse_nmfp_xml(payload: bytes, *, accession_number: str, source_url: str) -> dict[str, Any] | None:
    """Extract disclosed class NAV values without inferring missing currency."""
    root = ET.fromstring(payload)
    series_id = _text(root, "seriesId")
    report_period = _text(root, "repPdEnd") or _text(root, "reportPeriodEndDate")
    report_date = date.fromisoformat(report_period[:10]) if report_period else None
    classes: list[dict[str, Any]] = []
    for node in root.iter():
        if _tag(node) != "classLevelInfo":
            continue
        class_id = _text(node, "classesId") or _text(node, "classId")
        if not class_id:
            continue
        observations = []
        for item in node.iter():
            if _tag(item) != "dailyNetAssetValuePerShareClass":
                continue
            value = _amount(_text(item, "dailyNetAssetValuePerShareClass"))
            raw_date = _text(item, "dailyNetAssetValuePerShareDateClass")
            if not value or not raw_date:
                continue
            try:
                valuation_date = date.fromisoformat(raw_date[:10])
            except ValueError:
                continue
            observations.append({"valuation_date": valuation_date.isoformat(), "nav": value,
                                 "currency": None, "value_type": "SEC-reported class NAV per share"})
        if observations:
            classes.append({
                "class_id": class_id,
                "class_name": _text(node, "classFullName"),
                "class_net_assets": _amount(_text(node, "netAssetsOfClass")),
                "shares_outstanding": _amount(_text(node, "numberOfSharesOutstanding")),
                "observations": sorted(observations, key=lambda row: row["valuation_date"]),
            })
    if not classes:
        return None
    return {"series_id": series_id, "report_date": report_date.isoformat() if report_date else None,
            "accession_number": accession_number, "source_url": source_url, "classes": classes}


def _recent_filings(cik: str, *, lookback_days: int) -> list[dict[str, str]]:
    recent = json.loads(_request(SUBMISSIONS_URL.format(cik=cik)).decode("utf-8")).get("filings", {}).get("recent", {})
    cutoff = date.today() - timedelta(days=lookback_days)
    output = []
    forms = recent.get("form", [])
    for index, form in enumerate(forms):
        if form not in SUPPORTED_FORMS:
            continue
        filed = (recent.get("filingDate") or [""])[index]
        accession = (recent.get("accessionNumber") or [""])[index]
        primary = (recent.get("primaryDocument") or [""])[index]
        if not filed or date.fromisoformat(filed) < cutoff or not accession or not primary:
            continue
        output.append({"filed": filed, "accession": accession, "primary": primary})
    return sorted(output, key=lambda row: (row["filed"], row["accession"]), reverse=True)


def sync_sec_nmfp(fund_ids: set[int] | None = None, *, lookback_days: int = 450) -> dict[str, Any]:
    """Fetch recent money-market filings for mapped SEC fund classes and save NAV snapshots.

    Form N-MFP is limited to money market funds. Currency is intentionally left
    null because the published daily class NAV table does not itself carry a
    currency field; these records therefore remain separate from the canonical
    NAV endpoint until currency is independently verified.
    """
    if lookback_days < 1:
        raise ValueError("lookback_days must be at least 1")
    with SessionLocal() as session:
        query = select(Fund.id, Fund.source_fund_id, Fund.sec_cik, Fund.sec_series_id).where(
            Fund.domicile_country == "US", Fund.source_id == "sec_open_end_fund_classes",
            Fund.sec_cik.is_not(None))
        if fund_ids:
            query = query.where(Fund.id.in_(fund_ids))
        funds = session.execute(query).all()
        source = {"source_id": SOURCE_ID, "country_code": "US",
                  "organization": "U.S. Securities and Exchange Commission",
                  "source_name": "Form N-MFP money-market fund filings",
                  "endpoint_url": DATASET_URL, "verification_status": "Usable Fund Data Confirmed",
                  "integration_status": "Integrated", "license_status": "Unknown"}
        session.execute(insert(Source).values(**source).on_conflict_do_update(
            index_elements=[Source.source_id], set_={key: value for key, value in source.items() if key != "source_id"}))
        funds_by_cik: dict[str, list[tuple[int, str, str | None]]] = {}
        for fund_id, class_id, cik, series_id in funds:
            funds_by_cik.setdefault(re.sub(r"\D", "", cik).zfill(10), []).append((fund_id, class_id, series_id))
        retrieved = loaded = matched_filings = aum_snapshots = fetch_errors = parse_errors = 0
        for cik, mapped_funds in funds_by_cik.items():
            class_ids = {class_id for _, class_id, _ in mapped_funds}
            expected_series = {series for _, _, series in mapped_funds if series}
            for filing in _recent_filings(cik, lookback_days=lookback_days):
                accession_nodash = filing["accession"].replace("-", "")
                # The submissions API's primaryDocument for N-MFP3 points to
                # SEC's XSL-rendered XHTML (`xslN-MFP3_X01/...`), not the
                # machine-readable filing. The raw EDGAR XML is primary_doc.xml.
                url = ARCHIVE_URL.format(cik=str(int(cik)), accession_nodash=accession_nodash)
                try:
                    payload = _request(url)
                except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as error:
                    fetch_errors += 1
                    print(f"SEC N-MFP fetch failed for CIK {cik}, accession {filing['accession']}: {type(error).__name__}: {error}", flush=True)
                    continue
                retrieved += 1
                try:
                    report = parse_nmfp_xml(payload, accession_number=filing["accession"], source_url=url)
                except ET.ParseError as error:
                    parse_errors += 1
                    print(f"SEC N-MFP parse failed for CIK {cik}, accession {filing['accession']}: {error}", flush=True)
                    continue
                if not report or (report["series_id"] and expected_series
                                  and report["series_id"] not in expected_series):
                    continue
                matched_filings += 1
                report_classes = {row["class_id"]: row for row in report["classes"]}
                report_date = date.fromisoformat(report["report_date"]) if report["report_date"] else None
                for fund_id, class_id, _ in mapped_funds:
                    class_record = report_classes.get(class_id)
                    if not class_record:
                        continue
                    snapshot = {"fund_id": fund_id, "source_id": SOURCE_ID, "dataset": "nav_history",
                        "source_report_date": report_date,
                        "snapshot_key": f"nmfp:{filing['accession']}:{class_id}",
                        "payload": {"scope": "share_class", "class_id": class_id,
                            "class_name": class_record["class_name"], "currency": None,
                            "currency_status": "not provided in the SEC class NAV table",
                            "observations": class_record["observations"],
                            "class_net_assets": class_record["class_net_assets"],
                            "shares_outstanding": class_record["shares_outstanding"],
                            "accession_number": filing["accession"]}, "source_url": url}
                    statement = insert(FundProfileSnapshot).values(**snapshot)
                    session.execute(statement.on_conflict_do_update(
                        constraint="uq_fund_profile_source_snapshot", set_={
                            "source_report_date": statement.excluded.source_report_date,
                            "payload": statement.excluded.payload, "source_url": statement.excluded.source_url}))
                    loaded += 1
                    if report_date and class_record["class_net_assets"] is not None:
                        aum_snapshot = {"fund_id": fund_id, "source_id": SOURCE_ID,
                            "dataset": "aum_history", "source_report_date": report_date,
                            "snapshot_key": f"nmfp-aum:{filing['accession']}:{class_id}",
                            "payload": {"scope": "share_class", "class_id": class_id,
                                "class_name": class_record["class_name"],
                                "reported_value": class_record["class_net_assets"],
                                "currency": None,
                                "currency_status": "not independently verified from the class value field",
                                "shares_outstanding": class_record["shares_outstanding"],
                                "accession_number": filing["accession"]}, "source_url": url}
                        aum_statement = insert(FundProfileSnapshot).values(**aum_snapshot)
                        session.execute(aum_statement.on_conflict_do_update(
                            constraint="uq_fund_profile_source_snapshot", set_={
                                "source_report_date": aum_statement.excluded.source_report_date,
                                "payload": aum_statement.excluded.payload,
                                "source_url": aum_statement.excluded.source_url}))
                        aum_snapshots += 1
        session.commit()
        return {"fund_classes_examined": len(funds), "filings_retrieved": retrieved,
            "matched_filings": matched_filings, "nav_history_snapshots_loaded": loaded,
                "aum_history_snapshots_loaded": aum_snapshots, "filing_fetch_errors": fetch_errors,
                "filing_parse_errors": parse_errors,
            "dataset_scope": "Money market funds only", "currency_assigned": False,
            "source_url": DATASET_URL}
