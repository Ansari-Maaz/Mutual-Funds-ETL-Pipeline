"""Official class-level fund facts from SEC Form N-1A risk/return XBRL data.

The SEC DERA "Mutual Fund Prospectus Risk/Return Summary Data Sets" are quarterly
archives of the XBRL financial data every open-end fund and ETF files with its
prospectus (Form N-1A: 485BPOS / 497 / 497K). They are keyed by the SEC class ID
(``C000...``), the same identifier FundFlow stores as ``source_fund_id`` for
``sec_open_end_fund_classes``, so no fuzzy name matching is involved.

Fields imported (only when the FundFlow column is currently NULL):

* ``inception_date`` from the fund's own ``PerfInceptionDate`` /
  ``AnnualReturnInceptionDate`` fact in the performance table. Benchmark-index
  rows (which carry a ``measure`` value) are ignored: they describe an index,
  not the fund class.
* ``ticker`` from the prospectus cover-page class table (``scn.tsv``) and the
  ``dei:TradingSymbol`` fact in ``txt.tsv``, when well-formed and not already
  assigned to a different class.

The same archives also carry the prospectus fee table and performance table.
Those values are written to ``fund_profile_snapshots`` as source-backed class
profiles:

* ``summary`` - net/gross expense ratio, portfolio turnover, objective,
  strategy and share-class performance inception date;
* ``expense_ratio_history`` - net, gross, management, 12b-1 and other expense
  components;
* ``performance`` - publisher-reported 1/3/5/10-year average annual returns;
* ``n1a_prospectus`` - the objective and strategy text blocks;
* ``inception_date`` - the filed performance inception date.

Every value keeps the accession number and report date. ``num.tsv`` carries the
numeric facts and ``txt.tsv`` the text/date facts, so both are read.
"""
from __future__ import annotations

import csv
import html
import io
import json
import logging
import os
import re
import shutil
import urllib.error
import urllib.request
import zipfile
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterator

import psycopg

from app.config import database_url, timeout_seconds, user_agent

LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "united_states" / "rr"
REPORTS = ROOT / "reports"
BASE_URL = ("https://www.sec.gov/files/dera/data/mutual-fund-prospectus-risk/"
            "return-summary-data-sets/{quarter}_rr1.zip")
PAGE_URL = ("https://www.sec.gov/data-research/sec-markets-data/"
            "mutual-fund-prospectus-riskreturn-summary-data-sets")
SUPPORTED_LABEL_RE = re.compile(r"^(\d{4})(?:q([1-4])|-(0[1-9]|1[0-2]))?$")  # 2026q3, 2026-10 or annual 2023
REQUIRED_MEMBERS = {"sub.tsv", "txt.tsv", "scn.tsv"}
SOURCE_ID = "sec_open_end_fund_classes"
INCEPTION_TAGS = {"PerfInceptionDate", "AnnualReturnInceptionDate"}
TEXT_TAGS = {"ObjectivePrimaryTextBlock": "objective", "StrategyNarrativeTextBlock": "strategy"}
TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")
CLASS_RE = re.compile(r"^C\d{9}$")
SERIES_RE = re.compile(r"^S\d{9}$")
MIN_INCEPTION = date(1924, 3, 21)  # first US open-end mutual fund (MFS), a hard lower bound

EXPENSE_TAGS = {
    "NetExpensesOverAssets": "net",
    "ExpensesOverAssets": "gross",
    "ManagementFeesOverAssets": "management",
    "DistributionAndService12b1FeesOverAssets": "distribution_12b1",
    "OtherExpensesOverAssets": "other",
    "ExpenseExampleYear01": "expense_1y",
    "ExpenseExampleYear03": "expense_3y",
    "ExpenseExampleYear05": "expense_5y",
    "ExpenseExampleYear10": "expense_10y",
}
RETURN_TAGS = {"AvgAnnlRtrPct": "average", "AnnlRtrPct": "annual"}

csv.field_size_limit(1 << 26)  # txt.tsv carries multi-kilobyte prose cells


def _label_key(label: str) -> tuple[int, int]:
    """Sort key: (year, month-of-period-end) so monthly and quarterly labels interleave."""
    match = SUPPORTED_LABEL_RE.match(label)
    year = int(match.group(1))
    month = int(match.group(3)) if match.group(3) else (int(match.group(2)) * 3 if match.group(2) else 12)
    return year, month


def available_archives(limit: int | None = None) -> list[str]:
    """Newest-first labels of the archives SEC currently publishes in the supported layout.

    SEC publishes annual archives (2011-2023), quarterly archives from 2025q1 and
    a monthly one for the current period. Archives lacking the class/ticker
    tables (the earliest years) are skipped at parse time.
    """
    request = urllib.request.Request(PAGE_URL, headers={"User-Agent": user_agent(), "Accept": "text/html"})
    with urllib.request.urlopen(request, timeout=timeout_seconds()) as response:
        html_page = response.read().decode("utf-8", errors="replace")
    labels = {m for m in re.findall(r"/([0-9]{4}(?:q[1-4]|-[0-9]{2})?)_rr1\.zip", html_page) if SUPPORTED_LABEL_RE.match(m)}
    ordered = sorted(labels, key=_label_key, reverse=True)
    return ordered[:limit] if limit else ordered


def download_quarter(quarter: str, *, refresh: bool = False) -> Path | None:
    """Download one archive atomically; return None when SEC has not published it (404)."""
    RAW.mkdir(parents=True, exist_ok=True)
    archive = RAW / f"{quarter}_rr1.zip"
    if archive.exists() and not refresh and zipfile.is_zipfile(archive):
        return archive
    request = urllib.request.Request(BASE_URL.format(quarter=quarter),
                                     headers={"User-Agent": user_agent(), "Accept": "application/zip,*/*"})
    partial = archive.with_suffix(".zip.part")
    try:
        with urllib.request.urlopen(request, timeout=max(timeout_seconds(), 120)) as response, partial.open("wb") as out:
            shutil.copyfileobj(response, out, length=1024 * 1024)
        if not zipfile.is_zipfile(partial):
            raise ValueError(f"Risk/return archive {quarter} is not a valid zip")
        os.replace(partial, archive)
    except urllib.error.HTTPError as error:
        if error.code in (403, 404):
            LOGGER.info("Risk/return archive %s not published (HTTP %s)", quarter, error.code)
            return None
        raise
    finally:
        partial.unlink(missing_ok=True)
    return archive


def _rows(archive: Path, member: str) -> Iterator[dict[str, str]]:
    with zipfile.ZipFile(archive) as bundle, bundle.open(member) as raw:
        yield from csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8", errors="replace", newline=""),
                                  delimiter="\t")


def _parse_date(value: str | None) -> date | None:
    value = (value or "").strip()[:10]
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return parsed if MIN_INCEPTION <= parsed <= date.today() else None


def _compact_date(value: str | None) -> date | None:
    text = (value or "").strip()
    if len(text) != 8 or not text.isdigit():
        return _parse_date(text)
    try:
        parsed = date(int(text[:4]), int(text[4:6]), int(text[6:8]))
    except ValueError:
        return None
    return parsed if MIN_INCEPTION <= parsed <= date.today() else None


def _decimal(value: str | None) -> Decimal | None:
    text = (value or "").strip().replace(",", "")
    if not text:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _text_block(value: str | None) -> str | None:
    if not value:
        return None
    text = re.sub(r"<[^>]+>", " ", value)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _filed(stamp: str, current: dict[str, Any] | None) -> bool:
    return current is None or stamp > current.get("stamp", "")


def parse_archive(archive: Path) -> dict[str, Any]:
    """Extract class facts from one quarterly archive.

    Identity and date facts come from ``txt.tsv``; fee and return facts come from
    ``num.tsv``. The function is deliberately tolerant of older archives that
    lack ``num.tsv`` so the documented ticker/inception behaviour is preserved.
    """
    with zipfile.ZipFile(archive) as bundle:
        names = set(bundle.namelist())
    missing = REQUIRED_MEMBERS - names
    if missing:
        LOGGER.warning("Skipping %s: unsupported layout (missing %s)", archive.name, sorted(missing))
        return {"inception": {}, "tickers": {}, "expenses": {}, "returns": {},
                "turnover": {}, "texts": {}, "unsupported": True}
    filed: dict[str, str] = {}
    for row in _rows(archive, "sub.tsv"):
        filed[row["adsh"]] = (row.get("filed") or "")[:8]

    inception: dict[str, tuple[str, date, str]] = {}
    tickers: dict[str, tuple[str, str, str]] = {}
    texts: dict[str, dict[str, Any]] = {}
    for row in _rows(archive, "txt.tsv"):
        tag = row.get("tag")
        stamp = filed.get(row["adsh"], "")
        class_id = (row.get("class") or "").strip()
        series_id = (row.get("series") or "").strip()
        if tag in INCEPTION_TAGS and not (row.get("measure") or "").strip():
            parsed = _parse_date(row.get("value"))
            if not CLASS_RE.match(class_id) or parsed is None:
                continue
            current = inception.get(class_id)
            if current is None or stamp >= current[0]:
                inception[class_id] = (stamp, parsed, row["adsh"])
        elif tag == "TradingSymbol" and CLASS_RE.match(class_id):
            ticker = (row.get("value") or "").strip().upper()
            if not TICKER_RE.match(ticker):
                continue
            current = tickers.get(class_id)
            if current is None or stamp >= current[0]:
                tickers[class_id] = (stamp, ticker, row["adsh"])
        elif tag in TEXT_TAGS and SERIES_RE.match(series_id):
            text = _text_block(row.get("value"))
            if text is None:
                continue
            record = texts.get(series_id)
            if record is None or stamp > record["stamp"]:
                record = {"stamp": stamp, "adsh": row["adsh"],
                          "ddate": _compact_date(row.get("ddate")),
                          "objective": None, "strategy": None}
                texts[series_id] = record
            if stamp == record["stamp"]:
                record[TEXT_TAGS[tag]] = text

    # The scn table is the official cover-page class/ticker list. Keep it as a
    # ticker source even when txt.tsv does not carry a TradingSymbol fact.
    for row in _rows(archive, "scn.tsv"):
        class_id = (row.get("classid") or "").strip()
        ticker = (row.get("ticker") or "").strip().upper()
        if CLASS_RE.match(class_id) and TICKER_RE.match(ticker):
            stamp = filed.get(row["adsh"], "")
            current = tickers.get(class_id)
            if current is None or stamp >= current[0]:
                tickers[class_id] = (stamp, ticker, row["adsh"])

    expenses: dict[str, dict[str, Any]] = {}
    returns: dict[str, dict[int, dict[str, Any]]] = defaultdict(dict)
    turnover: dict[str, dict[str, Any]] = {}
    if "num.tsv" in names:
        for row in _rows(archive, "num.tsv"):
            tag = row.get("tag")
            if tag not in EXPENSE_TAGS and tag not in RETURN_TAGS and tag != "PortfolioTurnoverRate":
                continue
            stamp = filed.get(row["adsh"], "")
            class_id = (row.get("class") or "").strip()
            series_id = (row.get("series") or "").strip()
            ddate = _compact_date(row.get("ddate"))
            value = _decimal(row.get("value"))
            if value is None:
                continue
            if tag in EXPENSE_TAGS and CLASS_RE.match(class_id):
                current = expenses.get(class_id)
                if current is None or stamp > current["stamp"]:
                    current = {"stamp": stamp, "adsh": row["adsh"],
                               "ddate": ddate, "values": {}}
                    expenses[class_id] = current
                if current["adsh"] == row["adsh"]:
                    current["values"][EXPENSE_TAGS[tag]] = value
            elif tag == "PortfolioTurnoverRate" and SERIES_RE.match(series_id):
                current = turnover.get(series_id)
                if current is None or stamp > current["stamp"] or (
                        stamp == current["stamp"] and ddate and current.get("ddate")
                        and ddate >= current["ddate"]):
                    turnover[series_id] = {"stamp": stamp, "adsh": row["adsh"],
                                           "ddate": ddate, "value": value}
            elif tag == "AvgAnnlRtrPct" and CLASS_RE.match(class_id):
                otherdims = row.get("otherdims") or ""
                if (row.get("measure") or "").strip():
                    continue
                if "IndexAxis" in otherdims or "IndustrySectorAxis" in otherdims:
                    continue
                if "SalesLoadAxis" in otherdims and "WithoutSalesLoad" not in otherdims:
                    continue
                try:
                    quarters = int(row.get("qtrs") or 0)
                except ValueError:
                    quarters = 0
                if quarters <= 0 or quarters % 4:
                    continue
                years = quarters // 4
                if years not in {1, 3, 5, 10}:
                    continue
                current = returns[class_id].get(years)
                if (current is None or (ddate or date.min) > (current.get("ddate") or date.min)
                        or ((ddate or date.min) == (current.get("ddate") or date.min)
                            and stamp > current.get("stamp", ""))):
                    returns[class_id][years] = {
                        "stamp": stamp, "adsh": row["adsh"], "ddate": ddate,
                        "value": value, "years": years,
                    }
    return {"inception": inception, "tickers": tickers, "expenses": expenses,
            "returns": dict(returns), "turnover": turnover, "texts": texts}


def collect(quarters: list[str], *, refresh: bool = False) -> dict[str, Any]:
    """Merge several archives; the newest filing wins, conflicts are counted."""
    inception: dict[str, tuple[str, date, str]] = {}
    tickers: dict[str, tuple[str, str, str]] = {}
    expenses: dict[str, dict[str, Any]] = {}
    returns: dict[str, dict[int, dict[str, Any]]] = defaultdict(dict)
    turnover: dict[str, dict[str, Any]] = {}
    texts: dict[str, dict[str, Any]] = {}
    conflicts = 0
    used: list[str] = []
    for quarter in quarters:
        archive = download_quarter(quarter, refresh=refresh)
        if archive is None:
            continue
        parsed = parse_archive(archive)
        if parsed.get("unsupported"):
            continue
        used.append(quarter)
        for class_id, value in parsed["inception"].items():
            current = inception.get(class_id)
            if current is not None and current[1] != value[1]:
                conflicts += 1
            if current is None or value[0] >= current[0]:
                inception[class_id] = value
        for class_id, value in parsed["tickers"].items():
            current = tickers.get(class_id)
            if current is None or value[0] >= current[0]:
                tickers[class_id] = value
        for class_id, value in parsed["expenses"].items():
            current = expenses.get(class_id)
            if current is None or value["stamp"] > current["stamp"]:
                expenses[class_id] = value
            elif value["stamp"] == current["stamp"]:
                current["values"].update(value.get("values") or {})
        for class_id, horizons in parsed["returns"].items():
            for years, value in horizons.items():
                current = returns[class_id].get(years)
                if (current is None
                        or (value.get("ddate") or date.min) > (current.get("ddate") or date.min)
                        or ((value.get("ddate") or date.min) == (current.get("ddate") or date.min)
                            and value.get("stamp", "") > current.get("stamp", ""))):
                    returns[class_id][years] = value
        for series_id, value in parsed["turnover"].items():
            current = turnover.get(series_id)
            if current is None or value["stamp"] > current["stamp"]:
                turnover[series_id] = value
        for series_id, value in parsed["texts"].items():
            current = texts.get(series_id)
            if current is None or value["stamp"] > current["stamp"]:
                texts[series_id] = value
            elif value["stamp"] == current["stamp"]:
                current["objective"] = current.get("objective") or value.get("objective")
                current["strategy"] = current.get("strategy") or value.get("strategy")
    return {"quarters_used": used, "inception": inception, "tickers": tickers,
            "expenses": expenses, "returns": dict(returns), "turnover": turnover,
            "texts": texts, "inception_conflicts": conflicts}


def sync_sec_rr_profiles(*, quarters: int = 8, refresh: bool = False, dry_run: bool = False,
                         fill_tickers: bool = True) -> dict[str, Any]:
    """Fill US class identity and source-backed prospectus facts from N-1A XBRL."""
    data = collect(available_archives(quarters), refresh=refresh)
    raw_url = database_url().replace("postgresql+psycopg://", "postgresql://", 1)
    result: dict[str, Any] = {
        "quarters_used": data["quarters_used"],
        "classes_with_inception_in_sec": len(data["inception"]),
        "classes_with_ticker_in_sec": len(data["tickers"]),
        "classes_with_expenses_in_sec": len(data["expenses"]),
        "classes_with_returns_in_sec": len(data["returns"]),
        "series_with_text_in_sec": len(data["texts"]),
        "inception_conflicts": data["inception_conflicts"],
        "dry_run": dry_run,
    }
    if not data["quarters_used"]:
        result["note"] = "No risk/return archive could be downloaded"
        return result
    with psycopg.connect(raw_url, autocommit=False) as connection, connection.cursor() as cursor:
        cursor.execute("""
            CREATE TEMP TABLE stg_rr (
                class_id text PRIMARY KEY, inception date, inception_adsh text,
                ticker text, ticker_adsh text
            ) ON COMMIT DROP""")
        cursor.execute("""
            CREATE TEMP TABLE stg_rr_expense (
                class_id text PRIMARY KEY, ddate date, adsh text,
                net numeric, gross numeric, management numeric,
                distribution_12b1 numeric, other numeric,
                expense_1y numeric, expense_3y numeric, expense_5y numeric, expense_10y numeric
            ) ON COMMIT DROP""")
        cursor.execute("""
            CREATE TEMP TABLE stg_rr_return (
                class_id text, ddate date, years int, value numeric, adsh text,
                PRIMARY KEY (class_id, years)
            ) ON COMMIT DROP""")
        cursor.execute("""
            CREATE TEMP TABLE stg_rr_turnover (
                series_id text PRIMARY KEY, ddate date, value numeric, adsh text
            ) ON COMMIT DROP""")
        cursor.execute("""
            CREATE TEMP TABLE stg_rr_text (
                series_id text PRIMARY KEY, ddate date, objective text, strategy text, adsh text
            ) ON COMMIT DROP""")

        merged: dict[str, list[Any]] = defaultdict(lambda: [None, None, None, None])
        for class_id, (_, parsed, adsh) in data["inception"].items():
            merged[class_id][0:2] = [parsed, adsh]
        if fill_tickers:
            for class_id, (_, ticker, adsh) in data["tickers"].items():
                merged[class_id][2:4] = [ticker, adsh]
        with cursor.copy("COPY stg_rr (class_id, inception, inception_adsh, ticker, ticker_adsh) FROM STDIN") as copy:
            for class_id, (inc, inc_adsh, ticker, ticker_adsh) in merged.items():
                copy.write_row((class_id, inc, inc_adsh, ticker, ticker_adsh))

        with cursor.copy("""COPY stg_rr_expense (class_id, ddate, adsh, net, gross, management,
                distribution_12b1, other, expense_1y, expense_3y, expense_5y, expense_10y) FROM STDIN""") as copy:
            for class_id, value in data["expenses"].items():
                values = value.get("values") or {}
                copy.write_row((class_id, value.get("ddate"), value.get("adsh"),
                                values.get("net"), values.get("gross"), values.get("management"),
                                values.get("distribution_12b1"), values.get("other"),
                                values.get("expense_1y"), values.get("expense_3y"),
                                values.get("expense_5y"), values.get("expense_10y")))

        with cursor.copy("COPY stg_rr_return (class_id, ddate, years, value, adsh) FROM STDIN") as copy:
            for class_id, horizons in data["returns"].items():
                for years, value in horizons.items():
                    copy.write_row((class_id, value.get("ddate"), years, value.get("value"), value.get("adsh")))

        with cursor.copy("COPY stg_rr_turnover (series_id, ddate, value, adsh) FROM STDIN") as copy:
            for series_id, value in data["turnover"].items():
                copy.write_row((series_id, value.get("ddate"), value.get("value"), value.get("adsh")))

        with cursor.copy("COPY stg_rr_text (series_id, ddate, objective, strategy, adsh) FROM STDIN") as copy:
            for series_id, value in data["texts"].items():
                copy.write_row((series_id, value.get("ddate"), value.get("objective"),
                                value.get("strategy"), value.get("adsh")))

        cursor.execute("""
            SELECT count(*) FROM funds f JOIN stg_rr s ON s.class_id = f.source_fund_id
            WHERE f.source_id = %s AND f.inception_date IS NULL AND s.inception IS NOT NULL""", (SOURCE_ID,))
        result["inception_fillable"] = cursor.fetchone()[0]
        # A ticker is only assigned if no other US class already owns it.
        cursor.execute("""
            SELECT count(*) FROM funds f JOIN stg_rr s ON s.class_id = f.source_fund_id
            WHERE f.source_id = %s AND f.ticker IS NULL AND s.ticker IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM funds o WHERE o.domicile_country = 'US'
                              AND upper(o.ticker) = s.ticker)
              AND (SELECT count(*) FROM stg_rr t WHERE t.ticker = s.ticker) = 1""", (SOURCE_ID,))
        result["ticker_fillable"] = cursor.fetchone()[0]

        snapshot_sql = """
            INSERT INTO fund_profile_snapshots
                (fund_id, source_id, dataset, source_report_date, snapshot_key, payload, source_url, retrieved_at)
            {select}
            ON CONFLICT ON CONSTRAINT uq_fund_profile_source_snapshot DO UPDATE SET
                dataset = EXCLUDED.dataset, source_report_date = EXCLUDED.source_report_date,
                payload = EXCLUDED.payload, source_url = EXCLUDED.source_url, retrieved_at = now()"""

        cursor.execute(snapshot_sql.format(select="""
            SELECT f.id, %s, 'inception_date', s.inception,
                   'sec-rr-inception:' || s.class_id || ':' || s.inception,
                   jsonb_build_object('inception_date', s.inception::text, 'class_id', s.class_id,
                                      'accession_number', s.inception_adsh,
                                      'form', 'N-1A risk/return summary (XBRL)',
                                      'dataset', 'SEC DERA mutual fund prospectus risk/return data sets'),
                   %s, now()
            FROM funds f JOIN stg_rr s ON s.class_id = f.source_fund_id
            WHERE f.source_id = %s AND s.inception IS NOT NULL"""),
            (SOURCE_ID, URL_RR, SOURCE_ID))
        result["inception_snapshots"] = cursor.rowcount

        cursor.execute(snapshot_sql.format(select="""
            SELECT f.id, %s, 'summary',
                   COALESCE(e.ddate, tv.ddate, tx.ddate, s.inception),
                   'rr:' || f.source_fund_id || ':' || COALESCE(e.ddate::text, tv.ddate::text, tx.ddate::text, s.inception::text, 'undated') || ':summary',
                   jsonb_strip_nulls(jsonb_build_object(
                       'symbol', s.ticker, 'ticker', s.ticker,
                       'expense_ratio_net', e.net::text,
                       'expense_ratio_gross', e.gross::text,
                       'expense_ratio_basis', 'fraction of net assets',
                       'turnover_rate', tv.value::text,
                       'turnover_rate_basis', 'fraction of average net assets',
                       'overview', tx.objective, 'objective', tx.objective,
                       'strategy', tx.strategy,
                       'share_class_inception_date', s.inception::text,
                       'inception_date', s.inception::text,
                       'currency', 'USD',
                       'form', 'N-1A prospectus XBRL',
                       'source', 'SEC DERA mutual fund prospectus risk/return data sets')),
                   %s, now()
            FROM funds f
            JOIN stg_rr s ON s.class_id = f.source_fund_id
            LEFT JOIN stg_rr_expense e ON e.class_id = f.source_fund_id
            LEFT JOIN stg_rr_turnover tv ON tv.series_id = f.sec_series_id
            LEFT JOIN stg_rr_text tx ON tx.series_id = f.sec_series_id
            WHERE f.source_id = %s AND (e.class_id IS NOT NULL OR tv.series_id IS NOT NULL OR tx.series_id IS NOT NULL)"""),
            (SOURCE_ID, URL_RR, SOURCE_ID))
        result["summary_snapshots"] = cursor.rowcount

        cursor.execute(snapshot_sql.format(select="""
            SELECT f.id, %s, 'expense_ratio_history', e.ddate,
                   'rr:' || f.source_fund_id || ':' || COALESCE(e.ddate::text, 'undated') || ':expense:' || v.measure,
                   jsonb_strip_nulls(jsonb_build_object(
                       'measure', v.measure, 'reported_value', v.value::text,
                       'unit', 'fraction', 'effective_date', e.ddate::text,
                       'basis', 'prospectus fee table amount as a fraction of net assets',
                       'accession_number', e.adsh,
                       'source', 'SEC N-1A prospectus XBRL')),
                   %s, now()
            FROM funds f
            JOIN stg_rr_expense e ON e.class_id = f.source_fund_id
            CROSS JOIN LATERAL (VALUES
                ('net_expense_ratio', e.net), ('gross_expense_ratio', e.gross),
                ('management_fee', e.management), ('distribution_12b1_fee', e.distribution_12b1),
                ('other_expense', e.other)) AS v(measure, value)
            WHERE f.source_id = %s AND v.value IS NOT NULL"""),
            (SOURCE_ID, URL_RR, SOURCE_ID))
        result["expense_snapshots"] = cursor.rowcount

        cursor.execute(snapshot_sql.format(select="""
            SELECT f.id, %s, 'performance', r.ddate,
                   'rr:' || f.source_fund_id || ':' || COALESCE(r.ddate::text, 'undated') || ':average_annual_return_' || r.years || 'y',
                   jsonb_build_object(
                       'metric', CASE r.years WHEN 1 THEN 'oneYearReturn' WHEN 3 THEN 'threeYearReturn'
                                              WHEN 5 THEN 'fiveYearReturn' WHEN 10 THEN 'tenYearReturn'
                                              ELSE 'average_annual_return_' || r.years || 'y' END,
                       'value', r.value::text, 'unit', 'fraction', 'period_years', r.years,
                       'end_date', r.ddate::text, 'effective_date', r.ddate::text,
                       'load_basis', 'without_sales_load', 'accession_number', r.adsh,
                       'source', 'SEC N-1A prospectus XBRL'),
                   %s, now()
            FROM funds f JOIN stg_rr_return r ON r.class_id = f.source_fund_id
            WHERE f.source_id = %s"""),
            (SOURCE_ID, URL_RR, SOURCE_ID))
        result["performance_snapshots"] = cursor.rowcount

        cursor.execute(snapshot_sql.format(select="""
            SELECT f.id, %s, 'n1a_prospectus', tx.ddate,
                   'rr:' || f.source_fund_id || ':' || COALESCE(tx.ddate::text, 'undated') || ':n1a_prospectus',
                   jsonb_strip_nulls(jsonb_build_object(
                       'objective', tx.objective, 'strategy', tx.strategy,
                       'segment_scope', 'series-level prospectus text repeated on each class',
                       'accession_number', tx.adsh,
                       'source', 'SEC N-1A prospectus XBRL')),
                   %s, now()
            FROM funds f JOIN stg_rr_text tx ON tx.series_id = f.sec_series_id
            WHERE f.source_id = %s"""),
            (SOURCE_ID, URL_RR, SOURCE_ID))
        result["prospectus_snapshots"] = cursor.rowcount

        result["snapshots_written"] = sum(result.get(key, 0) for key in (
            "inception_snapshots", "summary_snapshots", "expense_snapshots",
            "performance_snapshots", "prospectus_snapshots"))
        if dry_run:
            connection.rollback()
            return result

        cursor.execute("""
            UPDATE funds f SET inception_date = s.inception
            FROM stg_rr s
            WHERE s.class_id = f.source_fund_id AND f.source_id = %s
              AND f.inception_date IS NULL AND s.inception IS NOT NULL""", (SOURCE_ID,))
        result["inception_filled"] = cursor.rowcount
        if fill_tickers:
            cursor.execute("""
                UPDATE funds f SET ticker = s.ticker
                FROM stg_rr s
                WHERE s.class_id = f.source_fund_id AND f.source_id = %s
                  AND f.ticker IS NULL AND s.ticker IS NOT NULL
                  AND NOT EXISTS (SELECT 1 FROM funds o WHERE o.domicile_country = 'US'
                                  AND upper(o.ticker) = s.ticker)
                  AND (SELECT count(*) FROM stg_rr t WHERE t.ticker = s.ticker) = 1""", (SOURCE_ID,))
            result["tickers_filled"] = cursor.rowcount
        connection.commit()
    result["finished_at"] = datetime.now(timezone.utc).isoformat()
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "sec_rr_profile_last_run.json").write_text(json.dumps(result, indent=2, default=str) + "\n")
    return result


URL_RR = ("https://www.sec.gov/data-research/sec-markets-data/"
          "mutual-fund-prospectus-riskreturn-summary-data-sets")
