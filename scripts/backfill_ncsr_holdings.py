"""Import official portfolio holdings from SEC N-CSR / N-CSRS schedules.

Funds that are absent from the DERA N-PORT bulk archives still file annual and
semi-annual shareholder reports under Form N-CSR/N-CSRS.  Item 7 of those
reports contains a physically filed ``Schedule of Investments`` with security
names, quantities and market values.  This script reads the latest report for
each registrant, resolves the series from the filing text, and attaches the
filed holdings to every local share class of that series that currently has no
holdings.  Existing holdings are never changed.

Usage::

    ./.venv/bin/python scripts/backfill_ncsr_holdings.py --limit-ciks 5 --dry-run
    ./.venv/bin/python scripts/backfill_ncsr_holdings.py --limit-ciks 20
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from app.config import database_url
from backfill_ncsr_nav import (
    _TableParser,
    _document_path,
    _fallback_series,
    _grid,
    _latest_filings,
    _plain_text,
    _submissions,
)


def _holdings_tables(text: str) -> list[str]:
    """Return HTML tables with a filed holdings value column."""
    output: list[str] = []
    for match in re.finditer(r"<table\b.*?</table>", text, re.S | re.I):
        table = match.group(0)
        if "value" not in _plain_text(table).lower():
            continue
        parser_instance = _TableParser()
        parser_instance.feed(table)
        if _header_info(_grid(parser_instance.rows)):
            output.append(table)
    return output

SOURCE_ID = "sec_ncsr_holdings"
SOURCE_NAME = "SEC Form N-CSR/N-CSRS Schedule of Investments - filed holdings"


def _decimal(value: str) -> float | None:
    text = value.strip().replace("$", "").replace(",", "").replace("\u2014", "").replace("\u2013", "")
    if not text or text.lower() in {"n a", "na", "not applicable", "-", "--"}:
        return None
    if text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1]
    try:
        number = float(text)
    except ValueError:
        return None
    if number == 0 or abs(number) > 1e15:
        return None
    return number


def _header_info(
    grid: list[dict[int, str]],
) -> tuple[int, int, int | None, str | None, int] | None:
    """Return (header_index, value_column, quantity_column, quantity_unit, value_scale)."""
    for index, row in enumerate(grid[:5]):
        cells = [(column, text.strip().lower()) for column, text in row.items() if text.strip()]
        value_columns = [(column, text) for column, text in cells
                         if text in {"value", "market value", "value ($)", "value (000)"}]
        if not value_columns:
            continue
        value_column = max(column for column, _ in value_columns)
        # "(000)" is an explicit filed unit, not an inferred value.
        value_scale = 1000 if any("(000)" in text for _, text in value_columns) else 1
        quantity_column: int | None = None
        quantity_unit: str | None = None
        for column, text in cells:
            if text == "shares":
                quantity_column, quantity_unit = column, "SH"
                break
            if text.startswith("principal amount"):
                quantity_column, quantity_unit = column, "P000"
                break
        return index, value_column, quantity_column, quantity_unit, value_scale
    return None


def _parse_schedule(
    grid: list[dict[int, str]],
    series: str,
) -> list[tuple[int, str, float | None, str | None, float, str | None]]:
    """Return (index, security_name, quantity, unit, market_value, currency)."""
    info = _header_info(grid)
    if not info:
        return []
    header_index, value_column, quantity_column, quantity_unit, value_scale = info
    output: list[tuple[int, str, float | None, str | None, float, str | None]] = []
    for row in grid[header_index + 1:]:
        text = " ".join(row.values()).strip()
        if not text or "total" in text.lower()[:40]:
            continue
        values = [(column, raw) for column, raw in row.items()
                  if column != quantity_column and _decimal(raw) is not None]
        if not values:
            continue
        value_column_raw = row.get(value_column, "")
        market_value = _decimal(value_column_raw)
        if market_value is None:
            market_value = values[-1][1] and _decimal(values[-1][1])
        if market_value is None:
            continue
        # Security name is the first non-numeric cell in the row.
        name = ""
        for column in sorted(row):
            raw = row[column].strip()
            if not raw:
                continue
            if _decimal(raw) is not None:
                continue
            if re.fullmatch(r"[\d%/.\-()]+", raw):
                continue
            if len(raw) < 3:
                continue
            name = raw
            break
        if not name or len(name) > 500:
            continue
        if name.lower().startswith(("see accompanying", "the accompanying", "notes to")):
            continue
        # A category heading has the same text in every column.
        filled = [value.strip() for value in row.values() if value.strip()]
        if filled and all(value == filled[0] for value in filled):
            continue
        quantity: float | None = None
        unit = quantity_unit
        if quantity_column is not None and quantity_unit == "SH":
            quantity = _decimal(row.get(quantity_column, ""))
        # Principal amounts are filed in thousands; keep the raw number out of
        # the quantity field so no implied conversion is published.
        if quantity_unit == "P000":
            quantity, unit = None, None
        market_value *= value_scale
        currency = "USD" if "$" in value_column_raw else None
        output.append((len(output) + 1, name[:500], quantity, unit, market_value, currency))
    return output


def _local_series(connection: psycopg.Connection, ciks: list[str]) -> dict[str, dict[str, list[int]]]:
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT f.sec_cik, s.payload->>'series_name', f.id
            FROM funds f
            JOIN fund_profile_snapshots s ON s.fund_id = f.id AND s.dataset = 'summary'
            WHERE f.domicile_country = 'US'
              AND f.sec_cik = ANY(%s)
              AND COALESCE(s.payload->>'series_name', '') <> ''
        """, (ciks,))
        rows = cursor.fetchall()
    result: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for cik, series, fund_id in rows:
        result[cik][series].append(fund_id)
    return result


def _target_funds(connection: psycopg.Connection) -> set[int]:
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT f.id FROM funds f
            WHERE f.domicile_country = 'US'
              AND f.sec_cik IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM portfolio_holdings h WHERE h.fund_id = f.id)
        """)
        return {row[0] for row in cursor.fetchall()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit-ciks", type=int)
    parser.add_argument("--cik", action="append")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db_url = database_url().replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(db_url) as connection, connection.cursor() as cursor:
        target_funds = _target_funds(connection)
        cursor.execute("""
            SELECT DISTINCT f.sec_cik FROM funds f
            WHERE f.domicile_country = 'US'
              AND f.sec_cik IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM portfolio_holdings h WHERE h.fund_id = f.id)
            ORDER BY f.sec_cik
        """)
        ciks = [row[0] for row in cursor.fetchall()]
        if args.cik:
            wanted = {cik.zfill(10) for cik in args.cik}
            ciks = [cik for cik in ciks if cik in wanted]
        if args.limit_ciks:
            ciks = ciks[:args.limit_ciks]
        print(json.dumps({"registrants_targeted": len(ciks), "no_holding_funds": len(target_funds)}), flush=True)

        local = _local_series(connection, ciks)
        pending: list[tuple[int, date, str, int, str, float | None, str | None, float, str | None, str, str]] = []
        index_counter: dict[tuple[int, date], int] = defaultdict(int)
        stats: dict[str, int] = defaultdict(int)
        for index, cik in enumerate(ciks, 1):
            try:
                submissions = _submissions(cik, refresh=args.refresh)
            except Exception as error:  # noqa: BLE001
                stats["submission_errors"] += 1
                print(f"submission error {cik}: {error}", flush=True)
                continue
            filings = _latest_filings(submissions)
            if not filings:
                stats["no_report"] += 1
                continue
            series_map = local.get(cik, {})
            if not series_map:
                stats["no_local_series"] += 1
                continue
            series_names = list(series_map)
            for filing in filings:
                report_date_text = filing.get("reportDate") or filing.get("filingDate") or ""
                try:
                    report_date = date.fromisoformat(report_date_text[:10])
                except ValueError:
                    continue
                name = filing.get("primaryDocument") or ""
                if not name.lower().endswith((".htm", ".html", ".xml")):
                    continue
                try:
                    path = _document_path(cik, filing["accessionNumber"], name, refresh=args.refresh)
                except Exception as error:  # noqa: BLE001
                    stats["download_errors"] += 1
                    print(f"download error {cik}: {error}", flush=True)
                    continue
                text = path.read_text(errors="replace")
                source_url = (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
                              f"{filing['accessionNumber'].replace('-', '')}/{name}")
                table_cursor = 0
                plain_buffer = ""
                for table in _holdings_tables(text):
                    table_index = text.find(table, table_cursor)
                    if table_index < 0:
                        continue
                    fallback, plain_buffer = _fallback_series(
                        text, table, table_cursor, plain_buffer, series_names,
                    )
                    table_cursor = table_index + len(table)
                    if not fallback:
                        continue
                    parser_instance = _TableParser()
                    parser_instance.feed(table)
                    grid = _grid(parser_instance.rows)
                    holdings = _parse_schedule(grid, fallback)
                    if not holdings:
                        continue
                    fund_ids = [fund_id for fund_id in series_map.get(fallback, []) if fund_id in target_funds]
                    if not fund_ids:
                        continue
                    for fund_id in fund_ids:
                        for _table_index, security_name, quantity, unit, market_value, currency in holdings:
                            key = (fund_id, report_date)
                            index_counter[key] += 1
                            pending.append((fund_id, report_date, source_url, index_counter[key],
                                            security_name, quantity, unit, market_value,
                                            currency, filing["accessionNumber"], SOURCE_ID))
                            stats["candidates"] += 1
            if index % 10 == 0 or index == len(ciks):
                print(json.dumps({"processed": index, "total": len(ciks), "candidates": len(pending), **stats}), flush=True)

        print(json.dumps({"candidates": len(pending), **stats}, indent=2), flush=True)
        if args.dry_run or not pending:
            connection.rollback()
            return

        cursor.execute("""
            INSERT INTO sources (source_id, country_code, organization, source_name, endpoint_url,
                                 verification_status, integration_status, license_status)
            VALUES (%s, 'US', 'U.S. Securities and Exchange Commission', %s,
                    'https://www.sec.gov/edgar/search/', 'Usable Fund Data Confirmed', 'Integrated', 'Unknown')
            ON CONFLICT (source_id) DO UPDATE SET source_name = EXCLUDED.source_name,
                endpoint_url = EXCLUDED.endpoint_url
        """, (SOURCE_ID, SOURCE_NAME))
        cursor.execute("""
            CREATE TEMP TABLE stg_ncsr_holdings (
                fund_id integer, reporting_date date, source_url text, holding_index integer,
                security_name text, quantity numeric, unit text, market_value numeric,
                market_value_currency text, accession_number text, data_source text
            ) ON COMMIT DROP
        """)
        with cursor.copy("COPY stg_ncsr_holdings FROM STDIN") as copy:
            for row in pending:
                copy.write_row(row)
        cursor.execute("""
            INSERT INTO portfolio_holdings
                (fund_id, reporting_date, source_url, holding_index, security_name, quantity,
                 unit, market_value, market_value_currency, accession_number, data_source)
            SELECT fund_id, reporting_date, source_url, holding_index, security_name, quantity,
                   unit, market_value, market_value_currency, accession_number, data_source
            FROM stg_ncsr_holdings
            ORDER BY fund_id, reporting_date, holding_index
            ON CONFLICT (fund_id, reporting_date, holding_index) DO NOTHING
        """)
        written = cursor.rowcount
        connection.commit()
        print(json.dumps({"holding_rows_written": written, "candidates": len(pending)}, indent=2))


if __name__ == "__main__":
    main()
