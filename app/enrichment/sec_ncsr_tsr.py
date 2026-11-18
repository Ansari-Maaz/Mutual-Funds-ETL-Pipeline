"""Import official SEC N-CSR/N-CSRS Tailored Shareholder Report (TSR) XBRL.

Every open-end fund files an annual (N-CSR) and semi-annual (N-CSRS) report.
Since 2024 those reports carry a machine-readable TSR XBRL instance whose facts
are tagged per share class with ``oef:ClassAxis`` (a ``C000xxxxxx`` class id).
The instance is an official SEC filing, so it is a primary source for:

* the class trading symbol;
* the class performance-inception date (young classes only);
* net assets reported for the series and repeated per class;
* net expense ratio, holdings count and portfolio turnover;
* average annual total returns for 1-, 5- and 10-year periods;
* sector allocation percentages and expense-example amounts.

The local ``funds`` table stores one row per SEC class (``source_fund_id`` is
the ``C000xxxxxx`` id), which matches the TSR class axis exactly. We fill only
empty ticker, inception and net-asset fields and keep every parsed value in a
versioned profile snapshot with filing accession and source URL provenance.

The importer caches submissions, filing indexes and XBRL instances under
``data/raw/united_states/ncsr_tsr`` so a repeat run is offline and idempotent.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import xml.etree.ElementTree as ET
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.session import SessionLocal
from app.holdings.sec_nport import _request
from app.models.schema import Fund, FundProfileSnapshot, Source

SOURCE_ID = "sec_ncsr_tsr"
DATASET_PAGE = "https://www.sec.gov/edgar/search/#/q=%22tailored%20shareholder%20report%22"
ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/united_states/ncsr_tsr"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
FILING_INDEX_URL = ("https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/index.json")
FILING_FILE_URL = ("https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{name}")

TSR_FORMS = {"N-CSR", "N-CSRS"}
CLASS_ID = re.compile(r"C\d{9}")
SERIES_ID = re.compile(r"S\d{9}")

# Scalar facts read from the class context. Namespaces change yearly, so only
# the local tag name is matched.
SCALAR_FACTS = {
    "TradingSymbol",
    "ClassName",
    "FundName",
    "SecurityExchangeName",
    "AssetsNet",
    "ExpenseRatioPct",
    "PerfInceptionDate",
    "HoldingsCount",
    "InvestmentCompanyPortfolioTurnover",
}
LIST_FACTS = {"AvgAnnlRtrPct", "PctOfNav", "ExpensesPaidAmt", "AccmVal", "AdvisoryFeesPaidAmt"}
DOCUMENT_FACTS = {
    "EntityRegistrantName",
    "EntityCentralIndexKey",
    "EntityInvCompanyType",
    "DocumentType",
    "DocumentPeriodEndDate",
    "AmendmentFlag",
}
INDEX_DIMENSIONS = ("IndexAxis", "IndustrySectorAxis")


def _tag(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _text(element: ET.Element) -> str | None:
    value = (element.text or "").strip()
    return value or None


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    text = str(value).replace(",", "").replace("$", "").strip()
    if not text or text.upper() in {"N/A", "NA", "NONE", "-", "--"}:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return None


def _submit_cik(cik: str) -> str:
    digits = re.sub(r"\D", "", str(cik))
    return digits.zfill(10)


def _cache_path(*parts: str) -> Path:
    path = RAW.joinpath(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _fetch_cached(url: str, path: Path, *, refresh: bool, binary: bool = True) -> bytes:
    if path.exists() and not refresh:
        return path.read_bytes()
    payload = _request(url)
    path.write_bytes(payload)
    return payload


def _submissions(cik: str, *, refresh: bool) -> dict[str, Any]:
    path = _cache_path("submissions", f"CIK{cik}.json")
    payload = _fetch_cached(SUBMISSIONS_URL.format(cik=cik), path, refresh=refresh)
    return json.loads(payload)


def _filing_rows(submissions: dict[str, Any]) -> list[dict[str, str]]:
    filings = submissions.get("filings") or {}
    recent = filings.get("recent") or {}
    columns = ("accessionNumber", "filingDate", "reportDate", "form", "primaryDocument")
    lengths = [len(recent.get(column) or []) for column in columns]
    rows: list[dict[str, str]] = []
    for index in range(min(lengths) if lengths else 0):
        rows.append({column: (recent.get(column) or [""])[index] for column in columns})
    return rows


def _candidate_filings(submissions: dict[str, Any], *, since_days: int,
                       max_filings: int) -> list[dict[str, str]]:
    cutoff = date.today() - timedelta(days=max(1, since_days))
    candidates: list[dict[str, str]] = []
    for row in _filing_rows(submissions):
        form = (row.get("form") or "").strip().upper()
        if form not in TSR_FORMS:
            continue
        filed = _date(row.get("filingDate"))
        if filed is None or filed < cutoff:
            continue
        if not row.get("accessionNumber"):
            continue
        candidates.append(row)
    candidates.sort(key=lambda row: row.get("filingDate") or "", reverse=True)
    return candidates[:max_filings]


def _instance_name(index: dict[str, Any]) -> tuple[str, int] | None:
    """Pick the XBRL instance document from an EDGAR filing index."""
    preferred: list[tuple[str, int]] = []
    others: list[tuple[str, int]] = []
    for item in (index.get("directory") or {}).get("item") or []:
        name = str(item.get("name") or "")
        lower = name.casefold()
        if not lower.endswith(".xml"):
            continue
        if any(lower.endswith(suffix) for suffix in ("_cal.xml", "_def.xml", "_lab.xml", "_pre.xml")):
            continue
        if lower in {"filingsummary.xml", "metalinks.json"}:
            continue
        try:
            size = int(item.get("size") or 0)
        except (TypeError, ValueError):
            size = 0
        if lower.endswith("_htm.xml"):
            preferred.append((name, size))
        else:
            others.append((name, size))
    if preferred:
        return max(preferred, key=lambda item: item[1])
    if others:
        return max(others, key=lambda item: item[1])
    return None


def _filing_index(cik: str, accession: str, *, refresh: bool) -> dict[str, Any]:
    short = accession.replace("-", "")
    path = _cache_path("filings", accession, "index.json")
    payload = _fetch_cached(FILING_INDEX_URL.format(cik=int(cik), accession=short),
                            path, refresh=refresh)
    return json.loads(payload)


def _instance_bytes(cik: str, accession: str, name: str, *, refresh: bool) -> bytes:
    short = accession.replace("-", "")
    path = _cache_path("filings", accession, name)
    return _fetch_cached(FILING_FILE_URL.format(cik=int(cik), accession=short, name=name),
                         path, refresh=refresh)


def _contexts(root: ET.Element) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for context in root.iter():
        if _tag(context) != "context":
            continue
        class_id = series_id = None
        dimensions: list[tuple[str, str]] = []
        for member in context.iter():
            if _tag(member) != "explicitMember":
                continue
            dimension = member.get("dimension") or ""
            value = (member.text or "").strip()
            dimensions.append((dimension, value))
            if "ClassAxis" in dimension:
                match = CLASS_ID.search(value)
                class_id = match.group(0) if match else None
            elif "LegalEntityAxis" in dimension:
                match = SERIES_ID.search(value)
                series_id = match.group(0) if match else None
        start = end = instant = None
        for node in context.iter():
            name = _tag(node)
            if name == "startDate":
                start = _date(_text(node))
            elif name == "endDate":
                end = _date(_text(node))
            elif name == "instant":
                instant = _date(_text(node))
        result[context.get("id") or ""] = {
            "class_id": class_id, "series_id": series_id, "dimensions": dimensions,
            "start": start, "end": end, "instant": instant,
        }
    return result


def _return_years(start: date | None, end: date | None) -> int | None:
    if start is None or end is None:
        return None
    years = round((end - start).days / 365.25)
    return years if 0 < years <= 50 else None


def parse_tsr_instance(payload: bytes, *, accession: str, filing_date: date | None,
                       form: str, source_url: str, instance_url: str) -> dict[str, Any] | None:
    """Parse a TSR XBRL instance into per-class records.

    The parser never invents values. It reads only facts attached to a
    ``oef:ClassAxis`` context and keeps the filed context period alongside each
    value so callers can distinguish 1/5/10-year returns from index comparisons.
    """
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        return None
    if _tag(root) != "xbrl":
        return None

    contexts = _contexts(root)
    document: dict[str, Any] = {}
    classes: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "returns": [], "sector_allocation": [], "expense_examples": []})

    for element in root.iter():
        name = _tag(element)
        context = contexts.get(element.get("contextRef") or "")
        if context is None:
            continue
        value = _text(element)
        if value is None:
            continue
        class_id = context.get("class_id")
        if not class_id:
            if name in DOCUMENT_FACTS:
                document.setdefault(name, value)
            continue
        record = classes[class_id]
        record["class_id"] = class_id
        if context.get("series_id"):
            record["series_id"] = context["series_id"]
        dimensions = context.get("dimensions") or []
        has_index_dimension = any(
            any(axis in dimension for axis in INDEX_DIMENSIONS)
            for dimension, _ in dimensions)

        if name in SCALAR_FACTS:
            record.setdefault(name, value)
            continue
        if name not in LIST_FACTS:
            continue

        if name == "PctOfNav":
            sector = next((value for dimension, value in dimensions
                           if "IndustrySectorAxis" in dimension), None)
            if sector:
                label = _sector_name(sector)
                if not _sector_is_valid(label):
                    continue
                weight = _decimal(value)
                record["sector_allocation"].append({
                    "sector": label,
                    "raw_sector": sector.split(":")[-1],
                    "pct_of_nav": value,
                    "weight_pct": str(weight * 100) if weight is not None else None,
                    "report_date": context["instant"].isoformat() if context.get("instant") else None,
                    "accession_number": accession,
                    "form": form,
                    "source_url": source_url,
                })
            continue
        if name == "AvgAnnlRtrPct":
            if has_index_dimension:
                continue
            load_basis = next((value for dimension, value in dimensions
                               if "SalesLoadAxis" in dimension), None)
            if load_basis and "without" not in load_basis.casefold():
                continue
            record["returns"].append({
                "start_date": context["start"].isoformat() if context.get("start") else None,
                "end_date": context["end"].isoformat() if context.get("end") else None,
                "years": _return_years(context.get("start"), context.get("end")),
                "average_annual_return_fraction": value,
                "load_basis": "without_sales_load" if load_basis else "as_reported",
                "accession_number": accession,
                "form": form,
                "source_url": source_url,
            })
            continue
        record["expense_examples"].append({
            "measure": name,
            "value": value,
            "start_date": context["start"].isoformat() if context.get("start") else None,
            "end_date": context["end"].isoformat() if context.get("end") else None,
            "accession_number": accession,
            "form": form,
            "source_url": source_url,
        })

    if not classes:
        return None
    for record in classes.values():
        # Keep a stable, readable shape and dedupe repeated facts.
        record["returns"] = _dedupe_returns(record["returns"])
        record["sector_allocation"] = _dedupe(record["sector_allocation"], ("sector",))
        record["expense_examples"] = _dedupe(
            record["expense_examples"], ("measure", "start_date", "end_date"))
    return {"accession_number": accession, "filing_date": filing_date,
            "form": form, "source_url": source_url, "instance_url": instance_url,
            "document": document, "classes": dict(classes)}


def _dedupe(rows: list[dict[str, Any]], keys: Iterable[str]) -> list[dict[str, Any]]:
    seen: dict[tuple, dict[str, Any]] = {}
    for row in rows:
        key = tuple(row.get(field) for field in keys)
        if key not in seen:
            seen[key] = row
    return list(seen.values())


def _dedupe_returns(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse the load and no-load duplicate rows for the same period.

    A no-load class files both an ``as_reported`` and a
    ``without_sales_load`` fact for the same period. Keep the explicit
    no-load value because it is the one comparable across classes.
    """
    chosen: dict[tuple, dict[str, Any]] = {}
    for row in rows:
        key = (row.get("start_date"), row.get("end_date"))
        current = chosen.get(key)
        if current is None or (row.get("load_basis") == "without_sales_load"
                               and current.get("load_basis") != "without_sales_load"):
            chosen[key] = row
    return sorted(chosen.values(),
                  key=lambda row: (row.get("years") is None, row.get("years") or 0))


def _sector_name(value: str) -> str:
    name = value.split(":")[-1].replace("Member", "")
    # XBRL industry members are packaged as "Sector<Name>Sector" or
    # "<Name>Sector"; the wrapper words are taxonomy noise, not labels.
    changed = True
    while changed and name:
        changed = False
        for prefix in ("Sector", "Industry"):
            if name.startswith(prefix) and len(name) > len(prefix):
                name = name[len(prefix):]
                changed = True
        if name.endswith("Sector") and len(name) > len("Sector"):
            name = name[: -len("Sector")]
            changed = True
    # Split CamelCase into words but keep acronyms ("REITs" stays "REITs").
    name = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name)
    name = re.sub(r"^([A-Z]{2,})(?=[A-Z][a-z]{2})", r"\1 ", name)
    return name.strip() or value


def _sector_is_valid(name: str) -> bool:
    """Reject benchmark rows and axis members that are not industry sectors."""
    lowered = name.casefold()
    if not name or len(name) > 60 or re.search(r"\d", name):
        return False
    if lowered in {"total", "other"} or lowered.startswith("bench"):
        return False
    # Filers add their own allocation buckets to the axis ("Other Sectors",
    # "Cash and Cash Equivalents Sector Weighting", "Bond Equity Sector
    # Municipals"). No published sector name contains these words.
    if "sector" in lowered or "weighting" in lowered:
        return False
    if lowered.endswith("allocation") or "minus" in lowered:
        return False
    return True


def _local_classes(ciks: set[str] | None, *, only_gaps: bool) -> dict[str, list[tuple[int, str]]]:
    statement = select(Fund.id, Fund.sec_cik, Fund.source_fund_id).where(
        Fund.domicile_country == "US", Fund.sec_cik.is_not(None),
        Fund.source_fund_id.like("C%"))
    if only_gaps:
        statement = statement.where(or_(
            Fund.ticker.is_(None), Fund.ticker == "",
            Fund.inception_date.is_(None), Fund.net_assets.is_(None)))
    with SessionLocal() as session:
        rows = session.execute(statement).all()
    grouped: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for fund_id, cik, class_id in rows:
        normalized = _submit_cik(cik)
        if ciks and normalized not in ciks:
            continue
        grouped[normalized].append((fund_id, class_id))
    return grouped


def _load_filing(cik: str, row: dict[str, str], *, refresh: bool) -> dict[str, Any] | None:
    accession = row["accessionNumber"]
    index = _filing_index(cik, accession, refresh=refresh)
    chosen = _instance_name(index)
    if chosen is None:
        return None
    name, _ = chosen
    payload = _instance_bytes(cik, accession, name, refresh=refresh)
    short = accession.replace("-", "")
    source_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{short}/{accession}-index.html"
    instance_url = FILING_FILE_URL.format(cik=int(cik), accession=short, name=name)
    return parse_tsr_instance(
        payload, accession=accession, filing_date=_date(row.get("filingDate")),
        form=(row.get("form") or "").strip().upper(), source_url=source_url,
        instance_url=instance_url)


def _merge_records(old: dict[str, Any] | None, new: dict[str, Any]) -> dict[str, Any]:
    """Merge two filings for the same class, newest facts winning field by field."""
    if old is None:
        return new
    old_date = old.get("report_date") or date.min
    new_date = new.get("report_date") or date.min
    older, newer = (old, new) if old_date <= new_date else (new, old)
    merged = dict(older)
    for key, value in newer.items():
        if key in {"returns", "sector_allocation", "expense_examples"}:
            continue
        if value not in (None, "", []):
            merged[key] = value
    # Keep every return period from both filings, preferring the newest filing
    # for a period that appears in both.
    merged["returns"] = _dedupe_returns(
        list(newer.get("returns") or []) + list(older.get("returns") or []))
    merged["sector_allocation"] = (newer.get("sector_allocation")
                                   or older.get("sector_allocation") or [])
    merged["expense_examples"] = _dedupe(
        list(newer.get("expense_examples") or []) + list(older.get("expense_examples") or []),
        ("measure", "start_date", "end_date"))
    merged["report_date"] = newer.get("report_date") or older.get("report_date")
    merged["document"] = newer.get("document") or older.get("document")
    return merged


def _process_cik(cik: str, wanted: dict[str, list[tuple[int, str]]], *,
                 since_days: int, max_filings: int, refresh: bool) -> dict[str, Any]:
    result = {"cik": cik, "filings": 0, "classes": {}, "errors": []}
    try:
        submissions = _submissions(cik, refresh=refresh)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError,
            json.JSONDecodeError) as error:
        result["errors"].append({"stage": "submissions", "error": f"{type(error).__name__}: {error}"})
        return result
    candidates = _candidate_filings(submissions, since_days=since_days, max_filings=max_filings)
    wanted_ids = {class_id for _, class_id in wanted[cik]}
    for row in candidates:
        try:
            parsed = _load_filing(cik, row, refresh=refresh)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError,
                json.JSONDecodeError, ET.ParseError) as error:
            result["errors"].append({"stage": "filing", "accession": row.get("accessionNumber"),
                                     "error": f"{type(error).__name__}: {error}"})
            continue
        if not parsed:
            continue
        result["filings"] += 1
        for class_id, record in parsed["classes"].items():
            if class_id not in wanted_ids:
                continue
            record = dict(record)
            record.update({"accession_number": parsed["accession_number"],
                           "filing_date": parsed["filing_date"],
                           "form": parsed["form"], "source_url": parsed["source_url"],
                           "instance_url": parsed["instance_url"],
                           "document": parsed["document"]})
            report_date = _date(record.get("document", {}).get("DocumentPeriodEndDate"))
            record["report_date"] = report_date
            result["classes"][class_id] = _merge_records(
                result["classes"].get(class_id), record)
    return result


def _snapshot_key(class_id: str, report_date: date | None, suffix: str) -> str:
    period = report_date.isoformat() if report_date else "undated"
    return f"{class_id}:{period}:{suffix}"[:64]


def _payload_classes(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "class_id": record.get("class_id"),
        "series_id": record.get("series_id"),
        "fund_name": record.get("FundName"),
        "class_name": record.get("ClassName"),
        "ticker": record.get("TradingSymbol"),
        "exchange": record.get("SecurityExchangeName"),
        "net_assets": record.get("AssetsNet"),
        "net_assets_scope": "series-level net assets repeated on each class context",
        "expense_ratio_pct_fraction": record.get("ExpenseRatioPct"),
        "holdings_count": record.get("HoldingsCount"),
        "portfolio_turnover_pct": record.get("InvestmentCompanyPortfolioTurnover"),
        "performance_inception_date": record.get("PerfInceptionDate"),
        "returns": record.get("returns") or [],
        "sector_allocation": record.get("sector_allocation") or [],
        "expense_examples": record.get("expense_examples") or [],
        "document": record.get("document") or {},
        "report_date": record["report_date"].isoformat() if record.get("report_date") else None,
        "filing_date": record["filing_date"].isoformat() if record.get("filing_date") else None,
        "form": record.get("form"),
        "accession_number": record.get("accession_number"),
        "instance_url": record.get("instance_url"),
        "source_url": record.get("source_url"),
    }


def _current_values(fund_ids: set[int]) -> dict[int, dict[str, Any]]:
    if not fund_ids:
        return {}
    with SessionLocal() as session:
        rows = session.execute(select(
            Fund.id, Fund.ticker, Fund.inception_date, Fund.net_assets
        ).where(Fund.id.in_(fund_ids))).all()
    return {row[0]: {"ticker": row[1], "inception_date": row[2], "net_assets": row[3]}
            for row in rows}


def _ensure_source(session) -> None:
    source = {
        "source_id": SOURCE_ID, "country_code": "US",
        "organization": "U.S. Securities and Exchange Commission",
        "source_name": "N-CSR/N-CSRS Tailored Shareholder Report XBRL",
        "endpoint_url": DATASET_PAGE,
        "verification_status": "Usable Fund Data Confirmed",
        "integration_status": "Integrated", "license_status": "Public domain",
    }
    session.execute(pg_insert(Source).values(**source).on_conflict_do_update(
        index_elements=[Source.source_id],
        set_={key: value for key, value in source.items() if key != "source_id"}))


def _write_batch(local: dict[str, list[tuple[int, str]]],
                 processed: dict[str, dict[str, Any]], result: dict[str, Any], *,
                 dry_run: bool, update_profiles: bool) -> None:
    """Build and persist snapshots and fund updates for one CIK batch."""
    fund_by_key = {(cik, class_id): fund_id
                   for cik, classes in local.items() for fund_id, class_id in classes}
    snapshots: list[dict[str, Any]] = []
    fund_updates: dict[int, dict[str, Any]] = {}
    for cik, entry in processed.items():
        for class_id, record in (entry.get("classes") or {}).items():
            fund_id = fund_by_key.get((cik, class_id))
            if fund_id is None:
                continue
            result["classes_matched"] += 1
            report_date = record.get("report_date")
            payload = _payload_classes(record)
            snapshots.append({
                "fund_id": fund_id, "source_id": SOURCE_ID, "dataset": "ncsr_tsr_class",
                "source_report_date": report_date,
                "snapshot_key": _snapshot_key(class_id, report_date, "ncsr_tsr_class"),
                "payload": payload, "source_url": record.get("source_url"),
            })
            expense = _decimal(record.get("ExpenseRatioPct"))
            if expense is not None:
                snapshots.append({
                    "fund_id": fund_id, "source_id": SOURCE_ID,
                    "dataset": "expense_ratio_history", "source_report_date": report_date,
                    "snapshot_key": _snapshot_key(class_id, report_date, "expense_ratio"),
                    "payload": {
                        "measure": "net_expense_ratio", "reported_value": str(expense),
                        "unit": "fraction", "percent_value": str(expense * 100),
                        "effective_date": report_date.isoformat() if report_date else None,
                        "basis": "net expense ratio as a fraction of net assets reported in the tailored shareholder report",
                        "accession_number": record.get("accession_number"),
                        "source_url": record.get("source_url"),
                    },
                    "source_url": record.get("source_url"),
                })
            turnover = _decimal(record.get("InvestmentCompanyPortfolioTurnover"))
            holdings_count = _decimal(record.get("HoldingsCount"))
            summary_payload = {
                "symbol": record.get("TradingSymbol"),
                "ticker": record.get("TradingSymbol"),
                "currency": "USD",
                "share_class_inception_date": record.get("PerfInceptionDate") or None,
                "expense_ratio_net": str(expense) if expense is not None else None,
                "expense_ratio_basis": "fraction of net assets",
                "turnover_rate": str(turnover) if turnover is not None else None,
                "turnover_rate_basis": "fraction of average net assets",
                "holdings_count": str(holdings_count) if holdings_count is not None else None,
                "net_assets": record.get("AssetsNet"),
                "net_assets_scope": "series-level net assets repeated on each class context",
                "fund_name": record.get("FundName"),
                "class_name": record.get("ClassName"),
                "report_date": report_date.isoformat() if report_date else None,
                "form": record.get("form"),
                "accession_number": record.get("accession_number"),
                "source_url": record.get("source_url"),
            }
            if any(summary_payload.get(key) not in (None, "") for key in
                   ("symbol", "expense_ratio_net", "turnover_rate", "holdings_count")):
                snapshots.append({
                    "fund_id": fund_id, "source_id": SOURCE_ID, "dataset": "summary",
                    "source_report_date": report_date,
                    "snapshot_key": _snapshot_key(class_id, report_date, "summary"),
                    "payload": summary_payload, "source_url": record.get("source_url"),
                })
            if payload.get("sector_allocation"):
                snapshots.append({
                    "fund_id": fund_id, "source_id": SOURCE_ID,
                    "dataset": "sector_allocation", "source_report_date": report_date,
                    "snapshot_key": _snapshot_key(class_id, report_date, "sector_allocation"),
                    "payload": {
                        "allocation": payload["sector_allocation"],
                        "basis": "percentage of net assets by industry sector as reported in the tailored shareholder report",
                        "effective_date": report_date.isoformat() if report_date else None,
                        "accession_number": record.get("accession_number"),
                        "source_url": record.get("source_url"),
                    },
                    "source_url": record.get("source_url"),
                })
            for item in payload.get("returns") or []:
                years = item.get("years")
                if years is None:
                    continue
                period_end = _date(item.get("end_date")) or report_date
                metric = {1: "oneYearReturn", 3: "threeYearReturn",
                          5: "fiveYearReturn", 10: "tenYearReturn"}.get(
                              years, f"average_annual_return_{years}y")
                snapshots.append({
                    "fund_id": fund_id, "source_id": SOURCE_ID,
                    "dataset": "performance", "source_report_date": period_end,
                    "snapshot_key": _snapshot_key(
                        class_id, period_end, f"average_annual_return_{years}y"),
                    "payload": {
                        "metric": metric,
                        "value": item.get("average_annual_return_fraction"),
                        "unit": "fraction",
                        "period_years": years,
                        "start_date": item.get("start_date"),
                        "end_date": item.get("end_date"),
                        "load_basis": item.get("load_basis"),
                        "effective_date": item.get("end_date"),
                        "accession_number": item.get("accession_number"),
                        "form": item.get("form"),
                        "source_url": item.get("source_url"),
                    },
                    "source_url": item.get("source_url"),
                })

            if update_profiles:
                updates = fund_updates.setdefault(fund_id, {})
                ticker = (record.get("TradingSymbol") or "").strip().upper()
                if ticker:
                    updates.setdefault("ticker", ticker[:30])
                inception = _date(record.get("PerfInceptionDate"))
                if inception:
                    updates.setdefault("inception_date", inception)
                assets = _decimal(record.get("AssetsNet"))
                if assets is not None:
                    updates.setdefault("net_assets", assets)
                    updates.setdefault("net_assets_date", report_date)
                if not updates.get("legal_name") and record.get("FundName"):
                    updates["legal_name"] = str(record["FundName"])[:500]

    unique: dict[tuple[int, str], dict[str, Any]] = {}
    for row in snapshots:
        unique[(row["fund_id"], row["snapshot_key"])] = row
    if len(unique) != len(snapshots):
        result["snapshot_duplicates"] += len(snapshots) - len(unique)
    snapshots = list(unique.values())
    result["snapshots_written"] += len(snapshots)
    if dry_run:
        current = _current_values(set(fund_updates))
        for fund_id, updates in fund_updates.items():
            fields = current.get(fund_id) or {}
            if not (fields.get("ticker") or "").strip() and updates.get("ticker"):
                result["tickers_filled"] += 1
            if fields.get("inception_date") is None and updates.get("inception_date"):
                result["inceptions_filled"] += 1
            if fields.get("net_assets") is None and updates.get("net_assets") is not None:
                result["net_assets_filled"] += 1
        return

    if not snapshots and not fund_updates:
        return
    with SessionLocal() as session:
        _ensure_source(session)
        table = FundProfileSnapshot.__table__
        for offset in range(0, len(snapshots), 400):
            chunk = snapshots[offset:offset + 400]
            statement = pg_insert(table).values(chunk)
            session.execute(statement.on_conflict_do_update(
                constraint="uq_fund_profile_source_snapshot",
                set_={"dataset": statement.excluded.dataset,
                      "source_report_date": statement.excluded.source_report_date,
                      "payload": statement.excluded.payload,
                      "source_url": statement.excluded.source_url,
                      "retrieved_at": datetime.now().astimezone()}))
        for fund_id, updates in fund_updates.items():
            fund = session.get(Fund, fund_id)
            if fund is None:
                continue
            applied: dict[str, Any] = {}
            if not (fund.ticker or "").strip() and updates.get("ticker"):
                applied["ticker"] = updates["ticker"]
                result["tickers_filled"] += 1
            if fund.inception_date is None and updates.get("inception_date"):
                applied["inception_date"] = updates["inception_date"]
                result["inceptions_filled"] += 1
            if fund.net_assets is None and updates.get("net_assets") is not None:
                applied["net_assets"] = updates["net_assets"]
                applied["net_assets_date"] = updates.get("net_assets_date")
                result["net_assets_filled"] += 1
            if not (fund.legal_name or "").strip() and updates.get("legal_name"):
                applied["legal_name"] = updates["legal_name"]
            if applied:
                session.execute(update(Fund).where(Fund.id == fund_id).values(**applied))
                result["profiles_updated"] += 1
        session.commit()


def sync_sec_ncsr_tsr(*, since_days: int = 420, max_filings: int = 8,
                      limit: int | None = None, ciks: set[str] | None = None,
                      refresh: bool = False, update_profiles: bool = True,
                      only_gaps: bool = False, batch_size: int = 100,
                      dry_run: bool = False, workers: int = 4) -> dict[str, Any]:
    """Import N-CSR/N-CSRS TSR class profiles and fill empty fund fields."""
    normalized_ciks = {_submit_cik(cik) for cik in ciks} if ciks else None
    local = _local_classes(normalized_ciks, only_gaps=only_gaps)
    if limit is not None:
        local = dict(list(local.items())[:max(0, limit)])
    result: dict[str, Any] = {
        "source_id": SOURCE_ID, "ciks_targeted": len(local),
        "ciks_completed": 0, "filings_parsed": 0, "classes_parsed": 0,
        "classes_matched": 0, "profiles_updated": 0, "tickers_filled": 0,
        "inceptions_filled": 0, "net_assets_filled": 0, "snapshots_written": 0,
        "snapshot_duplicates": 0,
        "dry_run": dry_run, "errors": [],
    }
    if not local:
        return result

    items = list(local.items())
    step = max(1, batch_size)
    for start in range(0, len(items), step):
        batch = dict(items[start:start + step])
        processed: dict[str, dict[str, Any]] = {}
        if workers > 1:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {
                    pool.submit(_process_cik, cik, {cik: wanted}, since_days=since_days,
                                max_filings=max_filings, refresh=refresh): cik
                    for cik, wanted in batch.items()
                }
                for future in as_completed(futures):
                    cik = futures[future]
                    try:
                        processed[cik] = future.result()
                    except Exception as error:  # keep one bad filing from stopping the run
                        result["errors"].append({"cik": cik, "stage": "worker",
                                                 "error": f"{type(error).__name__}: {error}"})
        else:
            for cik, wanted in batch.items():
                processed[cik] = _process_cik(cik, {cik: wanted}, since_days=since_days,
                                              max_filings=max_filings, refresh=refresh)

        result["ciks_completed"] += len(processed)
        for entry in processed.values():
            result["filings_parsed"] += entry.get("filings", 0)
            result["classes_parsed"] += len(entry.get("classes") or {})
            for error in entry.get("errors") or []:
                if len(result["errors"]) < 200:
                    result["errors"].append({"cik": entry["cik"], **error})

        _write_batch(batch, processed, result, dry_run=dry_run,
                     update_profiles=update_profiles)
        print(f"[ncsr-tsr] {result['ciks_completed']}/{result['ciks_targeted']} CIKs, "
              f"{result['classes_matched']} classes, {result['snapshots_written']} snapshots",
              file=sys.stderr, flush=True)
    return result
