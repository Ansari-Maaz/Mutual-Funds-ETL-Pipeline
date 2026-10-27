"""Fetch and load official SEC N-PORT holdings for SEC-linked US fund classes."""
from __future__ import annotations

import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
import gzip
import json
import re
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET
import zlib
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import timeout_seconds, user_agent
from app.db.session import SessionLocal
from app.models.schema import Fund, PortfolioHolding

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "united_states"
MASTER = RAW / "sec_series_classes.csv"
FILINGS_CACHE = RAW / "nport_filings"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
MAX_FILING_AGE_DAYS = 450
SEC_REQUEST_INTERVAL = 0.12
_SEC_REQUEST_LOCK = threading.Lock()
_NEXT_SEC_REQUEST_AT = 0.0


def _tag(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _text(parent: ET.Element, key: str) -> str | None:
    for element in parent.iter():
        if _tag(element) == key and element.text and element.text.strip():
            return element.text.strip()
    return None


def _decimal(value: str | None) -> Decimal | None:
    if not value or value.strip().casefold() in {"n/a", "na", "none"}:
        return None
    try:
        return Decimal(value.strip())
    except InvalidOperation:
        return None


def parse_nport_xml(payload: bytes, *, accession_number: str, source_url: str) -> dict[str, Any] | None:
    """Parse a single SEC primary N-PORT XML document; never infer missing values."""
    root = ET.fromstring(payload)
    general = next((node for node in root.iter() if _tag(node) == "genInfo"), None)
    if general is None:
        return None
    series_id = _text(general, "seriesId")
    report_date_raw = _text(general, "repPdDate")
    if not series_id or not report_date_raw:
        return None
    report_date = date.fromisoformat(report_date_raw[:10])
    holdings: list[dict[str, Any]] = []
    for index, node in enumerate(e for e in root.iter() if _tag(e) == "invstOrSec"):
        name = _text(node, "name") or _text(node, "issuerName") or _text(node, "title")
        if not name:
            continue
        cusip = _text(node, "cusip")
        ticker = None
        isin = None
        for child in node.iter():
            tag = _tag(child).casefold()
            if tag == "ticker":
                ticker = child.attrib.get("value") or (child.text.strip() if child.text else None)
                if ticker:
                    break
        for child in node.iter():
            if _tag(child).casefold() == "isin":
                isin = child.attrib.get("value") or (child.text.strip() if child.text else None)
                if isin:
                    break
        percentage = _decimal(_text(node, "pctVal"))
        holdings.append({
            "holding_index": index,
            "security_name": name[:500],
            "ticker": ticker[:50] if ticker else None,
            "isin": isin[:12] if isin else None,
            "cusip": cusip[:12] if cusip else None,
            "quantity": _decimal(_text(node, "balance")),
            "market_value": _decimal(_text(node, "valUSD")),
            "market_value_currency": "USD" if _decimal(_text(node, "valUSD")) is not None else None,
            # Form N-PORT requests percentages as percentages, not decimals.
            "portfolio_weight": percentage,
        })
    return {"series_id": series_id, "report_date": report_date,
            "accession_number": accession_number, "source_url": source_url,
            "holdings": holdings}


def _request(url: str) -> bytes:
    # Share a single fair-access limiter across the bounded worker pool.
    global _NEXT_SEC_REQUEST_AT
    with _SEC_REQUEST_LOCK:
        now = time.monotonic()
        starts_at = max(now, _NEXT_SEC_REQUEST_AT)
        _NEXT_SEC_REQUEST_AT = starts_at + SEC_REQUEST_INTERVAL
    if starts_at > now:
        time.sleep(starts_at - now)
    request = urllib.request.Request(url, headers={"User-Agent": user_agent(), "Accept-Encoding": "gzip, deflate", "Host": "www.sec.gov" if "www.sec.gov" in url else "data.sec.gov"})
    with urllib.request.urlopen(request, timeout=timeout_seconds()) as response:
        payload = response.read()
        encoding = response.headers.get("Content-Encoding", "").casefold()
    # urllib does not decompress HTTP content encodings automatically. SEC may
    # return gzip even when intermediaries omit Content-Encoding, so recognize
    # the gzip signature as well as the response header.
    if encoding == "gzip" or payload.startswith(b"\x1f\x8b"):
        return gzip.decompress(payload)
    if encoding == "deflate":
        try:
            return zlib.decompress(payload)
        except zlib.error:
            return zlib.decompress(payload, -zlib.MAX_WBITS)
    return payload


def _class_maps() -> tuple[dict[str, tuple[str, str]], dict[str, set[tuple[str, str]]]]:
    if not MASTER.exists():
        raise FileNotFoundError(f"SEC series/class master is missing: {MASTER}; run the SEC fund ETL first")
    result: dict[str, tuple[str, str]] = {}
    by_ticker: dict[str, set[tuple[str, str]]] = defaultdict(set)
    with MASTER.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if (row.get("Entity Org Type") or "").strip() != "30":
                continue
            class_id = (row.get("Class ID") or "").strip()
            series_id = (row.get("Series ID") or "").strip()
            cik_raw = re.sub(r"\D", "", row.get("CIK Number") or "")
            if class_id and series_id and cik_raw:
                cik = cik_raw.zfill(10)
                result[class_id] = (series_id, cik)
                ticker = (row.get("Class Ticker") or "").strip().upper()
                if ticker:
                    by_ticker[ticker].add((series_id, cik))
    return result, by_ticker


def _recent_filings(cik: str) -> list[dict[str, str]]:
    payload = json.loads(_request(SUBMISSIONS_URL.format(cik=cik)).decode("utf-8"))
    recent = payload.get("filings", {}).get("recent", {})
    result = []
    cutoff = date.today() - timedelta(days=MAX_FILING_AGE_DAYS)
    for index, form in enumerate(recent.get("form", [])):
        if form not in {"NPORT-P", "NPORT-P/A"}:
            continue
        filed = recent.get("filingDate", [""])[index]
        if not filed or date.fromisoformat(filed) < cutoff:
            continue
        primary = recent.get("primaryDocument", [""])[index]
        accession = recent.get("accessionNumber", [""])[index]
        if accession and primary and primary.lower().endswith((".xml", ".txt")):
            report_date = recent.get("reportDate", [""])[index]
            result.append({"accession": accession, "filed": filed,
                           "report_date": report_date or filed, "primary": primary})
    result.sort(key=lambda item: (item["report_date"], item["filed"], item["accession"]), reverse=True)
    return result


def _download_filing(cik: str, filing: dict[str, str]) -> tuple[dict[str, Any] | None, str]:
    no_dashes = filing["accession"].replace("-", "")
    # The SEC serves many N-PORT primary XML documents through an XSLT HTML
    # rendering. Fetch the filing's complete submission text to obtain the
    # original <XML> payload that parse_nport_xml expects.
    url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{no_dashes}/{filing['accession']}.txt"
    cache = FILINGS_CACHE / cik / f"{no_dashes}-{filing['accession']}.txt"
    if cache.exists():
        payload = cache.read_bytes()
    else:
        payload = _request(url)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(payload)
    try:
        embedded_xml = re.search(rb"<XML>\s*(.*?)\s*</XML>", payload, flags=re.IGNORECASE | re.DOTALL)
        if not embedded_xml:
            return None, filing["filed"]
        return parse_nport_xml(embedded_xml.group(1), accession_number=filing["accession"], source_url=url), filing["filed"]
    except ET.ParseError:
        return None, filing["filed"]


def sync_sec_holdings(fund_ids: set[int] | None = None) -> dict[str, int]:
    """Refresh N-PORT filings in the rolling history window for linked US fund classes.

    ``fund_ids`` optionally limits work to selected local funds, which is useful
    for an initial profile refresh before running the complete US catalog sync.
    """
    if "@" not in user_agent():
        raise RuntimeError("Set USER_AGENT to identify this application and include a monitored contact email before requesting SEC EDGAR data")
    class_map, ticker_map = _class_maps()
    with SessionLocal() as session:
        fund_query = select(Fund.id, Fund.source_id, Fund.source_fund_id, Fund.ticker).where(
            Fund.domicile_country == "US",
            ((Fund.source_id == "sec_open_end_fund_classes") | Fund.fund_type.ilike("%mutual fund%")))
        if fund_ids is not None:
            fund_query = fund_query.where(Fund.id.in_(fund_ids))
        funds = session.execute(fund_query).all()
    by_series: dict[str, list[int]] = defaultdict(list)
    series_cik: dict[str, str] = {}
    unmatched_ids = []
    mapped_funds = []
    for fund_id, source_id, source_fund_id, ticker in funds:
        match = class_map.get(source_fund_id) if source_id == "sec_open_end_fund_classes" else None
        if match is None and ticker:
            matches = ticker_map.get(ticker.strip().upper(), set())
            if len(matches) == 1:
                match = next(iter(matches))
        if not match:
            unmatched_ids.append(fund_id)
            continue
        series_id, cik = match
        by_series[series_id].append(fund_id)
        series_cik[series_id] = cik
        mapped_funds.append({"id": fund_id, "series_id": series_id, "cik": cik})

    with SessionLocal() as session:
        for row in mapped_funds:
            session.execute(update(Fund).where(Fund.id == row["id"]).values(
                sec_series_id=row["series_id"], sec_cik=row["cik"]))
        session.commit()

    series_by_cik: dict[str, set[str]] = defaultdict(set)
    for series_id, cik in series_cik.items():
        series_by_cik[cik].add(series_id)
    def fetch_cik(cik: str, target_series: set[str]) -> dict[str, dict[date, tuple[str, dict[str, Any]]]]:
        found: dict[str, dict[date, tuple[str, dict[str, Any]]]] = defaultdict(dict)
        pending_series = set(target_series)
        for filing in _recent_filings(cik):
            if not pending_series:
                break
            report, filed = _download_filing(cik, filing)
            if report is None or report["series_id"] not in pending_series:
                continue
            series_id = report["series_id"]
            # Filings are sorted newest first. Load the latest report for each
            # mapped series on an initial sync; subsequent runs add newer
            # reporting dates without replacing prior history.
            found[series_id][report["report_date"]] = (filed, report)
            pending_series.remove(series_id)
        return found

    failed_ciks: set[str] = set()
    targets = list(series_by_cik.items())
    now = datetime.now(timezone.utc)
    loaded = unavailable = rows_loaded = 0

    def store_cik(cik: str, target_series: set[str], found: dict[str, dict[date, tuple[str, dict[str, Any]]]]) -> tuple[int, int, int]:
        cik_loaded = cik_unavailable = cik_rows = 0
        with SessionLocal() as session:
            for series_id in target_series:
                fund_ids_for_series = by_series[series_id]
                series_reports = found.get(series_id, {})
                usable = [(report_date, report) for report_date, (_filed, report) in series_reports.items()
                          if report["holdings"]]
                if not usable:
                    session.execute(update(Fund).where(Fund.id.in_(fund_ids_for_series)).values(
                        holdings_status="unavailable", holdings_report_date=None))
                    cik_unavailable += len(fund_ids_for_series)
                    continue
                newest_report_date = max(report_date for report_date, _report in usable)
                for report_date, report in usable:
                    values = []
                    for fund_id in fund_ids_for_series:
                        for holding in report["holdings"]:
                            values.append({**holding, "fund_id": fund_id,
                                "reporting_date": report_date,
                                "accession_number": report["accession_number"],
                                "data_source": "sec_edgar_nport",
                                "source_url": report["source_url"], "retrieved_at": now})
                    table = PortfolioHolding.__table__
                    for offset in range(0, len(values), 400):
                        chunk = values[offset:offset + 400]
                        stmt = pg_insert(table).values(chunk)
                        update_columns = {key: getattr(stmt.excluded, key) for key in chunk[0]
                                          if key not in {"id", "fund_id", "reporting_date", "holding_index"}}
                        session.execute(stmt.on_conflict_do_update(
                            constraint="uq_fund_holding_report_item", set_=update_columns))
                    cik_rows += len(values)
                session.execute(update(Fund).where(Fund.id.in_(fund_ids_for_series)).values(
                    holdings_status="available", holdings_report_date=newest_report_date))
                cik_loaded += len(fund_ids_for_series)
            # Commit by CIK to bound memory and keep completed registrants visible.
            session.commit()
        return cik_loaded, cik_unavailable, cik_rows

    # Keep a small bounded pool: a CIK can contain many series and holdings.
    # The shared request limiter still caps all SEC requests below nine/sec.
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(fetch_cik, cik, target_series): cik for cik, target_series in targets}
        for completed, future in enumerate(as_completed(futures), 1):
            cik = futures.pop(future)
            try:
                found = future.result()
            except Exception as error:
                failed_ciks.add(cik)
                print(f"SEC fetch failed for CIK {cik}: {type(error).__name__}: {error}")
                continue
            try:
                cik_loaded, cik_unavailable, cik_rows = store_cik(cik, series_by_cik[cik], found)
                loaded += cik_loaded
                unavailable += cik_unavailable
                rows_loaded += cik_rows
            except Exception as error:
                failed_ciks.add(cik)
                print(f"SEC data load failed for CIK {cik}: {type(error).__name__}: {error}")
            del found
            if completed % 25 == 0 or completed == len(targets):
                print(f"SEC registrants processed: {completed}/{len(targets)}")

    with SessionLocal() as session:
        for fund_id in unmatched_ids:
            session.execute(update(Fund).where(Fund.id == fund_id).values(holdings_status="unavailable", holdings_report_date=None))
            unavailable += 1
        session.commit()
    return {"funds_checked": len(funds), "funds_with_holdings": loaded,
            "funds_unavailable": unavailable, "holding_rows_loaded": rows_loaded,
            "registrants_with_fetch_errors": len(failed_ciks)}
