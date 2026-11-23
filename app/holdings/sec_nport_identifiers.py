"""Build official security-identifier and issuer-industry crosswalks.

SEC Form N-PORT asks a filer to report a CUSIP, ISIN and ticker for each
position.  A single filer often knows only one of them (typically the CUSIP),
but across the whole filing population the same security is reported by many
funds.  This module aggregates that evidence so a CUSIP that any N-PORT filer
tagged with a ticker or ISIN can be labelled everywhere.

Only identifiers reported in an SEC filing are stored.  A CUSIP with conflicting
tickers is left empty unless one ticker has at least
``IDENTIFIER_AGREEMENT`` of the evidence, so a disputed mapping can never win
by a single vote.

The second crosswalk maps a ticker to the issuer's SEC EDGAR CIK and SIC code.
SIC is the only official issuer-industry classification the SEC publishes; it
is used as the holdings ``sector`` value with its code retained as provenance.
"""
from __future__ import annotations

import csv
import json
import re
import threading
import time
import urllib.error
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Iterator

import psycopg
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import database_url, timeout_seconds, user_agent
from app.db.session import SessionLocal
from app.models.schema import SecurityIdentifierMap, SecurityIndustry

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "united_states" / "nport_bulk"
REPORTS = ROOT / "reports"
IDENTIFIER_SOURCE = "sec_nport_identifiers"
INDUSTRY_SOURCE = "sec_edgar_sic"
IDENTIFIER_AGREEMENT = 0.8
_CUSIP_RE = re.compile(r"^[0-9A-Z*@#]{9}$")
_PLACEHOLDER_CUSIPS = {"000000000", "999999999", "N/A", "NA", "NONE"}
COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SUBMISSION_CACHE = ROOT / "data" / "raw" / "united_states" / "edgar_submissions"

# SIC major groups mapped to a familiar sector label.  The SEC publishes the
# four-digit SIC code and its description; this table groups those official
# codes into sectors without changing the underlying filing value.  Unknown
# codes keep the SEC description as the sector.
_SIC_RANGES = (
    (100, 999, "Agriculture"),
    (1000, 1499, "Energy & Mining"),
    (1500, 1799, "Construction"),
    (2000, 2199, "Consumer Staples"),
    (2200, 2399, "Consumer Discretionary"),
    (2400, 2799, "Materials"),
    (2800, 2899, "Health Care"),
    (2900, 2999, "Energy"),
    (3000, 3399, "Industrials"),
    (3570, 3579, "Information Technology"),
    (3400, 3599, "Industrials"),
    (3600, 3699, "Information Technology"),
    (3700, 3799, "Consumer Discretionary"),
    (3800, 3899, "Health Care"),
    (3900, 3999, "Industrials"),
    (4000, 4799, "Transportation"),
    (4800, 4899, "Communication Services"),
    (4900, 4999, "Utilities"),
    (5000, 5199, "Consumer Staples"),
    (5200, 5999, "Consumer Discretionary"),
    (6000, 6199, "Financials"),
    (6200, 6299, "Financials"),
    (6300, 6499, "Financials"),
    (6500, 6599, "Real Estate"),
    (6600, 6799, "Financials"),
    (7000, 7299, "Consumer Discretionary"),
    (7300, 7399, "Information Technology"),
    (7400, 7999, "Consumer Discretionary"),
    (8000, 8099, "Health Care"),
    (8100, 8999, "Industrials"),
    (9100, 9999, "Public Administration"),
)
_SIC_OVERRIDES = {
    "6726": "Funds",
    "6798": "Real Estate",
    "6799": "Financials",
    "6770": "Financials",
    "2834": "Health Care",
    "2835": "Health Care",
    "2836": "Health Care",
    "8731": "Health Care",
    "3672": "Information Technology",
    "3674": "Information Technology",
    "7370": "Information Technology",
    "7371": "Information Technology",
    "7372": "Information Technology",
    "7373": "Information Technology",
    "7374": "Information Technology",
    "4812": "Communication Services",
    "4813": "Communication Services",
    "4832": "Communication Services",
    "4833": "Communication Services",
    "4841": "Communication Services",
    "7812": "Communication Services",
    "7822": "Communication Services",
    "7900": "Communication Services",
    "7990": "Communication Services",
}


def cusip_is_plausible(value: str | None) -> bool:
    """Return True for a nine-character CUSIP that is not a filed placeholder."""
    text_value = (value or "").strip().upper()
    if text_value in _PLACEHOLDER_CUSIPS or len(text_value) != 9:
        return False
    if not _CUSIP_RE.match(text_value):
        return False
    # Reject repeated characters such as 111111111, which filers use for cash.
    return len(set(text_value)) > 1


def sector_for_sic(sic: str | None, description: str | None = None) -> str | None:
    """Group an official SEC SIC code into a sector label."""
    if not sic or not sic.strip().isdigit():
        return description.strip() if description and description.strip() else None
    code = sic.strip()
    if code in _SIC_OVERRIDES:
        return _SIC_OVERRIDES[code]
    numeric = int(code)
    for low, high, label in _SIC_RANGES:
        if low <= numeric <= high:
            return label
    return description.strip() if description and description.strip() else None


def _rows(path: Path) -> Iterator[dict[str, str]]:
    with path.open("r", encoding="utf-8", errors="replace", newline="") as stream:
        yield from csv.DictReader(stream, delimiter="\t")


def _clean(value: str | None, limit: int | None = None) -> str | None:
    token = (value or "").strip()
    if not token or token.upper() in {"N/A", "NA", "N.A.", "NONE", "-", "--"}:
        return None
    return token[:limit] if limit else token


def _int(value: str | None) -> int | None:
    try:
        return int(value) if value is not None and value.strip() else None
    except ValueError:
        return None


def _parse_sec_date(value: str | None) -> date | None:
    token = (value or "").strip().upper()
    if not token:
        return None
    months = {name: index for index, name in enumerate(
        ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"), 1)}
    parts = token.split("-")
    if len(parts) == 3 and parts[1] in months and parts[0].isdigit() and parts[2].isdigit():
        return date(int(parts[2]), months[parts[1]], int(parts[0]))
    for fmt in ("%Y-%m-%d", "%d-%b-%Y"):
        try:
            return datetime.strptime(token, fmt).date()
        except ValueError:
            continue
    return None


def local_quarters() -> list[str]:
    """Return extracted N-PORT quarter directories, newest first."""
    return sorted(
        (path.name for path in RAW.iterdir()
         if path.is_dir() and re.fullmatch(r"\d{4}q[1-4]", path.name)),
        reverse=True,
    )


def _raw_url() -> str:
    return database_url().replace("postgresql+psycopg://", "postgresql://", 1)


def _ensure_source() -> None:
    from app.models.schema import Source
    definition = {
        "source_id": IDENTIFIER_SOURCE, "country_code": "US",
        "organization": "U.S. Securities and Exchange Commission",
        "source_name": "SEC N-PORT filed security identifiers (CUSIP/ISIN/ticker)",
        "endpoint_url": "https://www.sec.gov/data-research/sec-markets-data/form-n-port-data-sets",
        "verification_status": "Usable Fund Data Confirmed",
        "integration_status": "Integrated", "license_status": "Public SEC filing",
    }
    with SessionLocal() as session:
        statement = pg_insert(Source).values(**definition)
        session.execute(statement.on_conflict_do_update(
            index_elements=[Source.source_id],
            set_={key: value for key, value in definition.items() if key != "source_id"}))
        session.commit()


def build_identifier_map_from_staging(cursor: psycopg.Cursor) -> int:
    """Aggregate identifier evidence already staged for one quarter.

    The caller must have populated ``stg_bulk_holdings`` (holding_id, cusip),
    ``stg_bulk_identifiers`` (holding_id, isin, ticker) and
    ``stg_bulk_accessions`` (accession, report_date).
    """
    ratio = float(IDENTIFIER_AGREEMENT)
    cursor.execute("""
        CREATE TEMP TABLE stg_identifier_ticker ON COMMIT DROP AS
        SELECT upper(btrim(h.cusip)) AS cusip,
               upper(btrim(i.ticker)) AS ticker,
               count(*)::int AS votes
        FROM stg_bulk_holdings h
        JOIN stg_bulk_identifiers i ON i.holding_id = h.holding_id
        WHERE h.cusip ~ '^[0-9A-Za-z*@#]{9}$'
          AND upper(btrim(h.cusip)) NOT IN ('000000000','999999999')
          AND nullif(btrim(i.ticker),'') IS NOT NULL
        GROUP BY 1, 2
    """)
    cursor.execute("""
        CREATE TEMP TABLE stg_identifier_isin ON COMMIT DROP AS
        SELECT upper(btrim(h.cusip)) AS cusip,
               upper(btrim(i.isin)) AS isin,
               count(*)::int AS votes
        FROM stg_bulk_holdings h
        JOIN stg_bulk_identifiers i ON i.holding_id = h.holding_id
        WHERE h.cusip ~ '^[0-9A-Za-z*@#]{9}$'
          AND upper(btrim(h.cusip)) NOT IN ('000000000','999999999')
          AND nullif(btrim(i.isin),'') IS NOT NULL
        GROUP BY 1, 2
    """)
    cursor.execute(f"""
        CREATE TEMP TABLE stg_identifier_best ON COMMIT DROP AS
        WITH ticker_total AS (
            SELECT cusip, sum(votes)::numeric AS total FROM stg_identifier_ticker GROUP BY 1
        ), ticker_ranked AS (
            SELECT t.cusip, t.ticker, t.votes, r.total,
                   row_number() OVER (PARTITION BY t.cusip ORDER BY t.votes DESC, t.ticker) AS rn
            FROM stg_identifier_ticker t JOIN ticker_total r USING (cusip)
        ), ticker_best AS (
            SELECT cusip, ticker, votes, total
            FROM ticker_ranked
            WHERE rn = 1 AND votes::numeric / total >= {ratio}
        ), isin_total AS (
            SELECT cusip, sum(votes)::numeric AS total FROM stg_identifier_isin GROUP BY 1
        ), isin_ranked AS (
            SELECT i.cusip, i.isin, i.votes, r.total,
                   row_number() OVER (PARTITION BY i.cusip ORDER BY i.votes DESC, i.isin) AS rn
            FROM stg_identifier_isin i JOIN isin_total r USING (cusip)
        ), isin_best AS (
            SELECT cusip, isin, votes
            FROM isin_ranked
            WHERE rn = 1 AND votes::numeric / total >= {ratio}
        )
        SELECT t.cusip, t.ticker, t.votes AS ticker_votes,
               i.isin, COALESCE(i.votes, 0) AS isin_votes,
               a.max_report_date AS latest_report_date
        FROM ticker_best t
        LEFT JOIN isin_best i USING (cusip)
        CROSS JOIN (SELECT max(report_date) AS max_report_date FROM stg_bulk_accessions) a
    """)
    cursor.execute("""
        INSERT INTO security_identifier_map (
            cusip, ticker, isin, ticker_votes, isin_votes, evidence_rows,
            latest_report_date, source_id, updated_at
        )
        SELECT cusip, ticker, isin, ticker_votes, isin_votes,
               ticker_votes + isin_votes, latest_report_date, %s, now()
        FROM stg_identifier_best
        ON CONFLICT (cusip) DO UPDATE SET
            ticker = CASE
                WHEN EXCLUDED.latest_report_date >= security_identifier_map.latest_report_date
                THEN COALESCE(EXCLUDED.ticker, security_identifier_map.ticker)
                ELSE security_identifier_map.ticker END,
            isin = CASE
                WHEN EXCLUDED.latest_report_date >= security_identifier_map.latest_report_date
                THEN COALESCE(EXCLUDED.isin, security_identifier_map.isin)
                ELSE security_identifier_map.isin END,
            ticker_votes = EXCLUDED.ticker_votes,
            isin_votes = EXCLUDED.isin_votes,
            evidence_rows = EXCLUDED.evidence_rows,
            latest_report_date = GREATEST(
                security_identifier_map.latest_report_date, EXCLUDED.latest_report_date),
            updated_at = now()
    """, (IDENTIFIER_SOURCE,))
    return cursor.rowcount


def apply_identifier_map(*, latest_only: bool = False) -> dict[str, int]:
    """Fill NULL holding tickers/ISINs from the official crosswalk.

    Existing values are never overwritten.  CUSIPs are compared case
    insensitively because some filings contain lowercase CUSIPs.

    ``latest_only`` restricts the update to each fund's newest report.  The
    full history contains tens of millions of rows that already have a filed
    ticker or refer to debt/derivative CUSIPs with no equity symbol; updating
    only the latest report keeps the profile pages current without a multi-hour
    rewrite of the whole table.
    """
    with psycopg.connect(_raw_url(), autocommit=False) as connection:
        with connection.cursor() as cursor:
            latest_from = ""
            latest_where = ""
            if latest_only:
                cursor.execute("""
                    CREATE TEMP TABLE stg_latest_reports ON COMMIT DROP AS
                    SELECT fund_id, max(reporting_date) AS reporting_date
                    FROM portfolio_holdings
                    GROUP BY 1
                """)
                cursor.execute("CREATE UNIQUE INDEX ON stg_latest_reports (fund_id)")
                cursor.execute("ANALYZE stg_latest_reports")
                latest_from = ", stg_latest_reports l"
                latest_where = """
                  AND h.fund_id = l.fund_id
                  AND h.reporting_date = l.reporting_date
                """
            cursor.execute("""
                UPDATE portfolio_holdings h
                SET ticker = m.ticker
                FROM security_identifier_map m
            """ + latest_from + """
                WHERE h.ticker IS NULL
                  AND h.cusip IS NOT NULL
                  AND upper(btrim(h.cusip)) = m.cusip
                  AND m.ticker IS NOT NULL
            """ + latest_where)
            ticker_rows = cursor.rowcount
            cursor.execute("""
                UPDATE portfolio_holdings h
                SET isin = m.isin
                FROM security_identifier_map m
            """ + latest_from + """
                WHERE h.isin IS NULL
                  AND h.cusip IS NOT NULL
                  AND upper(btrim(h.cusip)) = m.cusip
                  AND m.isin IS NOT NULL
            """ + latest_where)
            isin_rows = cursor.rowcount
        connection.commit()
    return {"ticker_rows_filled": ticker_rows, "isin_rows_filled": isin_rows,
            "latest_only": latest_only}


def sync_identifier_map(quarters: Iterable[str] | None = None, *, apply: bool = True,
                        latest_only: bool = False) -> dict[str, Any]:
    """Rebuild the map from extracted quarterly archives and apply it.

    ``quarters`` defaults to every extracted archive.  Only local files are
    read; use ``sync-sec-nport-bulk`` to download a new quarter first.
    """
    _ensure_source()
    selected = list(quarters or local_quarters())
    if not selected:
        raise FileNotFoundError("No extracted N-PORT quarters are available")
    counts: dict[str, Any] = {"quarters": selected, "map_rows": 0, "apply": {}}
    with psycopg.connect(_raw_url(), autocommit=False) as connection:
        for quarter in selected:
            directory = RAW / quarter
            holdings = directory / "FUND_REPORTED_HOLDING.tsv"
            identifiers = directory / "IDENTIFIERS.tsv"
            submissions = directory / "SUBMISSION.tsv"
            if not (holdings.exists() and identifiers.exists() and submissions.exists()):
                counts.setdefault("skipped", []).append(quarter)
                continue
            with connection.cursor() as cursor:
                cursor.execute("""
                    CREATE TEMP TABLE stg_bulk_holdings (
                        holding_id bigint, cusip text) ON COMMIT DROP;
                    CREATE TEMP TABLE stg_bulk_identifiers (
                        holding_id bigint, isin text, ticker text) ON COMMIT DROP;
                    CREATE TEMP TABLE stg_bulk_accessions (
                        accession text, report_date date) ON COMMIT DROP;
                """)
                with cursor.copy("COPY stg_bulk_holdings (holding_id, cusip) FROM STDIN") as copy:
                    for row in _rows(holdings):
                        copy.write_row((_int(row.get("HOLDING_ID")), _clean(row.get("ISSUER_CUSIP"), 12)))
                with cursor.copy("COPY stg_bulk_identifiers (holding_id, isin, ticker) FROM STDIN") as copy:
                    for row in _rows(identifiers):
                        copy.write_row((_int(row.get("HOLDING_ID")),
                                        _clean(row.get("IDENTIFIER_ISIN"), 12),
                                        _clean(row.get("IDENTIFIER_TICKER"), 50)))
                with cursor.copy("COPY stg_bulk_accessions (accession, report_date) FROM STDIN") as copy:
                    for row in _rows(submissions):
                        report_date = _parse_sec_date(row.get("REPORT_DATE"))
                        if report_date is not None:
                            copy.write_row((_clean(row.get("ACCESSION_NUMBER"), 50), report_date))
                cursor.execute("CREATE INDEX ON stg_bulk_holdings (holding_id)")
                cursor.execute("CREATE INDEX ON stg_bulk_identifiers (holding_id)")
                counts["map_rows"] += build_identifier_map_from_staging(cursor)
            connection.commit()
    counts["apply"] = apply_identifier_map(latest_only=latest_only) if apply else {"skipped": True}
    REPORTS.mkdir(parents=True, exist_ok=True)
    counts["completed_at"] = datetime.now(timezone.utc).isoformat()
    (REPORTS / "sec_nport_identifier_map.json").write_text(json.dumps(counts, indent=2) + "\n")
    return counts


def _sec_json(url: str) -> Any:
    request = urllib.request.Request(url, headers={
        "User-Agent": user_agent(), "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout_seconds()) as response:
        return json.load(response)


def _company_tickers_payload() -> Any:
    """Read the cached SEC company/ticker directory when available."""
    cache = ROOT / "data" / "raw" / "united_states" / "sec_company_tickers_exchange.json"
    if cache.exists():
        return json.loads(cache.read_text())
    payload = _sec_json(COMPANY_TICKERS_URL)
    cache.write_text(json.dumps(payload))
    return payload


def _submission_payload(cik: str) -> Any:
    """Read a cached EDGAR submission, or fetch and cache it once."""
    SUBMISSION_CACHE.mkdir(parents=True, exist_ok=True)
    cache = SUBMISSION_CACHE / f"CIK{cik}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    payload = _sec_json(SUBMISSIONS_URL.format(cik=cik))
    cache.write_text(json.dumps(payload))
    return payload


def sync_sec_industry(tickers: Iterable[str] | None = None, *, limit: int | None = None,
                      latest_holdings: bool = False) -> dict[str, Any]:
    """Map tickers to their SEC CIK and SIC industry.

    The ticker list defaults to every ticker in ``security_identifier_map``
    that is not already resolved.  Each CIK is read once from the official
    ``data.sec.gov/submissions`` endpoint and paced below the SEC's 10 req/s
    guidance.
    """
    from app.models.schema import Source
    definition = {
        "source_id": INDUSTRY_SOURCE, "country_code": "US",
        "organization": "U.S. Securities and Exchange Commission",
        "source_name": "SEC EDGAR company SIC industry classification",
        "endpoint_url": COMPANY_TICKERS_URL,
        "verification_status": "Usable Fund Data Confirmed",
        "integration_status": "Integrated", "license_status": "Public SEC filing",
    }
    with SessionLocal() as session:
        statement = pg_insert(Source).values(**definition)
        session.execute(statement.on_conflict_do_update(
            index_elements=[Source.source_id],
            set_={key: value for key, value in definition.items() if key != "source_id"}))
        session.commit()

    if tickers is None and latest_holdings:
        with SessionLocal() as session:
            tickers = [row[0] for row in session.execute(text("""
                WITH latest AS (
                    SELECT fund_id, max(reporting_date) AS reporting_date
                    FROM portfolio_holdings GROUP BY 1
                )
                SELECT DISTINCT upper(btrim(h.ticker))
                FROM portfolio_holdings h
                JOIN latest l USING (fund_id, reporting_date)
                LEFT JOIN security_industry i ON i.ticker = upper(btrim(h.ticker))
                WHERE h.ticker IS NOT NULL AND btrim(h.ticker) <> ''
                  AND i.ticker IS NULL
            """)).all()]
    elif tickers is None:
        with SessionLocal() as session:
            tickers = [row[0] for row in session.execute(text("""
                SELECT DISTINCT m.ticker
                FROM security_identifier_map m
                LEFT JOIN security_industry i ON i.ticker = m.ticker
                WHERE m.ticker IS NOT NULL AND i.ticker IS NULL
            """)).all()]
    wanted = {ticker.strip().upper() for ticker in tickers if ticker and ticker.strip()}
    if limit:
        wanted = set(sorted(wanted)[:limit])

    payload = _company_tickers_payload()
    fields = payload.get("fields") or []
    rows = payload.get("data") or []
    ticker_to_cik: dict[str, tuple[str, str, str]] = {}
    for row in rows:
        record = dict(zip(fields, row))
        ticker = str(record.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        # EDGAR uses BRK-B; N-PORT filers often write BRK/B.
        ticker_to_cik[ticker] = (str(record.get("cik") or "").zfill(10),
                                 str(record.get("name") or ""),
                                 str(record.get("exchange") or ""))
    for ticker in list(wanted):
        normalized = ticker.replace("/", "-")
        if ticker not in ticker_to_cik and normalized in ticker_to_cik:
            ticker_to_cik[ticker] = ticker_to_cik[normalized]

    resolved: dict[str, dict[str, Any]] = {}
    cik_cache: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, str]] = []

    # One CIK per company, fetched in parallel but paced below the SEC's
    # 10 requests/second guidance. Responses are cached on disk so a rerun is
    # network-free for CIKs that were already read.
    needed = {
        ticker_to_cik[ticker][0]: (ticker_to_cik[ticker][1], ticker_to_cik[ticker][2])
        for ticker in sorted(wanted)
        if ticker in ticker_to_cik and ticker_to_cik[ticker][0]
        and ticker_to_cik[ticker][0] != "0000000000"
    }
    next_at = [0.0]
    rate_lock = threading.Lock()

    def reserve_slot() -> None:
        with rate_lock:
            now = time.monotonic()
            start = max(now, next_at[0])
            next_at[0] = start + 0.12
        wait = start - time.monotonic()
        if wait > 0:
            time.sleep(wait)

    def fetch(cik: str, name: str, exchange: str) -> tuple[str, dict[str, Any], str | None]:
        reserve_slot()
        try:
            submission = _submission_payload(cik)
            return cik, {
                "cik": cik,
                "company_name": submission.get("name") or name,
                "sic": (submission.get("sic") or "").strip() or None,
                "sic_description": (submission.get("sicDescription") or "").strip() or None,
                "exchange": (submission.get("exchanges") or [exchange or None])[0],
            }, None
        except Exception as error:  # noqa: BLE001 - record and continue
            return cik, {}, str(error)[:200]

    if needed:
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = [pool.submit(fetch, cik, name, exchange)
                       for cik, (name, exchange) in needed.items()]
            for future in as_completed(futures):
                cik, info, error = future.result()
                cik_cache[cik] = info
                if error:
                    errors.append({"cik": cik, "error": error})

    for ticker in sorted(wanted):
        if ticker not in ticker_to_cik:
            continue
        cik = ticker_to_cik[ticker][0]
        info = cik_cache.get(cik) or {}
        if not info.get("sic") and not info.get("sic_description"):
            continue
        resolved[ticker] = {
            "ticker": ticker,
            **info,
            "sector": sector_for_sic(info.get("sic"), info.get("sic_description")),
            "source_url": SUBMISSIONS_URL.format(cik=cik),
        }

    if resolved:
        with SessionLocal() as session:
            statement = pg_insert(SecurityIndustry).values(list(resolved.values())).on_conflict_do_update(
                index_elements=[SecurityIndustry.ticker],
                set_={key: getattr(pg_insert(SecurityIndustry).excluded, key)
                      for key in ("cik", "company_name", "sic", "sic_description",
                                  "sector", "exchange", "source_id", "source_url", "updated_at")})
            session.execute(statement)
            session.commit()

    result = {
        "tickers_requested": len(wanted), "tickers_resolved": len(resolved),
        "ciks_read": len(cik_cache), "errors": errors[:50],
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "sec_industry_map.json").write_text(json.dumps(result, indent=2) + "\n")
    return result
