"""Crawl the AMF GECO per-share NAV API for French funds already loaded from the GECO compartment list.

GECO's back-office JSON (the same service the public GECO site and our list connector use) exposes, without a key:
* ``GET /back-office/funds/compartment/{cmpId}/shares``: share classes (parId, ISIN, currency, distribution policy)
* ``GET /back-office/funds/vlsCouponsAndOst/{parId}?startDate&endDate``: daily NAV, assets under management in
  thousands of the share currency, shares outstanding, coupons (distributions) and corporate actions.
The AMF states no reuse licence for this API; requests are throttled and the crawl is resumable and incremental.
"""
from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import timeout_seconds, user_agent
from app.db.session import SessionLocal
from app.models.schema import Fund, FundProfileSnapshot, NavObservation

BASE = "https://geco.amf-france.org/back-office/funds"
INDEX_URL = "https://geco.amf-france.org/liste-des-produits-d-epargne"
SOURCE_ID = "amf_geco"
EARLIEST = date(1990, 1, 1)


def _headers() -> dict[str, str]:
    return {"User-Agent": user_agent(), "Origin": "https://geco.amf-france.org", "Referer": INDEX_URL,
            "Accept": "application/json"}


def _dec(value: Any) -> Decimal | None:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def parse_nav_rows(document: dict[str, Any], fund_id: int, currency_default: str | None) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Return (nav_observation rows, latest point) from a vlsCouponsAndOst response."""
    rows: dict[tuple[date, str], dict[str, Any]] = {}
    latest: dict[str, Any] | None = None
    for point in document.get("netAssetValueDTO") or []:
        if point.get("cancellation"):
            continue
        nav = _dec(point.get("netAssetValue"))
        raw_date = (point.get("valuationDate") or "")[:10]
        currency = (point.get("quotationCurrency") or currency_default or "").strip()
        if nav is None or not raw_date or len(currency) != 3:
            continue
        valuation = date.fromisoformat(raw_date)
        rows[(valuation, currency)] = {"fund_id": fund_id, "source_id": SOURCE_ID, "source_url": f"{BASE}/vlsCouponsAndOst",
                                       "valuation_date": valuation, "nav": nav, "currency": currency}
        if latest is None or valuation > latest["date"]:
            latest = {"date": valuation, "assets_k": _dec(point.get("assetUnderManagementK") or point.get("assetUnderManagement")),
                      "shares": _dec(point.get("shareNumber")), "currency": currency}
    return list(rows.values()), latest


def _shares(client: httpx.Client, cmp_id: str) -> list[dict[str, Any]]:
    response = client.get(f"{BASE}/compartment/{cmp_id}/shares")
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, list) else []


def _history(client: httpx.Client, par_id: str, start: date, end: date) -> dict[str, Any]:
    response = client.get(f"{BASE}/vlsCouponsAndOst/{par_id}", params={"startDate": start.isoformat(), "endDate": end.isoformat()})
    response.raise_for_status()
    return response.json()


def crawl_geco_nav(*, limit: int | None = None, max_minutes: float | None = None, delay: float = 0.5,
                   only_missing: bool = True) -> dict[str, Any]:
    """Load NAV history for GECO share classes. Funds without any NAV are crawled first; reruns are incremental."""
    deadline = time.monotonic() + max_minutes * 60 if max_minutes else None
    today = date.today()
    stats = {"compartments": 0, "shares_matched": 0, "nav_rows": 0, "funds_with_nav": 0, "errors": 0, "no_nav": 0, "stopped_early": False}
    with SessionLocal() as session:
        last_nav = dict(session.execute(select(NavObservation.fund_id, func.max(NavObservation.valuation_date))
                                        .where(NavObservation.source_id == SOURCE_ID).group_by(NavObservation.fund_id)).all())
        funds = session.execute(select(Fund.id, Fund.source_fund_id, Fund.isin, Fund.currency)
                                .where(Fund.source_id == SOURCE_ID)).all()
    by_compartment: dict[str, list[tuple[int, str | None, str | None]]] = {}
    for fund_id, source_fund_id, isin, currency in funds:
        cmp_id = source_fund_id.split(":", 1)[0]
        by_compartment.setdefault(cmp_id, []).append((fund_id, isin, currency))
    # Compartments with no NAV yet first (new coverage), then the rest oldest-NAV first (incremental refresh).
    def priority(item: tuple[str, list]) -> tuple[int, date]:
        dates = [last_nav[f[0]] for f in item[1] if f[0] in last_nav]
        return (1, min(dates)) if dates else (0, EARLIEST)
    queue = sorted(by_compartment.items(), key=priority)
    if only_missing:
        queue = [item for item in queue if priority(item)[0] == 0]
    if limit:
        queue = queue[:limit]
    with httpx.Client(headers=_headers(), timeout=max(timeout_seconds(), 60), follow_redirects=True) as client:
        for cmp_id, members in queue:
            if deadline and time.monotonic() > deadline:
                stats["stopped_early"] = True
                break
            stats["compartments"] += 1
            try:
                shares = {s.get("isin"): s for s in _shares(client, cmp_id) if s.get("isin") and s.get("parId")}
                time.sleep(delay)
                with SessionLocal() as session:
                    for fund_id, isin, currency in members:
                        share = shares.get(isin)
                        if share is None:
                            continue
                        stats["shares_matched"] += 1
                        start = (last_nav[fund_id] + timedelta(days=1)) if fund_id in last_nav else EARLIEST
                        document = _history(client, share["parId"], start, today)
                        time.sleep(delay)
                        rows, latest = parse_nav_rows(document, fund_id, share.get("parRefDevCode") or currency)
                        if not rows:
                            stats["no_nav"] += 1
                        for offset in range(0, len(rows), 1000):
                            chunk = rows[offset:offset + 1000]
                            stmt = pg_insert(NavObservation.__table__).values(chunk)
                            session.execute(stmt.on_conflict_do_update(constraint="uq_nav_fund_date_currency",
                                set_={"nav": stmt.excluded.nav, "source_url": stmt.excluded.source_url}))
                        values: dict[str, Any] = {}
                        if share.get("parRefDevCode") and not currency:
                            values["currency"] = share["parRefDevCode"]
                        if latest and latest["assets_k"] is not None:
                            values.update(net_assets=latest["assets_k"] * 1000, net_assets_date=latest["date"])
                        if values:
                            session.execute(update(Fund).where(Fund.id == fund_id).values(**values))
                        coupons = document.get("couponDTOS") or []
                        if coupons:
                            payload = {"share_class": share.get("parNom"), "distribution_policy": share.get("parAffctnRevnuLib"),
                                       "coupons": coupons}
                            stmt = pg_insert(FundProfileSnapshot.__table__).values(
                                fund_id=fund_id, source_id=SOURCE_ID, dataset="distributions", source_report_date=None,
                                snapshot_key="geco_coupons", payload=payload, source_url=f"{BASE}/vlsCouponsAndOst",
                                retrieved_at=datetime.now(timezone.utc))
                            session.execute(stmt.on_conflict_do_update(constraint="uq_fund_profile_source_snapshot",
                                set_={"payload": stmt.excluded.payload, "retrieved_at": stmt.excluded.retrieved_at}))
                        if rows:
                            stats["funds_with_nav"] += 1
                            stats["nav_rows"] += len(rows)
                    session.commit()
            except (httpx.HTTPError, json.JSONDecodeError, ValueError):
                stats["errors"] += 1
                time.sleep(delay * 4)
    return stats
