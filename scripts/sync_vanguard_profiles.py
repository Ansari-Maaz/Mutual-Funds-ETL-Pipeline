"""Fetch structured official profile fields from Vanguard product pages.

This first provider adapter deliberately supports explicit ticker selection. It
does not infer that a ticker is a unique share class until the local DB confirms
exactly one US record for it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
from datetime import date, datetime, timezone
from decimal import Decimal
from html.parser import HTMLParser
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.config import timeout_seconds, user_agent
from app.db.session import SessionLocal
from app.models.schema import Fund, FundProfileSnapshot, Source

SOURCE_ID = "us_vanguard_fund_products"
SOURCE_URL = "https://advisors.vanguard.com/investments/products/{ticker}/"


class _StructuredDataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._capture = False
        self._parts: list[str] = []
        self.json_ld: list[Any] = []
        self.initial_fund_data: dict[str, Any] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "script" and (values.get("type") or "").casefold() == "application/ld+json":
            self._capture = True
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._capture:
            try:
                self.json_ld.append(json.loads("".join(self._parts)))
            except (ValueError, TypeError):
                pass
            self._capture = False


def _flatten(value: Any):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _flatten(item)
    elif isinstance(value, list):
        for item in value:
            yield from _flatten(item)


def _window_json(html: str, variable: str) -> dict[str, Any]:
    """Read one provider-published JSON object embedded in the product page."""
    marker = f"window.{variable} = "
    start = html.find(marker)
    if start < 0:
        return {}
    try:
        value, _ = json.JSONDecoder().raw_decode(html[start + len(marker):])
    except (ValueError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def parse_vanguard_product_page(html: str, *, ticker: str, page_url: str) -> dict[str, Any]:
    """Parse only provider-published schema.org FinancialProduct fields."""
    parser = _StructuredDataParser()
    parser.feed(html)
    products = [item for root in parser.json_ld for item in _flatten(root)
                if "FinancialProduct" in (item.get("@type") or [])
                or item.get("@type") == "FinancialProduct"]
    if len(products) != 1:
        raise ValueError(f"Expected one Vanguard FinancialProduct JSON-LD record, found {len(products)}")
    product = products[0]
    organizations = {item.get("@id"): item.get("name") for root in parser.json_ld for item in _flatten(root)
                     if item.get("@type") == "Organization" and item.get("@id") and item.get("name")}
    identifiers = {str(item.get("propertyID", "")).casefold(): item.get("value")
                   for item in product.get("identifier", []) if isinstance(item, dict)}
    properties = {str(item.get("name", "")).casefold(): item.get("value")
                  for item in product.get("additionalProperty", []) if isinstance(item, dict)}
    actual_ticker = str(identifiers.get("ticker") or "").strip().upper()
    if actual_ticker != ticker.upper():
        raise ValueError(f"Vanguard page ticker mismatch: requested {ticker}, page returned {actual_ticker or 'none'}")

    expense_text = product.get("feesAndCommissionsSpecification") or ""
    expense_match = re.search(r"expense\s+ratio\s*:\s*([0-9.]+\s*%)\s*(?:\(as of\s*(\d{4}-\d{2}-\d{2})\))?", expense_text, re.I)
    expense = None
    if expense_match:
        expense = {"reported_value": expense_match.group(1).replace(" ", ""),
                   "measure": "expense_ratio", "basis": "provider-displayed; ratio type not stated",
                   "effective_date": expense_match.group(2)}

    benchmark = properties.get("benchmark")
    inception = properties.get("inception date") or product.get("dateIssued")
    if inception:
        inception = date.fromisoformat(str(inception)[:10]).isoformat()
    assets_text = properties.get("net assets")
    assets = None
    if assets_text:
        match = re.fullmatch(r"USD\s+([0-9,.]+)\s*([KMBT])?\s*\(as of\s*(\d{4}-\d{2}-\d{2})\)", str(assets_text), re.I)
        if match:
            scale = {None: Decimal(1), "K": Decimal(1_000), "M": Decimal(1_000_000),
                     "B": Decimal(1_000_000_000), "T": Decimal(1_000_000_000_000)}[match.group(2).upper() if match.group(2) else None]
            assets = {"reported_value": str(assets_text),
                      "displayed_amount_usd": str(Decimal(match.group(1).replace(",", "")) * scale),
                      "precision": "rounded provider display; not an exact accounting value",
                      "effective_date": match.group(3),
                      "scope": "Ticker product page; JSON-LD does not further specify aggregate versus share-class scope"}

    # The product page also embeds separate provider-owned values with their
    # own effective dates. Keep their publication labels and raw JSON types.
    initial = _window_json(html, "__INITIAL_FUND_DATA__")
    fee_data = _window_json(html, "__FEES_AND_EXPENSE__")
    managed_assets = _window_json(html, "__MANAGED_ASSETS__")
    hero_stats = _window_json(html, "__HERO_STATS__")
    provider_inception = initial.get("inceptionDate") or initial.get("inception_date")
    if provider_inception:
        inception = date.fromisoformat(str(provider_inception)[:10]).isoformat()

    adjusted_expense = fee_data.get("adjustedExpenseRatio")
    if isinstance(adjusted_expense, dict) and adjusted_expense.get("value") not in (None, ""):
        expense = {
            "reported_value": str(adjusted_expense["value"]),
            "unit": "percent",
            "measure": "adjustedExpenseRatio",
            "basis": "Vanguard product page label; preserve as provider-reported",
            "effective_date": adjusted_expense.get("effectiveDate"),
        }

    fund_net_assets = managed_assets.get("fundNetAssetsData")
    if isinstance(fund_net_assets, dict) and fund_net_assets.get("amount") is not None:
        amount = Decimal(str(fund_net_assets["amount"]))
        effective = fund_net_assets.get("effectiveDate")
        assets = {
            "reported_value": str(fund_net_assets["amount"]),
            "amount": str(amount),
            "currency": "USD",
            "precision": "provider-reported numeric amount",
            "effective_date": effective,
            "scope": "fundNetAssetsData; Vanguard product-page field; no share-class scope assumption",
        }

    performance = {}
    for label in ("ytdReturn", "oneYearReturn"):
        stat = hero_stats.get(label)
        if isinstance(stat, dict) and stat.get("value") is not None and stat.get("effectiveDate"):
            performance[label] = {"value": stat["value"], "effective_date": stat["effectiveDate"],
                                  "unit": "percent", "source_label": label}
    risk = {}
    standard_deviation = hero_stats.get("threeYearStandardDeviation")
    if isinstance(standard_deviation, dict) and standard_deviation.get("value") is not None:
        risk["three_year_standard_deviation"] = {
            "value": standard_deviation["value"], "effective_date": standard_deviation.get("effectiveDate"),
            "unit": "percent", "source_label": "threeYearStandardDeviation",
        }

    return {
        "ticker": actual_ticker,
        "name": product.get("name"),
        "provider": ((product.get("provider") or {}).get("name")
                     or organizations.get((product.get("provider") or {}).get("@id")))
                    if isinstance(product.get("provider"), dict) else None,
        "official_url": product.get("url") or page_url,
        "category": product.get("category"),
        "objective": product.get("description"),
        "cusip": identifiers.get("cusip"),
        "benchmark": benchmark,
        "management_style": properties.get("management style"),
        "distribution_schedule": properties.get("distribution schedule"),
        "inception_date": inception,
        "holdings_count": properties.get("holdings count"),
        "expense_ratio": expense,
        "net_assets": assets,
        "performance": performance,
        "risk": risk,
        "dividend_yield": hero_stats.get("dividendYield"),
        "provider_fund_id": initial.get("portId"),
        "provider_instrument_flags": {key: initial[key] for key in
            ("isETF", "isMutualFund", "isIndex", "isMoneyMarket", "isFixedIncome") if key in initial},
    }


def _fetch_page(ticker: str) -> tuple[str, str]:
    url = SOURCE_URL.format(ticker=ticker.lower())
    request = urllib.request.Request(url, headers={"User-Agent": user_agent(), "Accept": "text/html"})
    with urllib.request.urlopen(request, timeout=timeout_seconds()) as response:
        if response.status != 200:
            raise RuntimeError(f"Vanguard returned HTTP {response.status}")
        return response.read().decode("utf-8", "replace"), response.geturl()


def sync_ticker(ticker: str) -> dict[str, Any]:
    ticker = ticker.strip().upper()
    html, page_url = _fetch_page(ticker)
    record = parse_vanguard_product_page(html, ticker=ticker, page_url=page_url)
    with SessionLocal() as session:
        funds = session.scalars(select(Fund).where(Fund.domicile_country == "US", Fund.ticker == ticker)).all()
        if len(funds) != 1:
            raise ValueError(f"Expected exactly one US fund with ticker {ticker}; found {len(funds)}")
        fund = funds[0]
        source = {"source_id": SOURCE_ID, "country_code": "US", "organization": "The Vanguard Group",
                  "source_name": "Vanguard official fund product pages", "endpoint_url": "https://advisors.vanguard.com/investments/mutual-funds",
                  "verification_status": "Usable Fund Data Confirmed", "integration_status": "Integrated",
                  "license_status": "Unknown"}
        session.execute(insert(Source).values(**source).on_conflict_do_update(
            index_elements=[Source.source_id], set_={key: value for key, value in source.items() if key != "source_id"}))
        # Update only direct, unambiguous master fields; never turn the sponsor
        # into a named portfolio manager.
        fund.provider = record["provider"] or fund.provider
        category = record["category"]
        fund.category = (category[-1] if isinstance(category, list) and category else category) or fund.category
        fund.inception_date = date.fromisoformat(record["inception_date"]) if record["inception_date"] else fund.inception_date
        fund.official_url = record["official_url"]
        retrieved_at = datetime.now(timezone.utc)
        snapshots = []
        summary = {key: record.get(key) for key in ("ticker", "name", "provider", "official_url", "category",
            "objective", "cusip", "benchmark", "management_style", "distribution_schedule", "inception_date",
            "holdings_count", "dividend_yield", "provider_fund_id", "provider_instrument_flags")
            if record.get(key) is not None}
        if summary:
            snapshots.append(("summary", None, summary))
        if record["expense_ratio"]:
            effective = record["expense_ratio"].get("effective_date")
            snapshots.append(("expense_ratio_history", date.fromisoformat(effective) if effective else None,
                              record["expense_ratio"]))
        if record["net_assets"] and record["net_assets"].get("effective_date"):
            snapshots.append(("aum_history", date.fromisoformat(record["net_assets"]["effective_date"]), record["net_assets"]))
            fund.net_assets = Decimal(record["net_assets"]["amount"])
            fund.net_assets_date = date.fromisoformat(record["net_assets"]["effective_date"])
        for metric, value in record["performance"].items():
            snapshots.append(("performance", date.fromisoformat(value["effective_date"]),
                              {"metric": metric, **value, "methodology": "Provider-reported value; not independently recalculated"}))
        for metric, value in record["risk"].items():
            effective = value.get("effective_date")
            snapshots.append(("risk", date.fromisoformat(effective) if effective else None,
                              {"metric": metric, **value, "methodology": "Provider-reported value; not independently recalculated"}))
        for dataset, as_of, payload in snapshots:
            identity = f"{SOURCE_ID}:{dataset}:{as_of.isoformat() if as_of else 'current'}"
            key = hashlib.sha256(identity.encode()).hexdigest()
            statement = insert(FundProfileSnapshot).values(fund_id=fund.id, source_id=SOURCE_ID, dataset=dataset,
                source_report_date=as_of, snapshot_key=key, payload=payload, source_url=page_url, retrieved_at=retrieved_at)
            session.execute(statement.on_conflict_do_update(constraint="uq_fund_profile_source_snapshot", set_={
                "source_report_date": statement.excluded.source_report_date,
                "payload": statement.excluded.payload,
                "source_url": statement.excluded.source_url,
                "retrieved_at": statement.excluded.retrieved_at,
            }))
        session.commit()
        return {"fund_id": fund.id, "ticker": ticker, "official_url": page_url,
                "snapshot_datasets": [item[0] for item in snapshots],
                "fields": record}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", action="append", required=True, help="Exact ticker; repeat to select multiple Vanguard funds")
    args = parser.parse_args()
    for ticker in args.ticker:
        print(json.dumps(sync_ticker(ticker), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
