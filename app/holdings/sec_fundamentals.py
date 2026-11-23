"""Official trailing P/E for portfolio holdings.

No official U.S. source publishes forward earnings estimates, so FundFlow never
writes ``forward_pe``.  A trailing P/E *can* be built from two filed facts:

* price per share: N-PORT ``market value / balance`` for the reported position;
* annual EPS: the issuer's SEC XBRL ``EarningsPerShareDiluted`` company concept.

The result is stored on ``holding_metrics`` with the exact EPS period and the
XBRL source URL in ``trailing_pe_basis``.  It is deliberately labelled trailing:
it is not a forecast and it is not a vendor estimate.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import psycopg
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import database_url, timeout_seconds, user_agent
from app.db.session import SessionLocal
from app.models.schema import SecurityFundamental, SecurityIndustry, Source

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/united_states"
CACHE = RAW / "companyconcept"
REPORTS = ROOT / "reports"
SOURCE_ID = "sec_xbrl_eps"
CONCEPT_URL = (
    "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/{taxonomy}/{tag}.json"
)
TAGS = (
    ("us-gaap", "EarningsPerShareDiluted", "diluted"),
    ("us-gaap", "EarningsPerShareBasicAndDiluted", "diluted"),
    ("us-gaap", "EarningsPerShareBasic", "basic"),
    ("ifrs-full", "EarningsPerShareDiluted", "diluted"),
    ("ifrs-full", "EarningsPerShareBasic", "basic"),
)
ANNUAL_FORMS = {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"}
MAX_PE = 1000.0
MIN_PE = 0.1
REQUEST_INTERVAL = 0.12


def _raw_url() -> str:
    return database_url().replace("postgresql+psycopg://", "postgresql://", 1)


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _ensure_source() -> None:
    definition = {
        "source_id": SOURCE_ID, "country_code": "US",
        "organization": "U.S. Securities and Exchange Commission",
        "source_name": "SEC XBRL company facts (annual diluted EPS)",
        "endpoint_url": "https://data.sec.gov/api/xbrl/companyconcept/",
        "verification_status": "Usable Fund Data Confirmed",
        "integration_status": "Integrated", "license_status": "Public domain",
    }
    with SessionLocal() as session:
        statement = pg_insert(Source).values(**definition)
        session.execute(statement.on_conflict_do_update(
            index_elements=[Source.source_id],
            set_={key: value for key, value in definition.items() if key != "source_id"}))
        session.commit()


def _fetch(cik: str, taxonomy: str, tag: str) -> dict[str, Any] | None:
    """Read one company concept, cached on disk so a rerun is network-free."""
    CACHE.mkdir(parents=True, exist_ok=True)
    cache = CACHE / f"CIK{cik}_{taxonomy}_{tag}.json"
    if cache.exists():
        try:
            return json.loads(cache.read_text())
        except json.JSONDecodeError:
            cache.unlink(missing_ok=True)
    url = CONCEPT_URL.format(cik=cik, taxonomy=taxonomy, tag=tag)
    request = urllib.request.Request(
        url, headers={"User-Agent": user_agent(), "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds()) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            cache.write_text("null")
            return None
        raise
    cache.write_text(json.dumps(payload))
    return payload


def annual_eps(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return the newest annual EPS fact from a company-concept payload."""
    if not payload:
        return None
    best: tuple[date, date, dict[str, Any]] | None = None
    for unit, facts in (payload.get("units") or {}).items():
        if "shares" not in unit.lower():
            continue
        for fact in facts:
            if not fact.get("start") or not fact.get("end"):
                continue
            if (fact.get("form") or "") not in ANNUAL_FORMS:
                continue
            try:
                start = date.fromisoformat(fact["start"][:10])
                end = date.fromisoformat(fact["end"][:10])
            except ValueError:
                continue
            if not 340 <= (end - start).days <= 380:
                continue
            value = _decimal(fact.get("val"))
            if value is None:
                continue
            try:
                filed = date.fromisoformat((fact.get("filed") or "1900-01-01")[:10])
            except ValueError:
                filed = date(1900, 1, 1)
            candidate = (end, filed, fact)
            if best is None or candidate[:2] > best[:2]:
                best = candidate
    if best is None:
        return None
    end, filed, fact = best
    return {
        "eps": _decimal(fact.get("val")),
        "period_start": date.fromisoformat(fact["start"][:10]),
        "period_end": end,
        "filed": filed,
        "fiscal_year": fact.get("fy"),
        "unit": next(iter(payload.get("units") or {}), None),
    }


def _resolve_fundamentals(
    tickers: list[str] | None, *, limit: int | None
) -> tuple[list[dict[str, Any]], list[dict[str, str]], dict[str, int]]:
    with SessionLocal() as session:
        query = select(SecurityIndustry.ticker, SecurityIndustry.cik,
                       SecurityIndustry.company_name).where(
            SecurityIndustry.cik.is_not(None), SecurityIndustry.cik != "")
        rows = session.execute(query).all()
    if tickers:
        wanted = {ticker.upper().strip() for ticker in tickers}
        rows = [row for row in rows if row.ticker.upper() in wanted]
    if limit:
        rows = rows[:limit]

    # One company-concept request per CIK, not per share class.
    by_cik: dict[str, list[tuple[str, str | None]]] = {}
    for ticker, cik, name in rows:
        by_cik.setdefault(cik, []).append((ticker, name))

    next_at = [0.0]
    lock = threading.Lock()

    def reserve() -> None:
        with lock:
            now = time.monotonic()
            start = max(now, next_at[0])
            next_at[0] = start + REQUEST_INTERVAL
        wait = start - time.monotonic()
        if wait > 0:
            time.sleep(wait)

    def load(cik: str) -> tuple[str, dict[str, Any] | None, str | None, str | None, str]:
        reserve()
        errors: list[str] = []
        for taxonomy, tag, measure in TAGS:
            try:
                payload = _fetch(cik, taxonomy, tag)
            except Exception as error:  # noqa: BLE001 - continue to next concept
                errors.append(f"{taxonomy}:{tag}: {type(error).__name__}")
                continue
            parsed = annual_eps(payload)
            if parsed and parsed.get("eps") is not None:
                url = CONCEPT_URL.format(cik=cik, taxonomy=taxonomy, tag=tag)
                return cik, parsed, measure, url, "; ".join(errors)
        return cik, None, None, None, "; ".join(errors)

    resolved: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(load, cik) for cik in sorted(by_cik)]
        for future in as_completed(futures):
            cik, parsed, measure, url, error = future.result()
            if error:
                errors.append({"cik": cik, "error": error[:300]})
            if not parsed:
                continue
            for ticker, name in by_cik[cik]:
                resolved.append({
                    "ticker": ticker.upper().strip(), "cik": cik,
                    "company_name": (name or "")[:300] or None,
                    "eps": parsed["eps"], "eps_measure": measure,
                    "eps_period_start": parsed["period_start"],
                    "eps_period_end": parsed["period_end"],
                    "eps_filed": parsed["filed"],
                    "fiscal_year": parsed["fiscal_year"],
                    "source_id": SOURCE_ID, "source_url": url,
                })
    return resolved, errors, {"tickers_requested": len(rows), "ciks_requested": len(by_cik)}


def sync_sec_eps(
    tickers: list[str] | None = None, *, limit: int | None = None,
    refresh: bool = False,
) -> dict[str, Any]:
    """Cache annual diluted EPS from SEC XBRL for every resolved holding ticker."""
    _ensure_source()
    if refresh:
        # Re-read the concepts already on disk by deleting the cache entries.
        for path in CACHE.glob("CIK*.json"):
            path.unlink(missing_ok=True)
    resolved, errors, stats = _resolve_fundamentals(tickers, limit=limit)
    with SessionLocal() as session:
        for row in resolved:
            statement = pg_insert(SecurityFundamental).values(**row)
            session.execute(statement.on_conflict_do_update(
                index_elements=[SecurityFundamental.ticker],
                set_={key: value for key, value in row.items() if key != "ticker"}
                | {"updated_at": datetime.now(timezone.utc)}))
        session.commit()
    payload = {
        "source_id": SOURCE_ID, **stats,
        "tickers_with_eps": len(resolved),
        "errors": errors[:50],
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "sec_xbrl_eps.json").write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def sync_trailing_pe(*, latest_only: bool = True) -> dict[str, Any]:
    """Write an official trailing P/E for N-PORT positions with an EPS match."""
    _ensure_source()
    started = time.monotonic()
    with psycopg.connect(_raw_url(), autocommit=False) as connection:
        with connection.cursor() as cursor:
            if latest_only:
                cursor.execute("""
                    CREATE TEMP TABLE stg_pe_reports ON COMMIT DROP AS
                    SELECT fund_id, max(reporting_date) AS reporting_date
                    FROM portfolio_holdings
                    WHERE data_source IN ('sec_edgar_nport_bulk', 'sec_edgar_nport')
                    GROUP BY 1
                """)
                cursor.execute("CREATE INDEX ON stg_pe_reports (fund_id, reporting_date)")
                cursor.execute("ANALYZE stg_pe_reports")
            # The temp table only exists in latest-only mode, so the filter must
            # be omitted from the SQL text entirely in all-reports mode; a
            # short-circuiting parameter would still be parsed and fail.
            latest_filter = """
                  AND EXISTS (
                      SELECT 1 FROM stg_pe_reports r
                      WHERE r.fund_id = h.fund_id
                        AND r.reporting_date = h.reporting_date)
            """ if latest_only else ""
            cursor.execute("""
                CREATE TEMP TABLE stg_pe ON COMMIT DROP AS
                SELECT h.id AS holding_id, h.reporting_date, h.source_url,
                       sf.eps, sf.eps_period_end, sf.source_url AS eps_source_url,
                       round((h.market_value / h.quantity) / sf.eps, 8) AS trailing_pe
                FROM portfolio_holdings h
                JOIN security_fundamentals sf
                  ON sf.ticker = upper(btrim(h.ticker))
                WHERE h.data_source IN ('sec_edgar_nport_bulk', 'sec_edgar_nport')
                  AND h.asset_category = 'EC'
                  AND h.unit = 'NS'
                  AND h.quantity > 0
                  AND h.market_value > 0
                  AND sf.eps > 0
            """ + latest_filter)
            cursor.execute("""
                DELETE FROM stg_pe
                WHERE trailing_pe < %s OR trailing_pe > %s
            """, (MIN_PE, MAX_PE))
            cursor.execute("SELECT count(*) FROM stg_pe")
            computed = cursor.fetchone()[0]
            cursor.execute("""
                INSERT INTO holding_metrics (
                    holding_id, data_source, source_url, as_of_date,
                    trailing_pe, trailing_eps, eps_period_end,
                    trailing_pe_basis, retrieved_at
                )
                SELECT holding_id, 'sec_nport_derived', source_url, reporting_date,
                       trailing_pe, eps, eps_period_end,
                       'Trailing P/E = N-PORT filed market value per share / SEC XBRL '
                       || 'annual diluted EPS of ' || eps::text
                       || ' for the fiscal year ended ' || eps_period_end::text
                       || ' (' || eps_source_url || '). Not a forecast; excludes '
                       || 'negative-EPS issuers and non-common-equity positions.',
                       now()
                FROM stg_pe
                ON CONFLICT (holding_id, data_source, as_of_date)
                DO UPDATE SET
                    trailing_pe = EXCLUDED.trailing_pe,
                    trailing_eps = EXCLUDED.trailing_eps,
                    eps_period_end = EXCLUDED.eps_period_end,
                    trailing_pe_basis = EXCLUDED.trailing_pe_basis,
                    retrieved_at = EXCLUDED.retrieved_at
            """)
            written = cursor.rowcount
        connection.commit()
    result = {
        "source_id": SOURCE_ID, "positions_computed": computed,
        "positions_written": written, "latest_only": latest_only,
        "min_pe": MIN_PE, "max_pe": MAX_PE,
        "seconds": round(time.monotonic() - started, 1),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "sec_trailing_pe.json").write_text(json.dumps(result, indent=2) + "\n")
    return result
