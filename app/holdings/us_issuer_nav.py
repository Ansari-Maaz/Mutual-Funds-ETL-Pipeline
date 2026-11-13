"""Official issuer NAV adapters for US funds.

FundFlow already stores market-price closes from provider feeds. This module
adds NAV observations read directly from the fund issuer's own public pages or
downloads, for the fund families whose sites publish structured data. Every
value keeps the issuer page URL, the reported valuation date, and a distinct
source_id so market-price rows are never presented as issuer NAV.

Covered adapters
----------------
* ``us_vanguard_fund_products``: Vanguard product pages embed a JSON object
  with the daily NAV and one month of dated NAV history.
* ``us_ssga_spdr_navs``: State Street publishes a daily NAV history workbook
  per SPDR fund ticker.
* ``us_capital_group_fund_pages``: Capital Group / American Funds product
  pages embed the daily NAV per share and its as-of date in page JSON.

Issuers whose sites require authentication, block automated access, or render
NAV only through client-side JavaScript are listed in
``docs/US_OFFICIAL_SOURCES.md`` together with the exact failure observed; they
are intentionally not scraped so the pipeline never fabricates values.
"""
from __future__ import annotations

import html
import io
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from openpyxl import load_workbook
from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import timeout_seconds, user_agent
from app.db.session import SessionLocal
from app.models.schema import Fund, NavObservation, Source

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 " \
             "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
VANGUARD_MUTUAL_URL = "https://investor.vanguard.com/investment-products/mutual-funds/profile/{ticker}"
VANGUARD_ETF_URL = "https://investor.vanguard.com/investment-products/etfs/profile/{ticker}"
SSGA_NAV_URL = ("https://www.ssga.com/us/en/intermediary/library-content/products/"
                "fund-data/etfs/us/navhist-us-en-{ticker}.xlsx")
CAPITAL_GROUP_URL = "https://www.capitalgroup.com/individual/investments/fund/{ticker}"

VANGUARD_SOURCE = "us_vanguard_fund_products"
SSGA_SOURCE = "us_ssga_spdr_navs"
CAPITAL_GROUP_SOURCE = "us_capital_group_fund_pages"

# Capital Group's American Funds trusts. Patterns are deliberately explicit so
# the adapter never requests unrelated issuers that merely share a name word.
CAPITAL_GROUP_PROVIDERS = (
    "%American Funds%", "%AMCAP%", "AMERICAN BALANCED FUND%",
    "AMERICAN MUTUAL FUND%", "AMERICAN HIGH INCOME TRUST%",
    "CAPITAL WORLD%", "EUROPACIFIC%", "GROWTH FUND OF AMERICA%",
    "INCOME FUND OF AMERICA%", "SMALLCAP WORLD%", "WASHINGTON MUTUAL%",
    "NEW ECONOMY FUND%", "NEW PERSPECTIVE FUND%", "FUNDAMENTAL INVESTORS%",
    "INVESTMENT COMPANY OF AMERICA%", "CAPITAL INCOME BUILDER%",
)

CAPITAL_GROUP_PRICE = re.compile(
    r'priceDistribution\\?"?\s*:\s*\{\\?"?price\\?"?\s*:\s*\{\\?"?asOfDate\\?"?\s*:\s*\\?"'
    r'(?P<date>[0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4})\\?"\s*,\s*\\?"?period\\?"?\s*:\s*\\?"daily\\?"'
    r'\s*,\s*\\?"?nav\\?"?\s*:\s*\\?"(?P<nav>[0-9.,]+)')


def _capital_group_parse(payload: bytes, *, ticker: str) -> dict[str, Any] | None:
    """Read the issuer's daily NAV from an American Funds product page."""
    text = payload.decode("utf-8", errors="replace")
    match = CAPITAL_GROUP_PRICE.search(text)
    if not match:
        return None
    nav = _decimal(match.group("nav"))
    if nav is None:
        return None
    raw_date = match.group("date")
    parsed = None
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            parsed = datetime.strptime(raw_date, fmt).date()
            break
        except ValueError:
            continue
    if parsed is None:
        return None
    return {"ticker": ticker.upper(), "nav_rows": [{"valuation_date": parsed, "nav": nav}]}



def _decimal(text: Any) -> Decimal | None:
    if text is None:
        return None
    cleaned = str(text).replace("$", "").replace(",", "").strip()
    if not cleaned or cleaned.upper() in {"N/A", "NA", "-", "--"}:
        return None
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None
    return value if value > 0 else None


def _request(url: str) -> tuple[bytes, str]:
    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*",
        "Accept-Language": "en-US,en;q=0.9",
    })
    with urllib.request.urlopen(request, timeout=max(30.0, timeout_seconds())) as response:
        return response.read(), response.geturl()


def _ensure_sources(session) -> None:
    values = [
        {"source_id": VANGUARD_SOURCE, "country_code": "US",
         "organization": "The Vanguard Group",
         "source_name": "Vanguard official fund product pages",
         "endpoint_url": VANGUARD_MUTUAL_URL.format(ticker="VFIAX"),
         "verification_status": "Usable Fund Data Confirmed",
         "integration_status": "Integrated", "license_status": "Unknown"},
        {"source_id": SSGA_SOURCE, "country_code": "US",
         "organization": "State Street Global Advisors",
         "source_name": "SPDR official fund NAV history workbooks",
         "endpoint_url": SSGA_NAV_URL.format(ticker="SPY"),
         "verification_status": "Usable Fund Data Confirmed",
         "integration_status": "Integrated", "license_status": "Unknown"},
        {"source_id": CAPITAL_GROUP_SOURCE, "country_code": "US",
         "organization": "Capital Group / American Funds",
         "source_name": "Capital Group official fund product pages",
         "endpoint_url": CAPITAL_GROUP_URL.format(ticker="agthx"),
         "verification_status": "Usable Fund Data Confirmed",
         "integration_status": "Integrated", "license_status": "Unknown"},
    ]
    for value in values:
        statement = pg_insert(Source).values(**value)
        session.execute(statement.on_conflict_do_update(
            index_elements=[Source.source_id],
            set_={key: item for key, item in value.items() if key != "source_id"}))


def _parse_vanguard_new_format(text: str, *, ticker: str) -> dict[str, Any] | None:
    """Parse the newer Vanguard page format using <script id="fundProfileData" ...>."""
    match = re.search(r'<script[^>]+id="fundProfileData"[^>]*>(\{.*?\})</script>', text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
    except (json.JSONDecodeError, ValueError):
        return None
    fund = data.get("fundProfile") or {}
    page_ticker = str(fund.get("ticker") or "").strip().upper()
    if page_ticker and page_ticker != ticker.upper():
        raise ValueError(f"Vanguard page ticker mismatch: requested {ticker}, page reported {page_ticker}")

    # Extract single-point NAV from navData if present, else no nav_rows
    nav_data = data.get("navData") or {}
    rows: list[dict[str, Any]] = []
    nav_price = _decimal(str(nav_data.get("navPrice") or fund.get("navPrice") or ""))
    nav_date_raw = str(nav_data.get("navAsOfDate") or nav_data.get("asOfDate") or "").strip()
    if nav_price and nav_date_raw:
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y", "%Y-%m-%d"):
            try:
                val_date = datetime.strptime(nav_date_raw[:19] if "T" in nav_date_raw else nav_date_raw, fmt).date()
                rows.append({"valuation_date": val_date, "nav": nav_price})
                break
            except ValueError:
                continue

    inception_raw = str(fund.get("inceptionDate") or "").strip()
    inception_date = None
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            inception_date = datetime.strptime(inception_raw[:19] if "T" in inception_raw else inception_raw, fmt).date()
            break
        except (ValueError, AttributeError):
            continue

    return {
        "ticker": ticker.upper(),
        "name": fund.get("longName") or fund.get("shortName"),
        "nav_rows": rows,
        "reported_nav": nav_price,
        "reported_nav_date": nav_date_raw or None,
        "inception_date": inception_date,
        "expense_ratio": _decimal(str(fund.get("expenseRatio") or "")),
        "category": (fund.get("equityInvestmentStyleName") or
                     (fund.get("fundCategory") or {}).get("mid", {}).get("name") or None),
        "profile": fund,
        "_format": "new",
    }


def parse_vanguard_profile(payload: bytes, *, ticker: str) -> dict[str, Any]:
    """Parse the issuer-published NAV block embedded in a Vanguard page.

    Handles two formats:
    - Legacy: data-vgn-funds-profile='...' attribute with full historical NAV
    - New (2025+): <script id="fundProfileData" type="application/json"> with fund metadata
    """
    text = payload.decode("utf-8", errors="replace")

    # Try new format first (2025+ Vanguard pages)
    new_result = _parse_vanguard_new_format(text, ticker=ticker)
    if new_result is not None:
        return new_result

    # Fall back to legacy format
    match = re.search(r"data-vgn-funds-profile='([^']+)'", text)
    if not match:
        raise ValueError("Vanguard page does not contain data-vgn-funds-profile or fundProfileData")
    profile = json.loads(html.unescape(match.group(1)))
    overview = profile.get("overview") if isinstance(profile.get("overview"), dict) else {}
    historical = ((profile.get("price") or {}).get("historicalPrice")
                  if isinstance(profile.get("price"), dict) else None) or {}
    reported_ticker = str(historical.get("ticker") or overview.get("iovTickerSymbol") or "").split(".")[0].upper()
    if reported_ticker and reported_ticker != ticker.upper():
        raise ValueError(f"Vanguard page ticker mismatch: requested {ticker}, page reported {reported_ticker}")
    rows: list[dict[str, Any]] = []
    for period in ("1m", "3m", "6m", "1y"):
        block = historical.get(period)
        if not isinstance(block, dict):
            continue
        for item in block.get("nav") or []:
            if not isinstance(item, dict):
                continue
            nav = _decimal(item.get("price"))
            raw_date = str(item.get("asOfDate") or "").strip()
            if nav is None or not raw_date:
                continue
            try:
                valuation_date = datetime.strptime(raw_date, "%m/%d/%Y").date()
            except ValueError:
                continue
            rows.append({"valuation_date": valuation_date, "nav": nav})
    deduped = {row["valuation_date"]: row for row in rows}
    return {"ticker": ticker.upper(), "name": overview.get("fundName"),
            "nav_rows": [deduped[key] for key in sorted(deduped)],
            "reported_nav": _decimal(str(overview.get("navPrice") or "")),
            "reported_nav_date": overview.get("navPriceAsOfDate"),
            "profile": overview,
            "_format": "legacy"}


def _read_ssga_workbook(payload: bytes, *, ticker: str, history_days: int) -> list[dict[str, Any]]:
    workbook = load_workbook(io.BytesIO(payload), read_only=True, data_only=True)
    sheet = workbook[workbook.sheetnames[0]]
    rows = []
    file_ticker = None
    header_seen = False
    for values in sheet.iter_rows(values_only=True):
        cells = list(values)
        if not header_seen:
            label = str(cells[0] or "").strip().lower() if cells else ""
            if label.startswith("ticker") and len(cells) > 1:
                file_ticker = str(cells[1] or "").strip().upper()
            if label == "date":
                header_seen = True
            continue
        raw_date, nav = (cells[0], cells[1]) if len(cells) > 1 else (None, None)
        value = _decimal(nav)
        if value is None or raw_date is None:
            continue
        if isinstance(raw_date, datetime):
            valuation_date = raw_date.date()
        elif isinstance(raw_date, date):
            valuation_date = raw_date
        else:
            try:
                valuation_date = datetime.strptime(str(raw_date).strip(), "%d-%b-%Y").date()
            except ValueError:
                continue
        rows.append({"valuation_date": valuation_date, "nav": value,
                     "shares_outstanding": _decimal(cells[2]) if len(cells) > 2 else None,
                     "net_assets": _decimal(cells[3]) if len(cells) > 3 else None})
    if file_ticker and file_ticker != ticker.upper():
        raise ValueError(f"SSGA workbook ticker mismatch: requested {ticker}, file reported {file_ticker}")
    rows.sort(key=lambda row: row["valuation_date"], reverse=True)
    return rows[:max(1, history_days)]


def _store_navs(source_id: str, ticker: str, source_url: str,
                rows: Iterable[dict[str, Any]]) -> int:
    prepared = [{
        "fund_id": fund_id, "valuation_date": row["valuation_date"], "nav": row["nav"],
        "currency": "USD", "source_id": source_id, "source_url": source_url,
        "ohlc_basis": "single_daily_nav",
    } for fund_id, row in rows]
    if not prepared:
        return 0
    with SessionLocal() as session:
        statement = pg_insert(NavObservation.__table__).values(prepared)
        statement = statement.on_conflict_do_update(
            constraint="uq_nav_fund_date_currency",
            set_={"nav": statement.excluded.nav, "source_id": statement.excluded.source_id,
                  "source_url": statement.excluded.source_url,
                  "ohlc_basis": statement.excluded.ohlc_basis,
                  "retrieved_at": datetime.now(timezone.utc)})
        session.execute(statement)
        session.commit()
    return len(prepared)


def _candidate_funds(source: str, *, only_missing: bool, providers: tuple[str, ...]) -> list[Fund]:
    with SessionLocal() as session:
        query = select(Fund).where(
            Fund.domicile_country == "US", Fund.ticker.is_not(None), Fund.ticker != "",
            or_(*[Fund.provider.ilike(pattern) for pattern in providers]),
        ).order_by(Fund.ticker)
        funds = session.scalars(query).all()
        if only_missing:
            covered = set(session.execute(
                select(NavObservation.fund_id).distinct()).scalars().all())
            funds = [fund for fund in funds if fund.id not in covered]
        return funds


def _throttle(seconds: float) -> None:
    if seconds and seconds > 0:
        time.sleep(seconds)


def sync_vanguard_navs(*, only_missing: bool = True, limit: int | None = None,
                       delay_seconds: float = 0.35) -> dict[str, Any]:
    funds = [fund for fund in _candidate_funds(
        VANGUARD_SOURCE, only_missing=only_missing, providers=("%Vanguard%",))
        if (fund.ticker or "").strip()]
    if limit is not None:
        funds = funds[:limit]
    result = {"source_id": VANGUARD_SOURCE, "funds_requested": len(funds),
              "funds_with_nav": 0, "nav_rows": 0, "errors": []}
    with SessionLocal() as session:
        _ensure_sources(session)
        session.commit()
    metadata_updated = 0
    for fund in funds:
        ticker = (fund.ticker or "").strip().upper()
        last_error = None
        for template in (VANGUARD_MUTUAL_URL, VANGUARD_ETF_URL):
            url = template.format(ticker=ticker.lower())
            try:
                payload, final_url = _request(url)
                parsed = parse_vanguard_profile(payload, ticker=ticker)
                # Store NAV rows if present (new format may only have single-point)
                if parsed["nav_rows"]:
                    nav_batch = [{"fund_id": fund.id, **row} for row in parsed["nav_rows"]]
                    result["nav_rows"] += _store_navs(VANGUARD_SOURCE, ticker, final_url, nav_batch)
                    result["funds_with_nav"] += 1
                # Backfill metadata from new-format pages (inception_date, expense_ratio, category)
                meta_updates: dict[str, Any] = {}
                if parsed.get("inception_date") and fund.inception_date is None:
                    meta_updates["inception_date"] = parsed["inception_date"]
                if parsed.get("category") and not (fund.category or "").strip():
                    meta_updates["category"] = parsed["category"]
                if meta_updates:
                    with SessionLocal() as meta_session:
                        from sqlalchemy import update as _update
                        meta_session.execute(
                            _update(Fund).where(Fund.id == fund.id).values(**meta_updates)
                        )
                        meta_session.commit()
                    metadata_updated += 1
                last_error = None
                break
            except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as error:
                last_error = f"{type(error).__name__}: {error}"
        if last_error:
            result["errors"].append({"ticker": ticker, "error": last_error})
        _throttle(delay_seconds)
    result["metadata_updated"] = metadata_updated
    return result


def sync_ssga_navs(*, only_missing: bool = True, limit: int | None = None,
                   history_days: int = 30, delay_seconds: float = 0.35) -> dict[str, Any]:
    funds = [fund for fund in _candidate_funds(
        SSGA_SOURCE, only_missing=only_missing,
        providers=("%SPDR%", "%State Street%"))
        if (fund.ticker or "").strip()]
    if limit is not None:
        funds = funds[:limit]
    result = {"source_id": SSGA_SOURCE, "funds_requested": len(funds),
              "funds_with_nav": 0, "nav_rows": 0, "errors": []}
    with SessionLocal() as session:
        _ensure_sources(session)
        session.commit()
    for fund in funds:
        ticker = (fund.ticker or "").strip().upper()
        url = SSGA_NAV_URL.format(ticker=ticker.lower())
        try:
            payload, final_url = _request(url)
            rows = _read_ssga_workbook(payload, ticker=ticker, history_days=history_days)
            if not rows:
                raise ValueError("workbook contains no dated NAV rows")
            result["nav_rows"] += _store_navs(
                SSGA_SOURCE, ticker, final_url,
                [{"fund_id": fund.id, **row} for row in rows])
            result["funds_with_nav"] += 1
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError) as error:
            result["errors"].append({"ticker": ticker, "error": f"{type(error).__name__}: {error}"})
        _throttle(delay_seconds)
    return result


def sync_capital_group_navs(*, only_missing: bool = True, limit: int | None = None,
                            delay_seconds: float = 0.35) -> dict[str, Any]:
    """Read daily NAV from Capital Group / American Funds product pages."""
    funds = [fund for fund in _candidate_funds(
        CAPITAL_GROUP_SOURCE, only_missing=only_missing,
        providers=CAPITAL_GROUP_PROVIDERS)
        if (fund.ticker or "").strip()]
    if limit is not None:
        funds = funds[:limit]
    result = {"source_id": CAPITAL_GROUP_SOURCE, "funds_requested": len(funds),
              "funds_with_nav": 0, "nav_rows": 0, "errors": []}
    with SessionLocal() as session:
        _ensure_sources(session)
        session.commit()
    for fund in funds:
        ticker = (fund.ticker or "").strip().upper()
        url = CAPITAL_GROUP_URL.format(ticker=ticker.lower())
        try:
            payload, final_url = _request(url)
            parsed = _capital_group_parse(payload, ticker=ticker)
            if not parsed:
                raise ValueError("page did not expose a daily NAV value")
            result["nav_rows"] += _store_navs(
                CAPITAL_GROUP_SOURCE, ticker, final_url,
                [{"fund_id": fund.id, **row} for row in parsed["nav_rows"]])
            result["funds_with_nav"] += 1
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError) as error:
            result["errors"].append({"ticker": ticker, "error": f"{type(error).__name__}: {error}"})
        _throttle(delay_seconds)
    return result


ADAPTERS = {
    "vanguard": sync_vanguard_navs,
    "ssga": sync_ssga_navs,
    "capital_group": sync_capital_group_navs,
}


def sync_official_us_navs(sources: Iterable[str] | None = None, *,
                          only_missing: bool = True, limit: int | None = None) -> dict[str, Any]:
    """Run the selected official issuer NAV adapters."""
    selected = list(sources or ADAPTERS)
    result = {"generated_at": datetime.now(timezone.utc).isoformat(), "adapters": {}}
    for name in selected:
        if name not in ADAPTERS:
            raise ValueError(f"Unknown official NAV adapter: {name}")
        result["adapters"][name] = ADAPTERS[name](only_missing=only_missing, limit=limit)
    return result
