"""Import official period-end NAVs from SEC N-CSR / N-CSRS reports.

Many share classes have no ticker and no daily NAV feed, but every open-end
fund's annual and semi-annual report contains a Statement of Assets and
Liabilities that files ``Net asset value per share`` for each share class.  This
script reads the latest report period available for each registrant, parses the
class-level NAV rows from the official HTML filing, maps them to the local SEC
class using the ``summary`` snapshot (series_name + class_name), and stores a
single period-end USD NAV observation.  Values are never derived from net
assets or shares and existing NAV observations are never changed.

Usage::

    ./.venv/bin/python scripts/backfill_ncsr_nav.py --limit-ciks 20
    ./.venv/bin/python scripts/backfill_ncsr_nav.py --dry-run
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.error
from collections import defaultdict
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import database_url
from app.holdings.sec_nport import _request

RAW = ROOT / "data" / "raw" / "united_states" / "ncsr_nav"
SUBMISSIONS = ROOT / "data" / "raw" / "united_states" / "edgar_submissions"
SOURCE_ID = "sec_ncsr_nav"
SOURCE_NAME = "SEC Form N-CSR/N-CSRS Statement of Assets - filed NAV per share"
REPORT_FORMS = {"N-CSR", "N-CSRS"}


class _TableParser(HTMLParser):
    """Collect HTML table rows while preserving colspan/rowspan."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[tuple[str, tuple[int, int]]]] = []
        self._row: list[tuple[str, tuple[int, int]]] | None = None
        self._cell: list[str] | None = None
        self._span = (1, 1)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []
            self._span = (
                _positive_int(attributes.get("colspan")),
                _positive_int(attributes.get("rowspan")),
            )

    def handle_endtag(self, tag: str) -> None:
        if tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None
        elif tag in {"td", "th"} and self._cell is not None and self._row is not None:
            self._row.append((" ".join("".join(self._cell).split()), self._span))
            self._cell = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


def _positive_int(value: Any) -> int:
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return 1


def _grid(rows: list[list[tuple[str, tuple[int, int]]]]) -> list[dict[int, str]]:
    """Expand a parsed table into a rectangular grid, including rowspans."""
    carry: dict[int, tuple[str, int]] = {}
    output: list[dict[int, str]] = []
    for row in rows:
        grid: dict[int, str] = {}
        column = 0
        for text, (colspan, rowspan) in row:
            while column in grid or column in carry:
                column += 1
            for offset in range(colspan):
                grid[column + offset] = text
                if rowspan > 1:
                    carry[column + offset] = (text, rowspan - 1)
            column += colspan
        for column, (text, remaining) in list(carry.items()):
            if column not in grid:
                grid[column] = text
            if remaining <= 1:
                del carry[column]
            else:
                carry[column] = (text, remaining - 1)
        if grid:
            output.append(grid)
    return output


def _normalise(value: str) -> str:
    text = re.sub(r"\([a-z0-9]{1,3}\)\s*$", "", value.strip(), flags=re.I)
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _series_score(header: str, series: str) -> float:
    left = _normalise(header)
    right = _normalise(series)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    if left in right or right in left:
        return 0.95
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    return len(left_tokens & right_tokens) / max(1, len(left_tokens | right_tokens))


def _class_key(value: str, series: str | None = None) -> str:
    text = value
    if series:
        text = re.sub(re.escape(series), " ", text, flags=re.I)
    text = re.sub(r"\(([a-z0-9]{1,8}(?:-[a-z0-9]{1,8})*)\)\s*$", r" \1 ", text, flags=re.I)
    text = re.sub(r"\b(class|share|shares|series)\b", " ", text, flags=re.I)
    text = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return " ".join(text.split())


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
    if number <= 0 or number > 1_000_000:
        return None
    return number


def _spans(row: dict[int, str]) -> list[tuple[str, int, int]]:
    spans: list[tuple[str, int, int]] = []
    previous: tuple[str, int, int] | None = None
    for column in sorted(row):
        text = row[column].strip()
        if not text:
            continue
        if previous and previous[0] == text and previous[2] == column - 1:
            spans[-1] = (text, previous[1], column)
        else:
            spans.append((text, column, column))
        previous = spans[-1]
    return spans


def _header_row(
    grid: list[dict[int, str]],
    series_names: list[str],
) -> tuple[int, list[tuple[str, int, int, str, float]]] | None:
    best: tuple[int, list[tuple[str, int, int, str, float]]] | None = None
    # The column header is always near the top of a statement-of-assets
    # table.  Restricting the search avoids mistaking a later numeric row
    # (for example a maturity year) for a fund header.
    for index, row in enumerate(grid[:4]):
        matches: list[tuple[str, int, int, str, float]] = []
        for text, start, end in _spans(row):
            scores = sorted(((_series_score(text, series), series) for series in series_names), reverse=True)
            if not scores:
                continue
            score, series = scores[0]
            if score < 0.3:
                continue
            if len(scores) > 1 and score - scores[1][0] < 0.08:
                continue
            matches.append((text, start, end, series, score))
        if len(matches) >= 2 and (best is None or len(matches) > len(best[1])):
            best = (index, matches)
    return best


def _class_label(row: dict[int, str]) -> str | None:
    """Return the share-class token from the leading cells of a row."""
    first = " ".join(row.get(column, "") for column in sorted(row)[:2]).strip()
    class_match = re.search(r"(?:share\s+)?class\s+([a-z0-9]+(?:-[a-z0-9]+)*)", first, re.I)
    if class_match:
        return class_match.group(1)
    paren_match = re.search(r"\(([a-z0-9]{1,8}(?:-[a-z0-9]{1,8})*)\)\s*$", first, re.I)
    if paren_match:
        return paren_match.group(1)
    named_match = re.match(r"([a-z][a-z ]{1,20}?)\s+class\b", first, re.I)
    if named_match:
        return named_match.group(1).strip()
    if re.fullmatch(r"[a-z0-9]{1,8}(?:-[a-z0-9]{1,8})*", first, re.I):
        return first
    return None


def _header_values(
    row: dict[int, str],
    header: list[tuple[str, int, int, str, float]],
) -> list[tuple[str, int, int, str, float]]:
    """Return one filed numeric value per matched fund column."""
    output: list[tuple[str, int, int, str, float]] = []
    for text, start, end, series, _score in header:
        columns = [start] if start == end else list(range(start, end + 1))
        values = [_decimal(row[column]) for column in columns if column in row]
        values = [value for value in values if value is not None]
        if not values and start != end and end + 1 in row:
            value = _decimal(row[end + 1])
            values = [value] if value is not None else []
        if len(values) != 1:
            continue
        output.append((text, start, end, series, values[0]))
    return output


def _nav_rows(
    grid: list[dict[int, str]],
    header: list[tuple[str, int, int, str, float]],
) -> list[tuple[str, int, int, str, str, float]]:
    """Return (header, start, end, series, class_label, nav) candidates.

    Two official layouts are handled: a single row that names the class (for
    example ``Net asset value per share - Class A``) and a section heading
    ``NET ASSET VALUE PER SHARE:`` followed by one row per class.
    """
    output: list[tuple[str, int, int, str, str, float]] = []
    nav_section = False
    for row in grid:
        row_text = " ".join(" ".join(row.values()).lower().split())
        if "net asset value per share" in row_text:
            values = _header_values(row, header)
            if values:
                label = _class_label(row) or ""
                output.extend(
                    (text, start, end, series, label, value)
                    for text, start, end, series, value in values
                )
                nav_section = False
            else:
                nav_section = True
            continue
        if not nav_section:
            continue
        if "offering price" in row_text or "sales charge" in row_text:
            continue
        values = _header_values(row, header)
        if not values:
            # A text-only row that is not a class row ends the NAV section.
            if not _class_label(row):
                nav_section = False
            continue
        label = _class_label(row)
        if not label:
            continue
        output.extend(
            (text, start, end, series, label, value)
            for text, start, end, series, value in values
        )
    return output


def _class_column_nav_rows(
    grid: list[dict[int, str]],
    series: str,
) -> list[tuple[str, int, int, str, str, float]]:
    """Parse a statement with a ``Class`` column and a ``Net asset value`` column.

    Some registrants (for example AllianceBernstein) put the fund name outside
    the table and list one row per share class with net assets, shares and NAV.
    The NAV is the rightmost filed numeric value in each class row.
    """
    output: list[tuple[str, int, int, str, str, float]] = []
    header_index: int | None = None
    nav_column: int | None = None
    class_column: int | None = None
    for index, row in enumerate(grid[:6]):
        nav_columns = [
            column for column, text in row.items()
            if re.search(r"net\s*asset\s*value", text, re.I)
            and "end of period" not in text.lower()
        ]
        class_columns = [
            column for column, text in row.items()
            if text.strip().lower() == "class"
        ]
        if nav_columns:
            header_index = index
            nav_column = max(nav_columns)
            # Some statements omit a literal "Class" heading; the class label
            # still occupies the first column of each row.
            class_column = min(class_columns) if class_columns else min(row)
            break
    if header_index is None or nav_column is None or class_column is None:
        return output
    for row in grid[header_index + 1:]:
        row_text = " ".join(row.values()).lower()
        if "offering price" in row_text or "sales charge" in row_text:
            continue
        first = row.get(class_column, "") or (row.get(min(row), "") if row else "")
        label = _class_label({0: first})
        if not label:
            continue
        value = _decimal(row.get(nav_column, ""))
        if value is None:
            continue
        output.append(("", nav_column, nav_column, series, label, value))
    return output


def _offering_price_nav_rows(
    grid: list[dict[int, str]],
    series: str,
) -> list[tuple[str, int, int, str, str, float]]:
    """Parse ``net asset value, offering and redemption price per share`` rows.

    These statements place the class label on the preceding row and include the
    filed net assets and share count inside the NAV sentence itself.  The last
    numeric value on the row is the filed NAV per share.
    """
    output: list[tuple[str, int, int, str, str, float]] = []
    current_class: str | None = None
    for row in grid:
        row_text = " ".join(" ".join(row.values()).lower().split())
        if re.search(r"net\s*asset\s*value.{0,80}per\s*share", row_text) and "end of period" not in row_text:
            values = [_decimal(value) for value in row.values()]
            values = [value for value in values if value is not None]
            if current_class and values:
                output.append(("", 0, 0, series, current_class, values[-1]))
            continue
        label = _class_label(row)
        if label and len(row_text) < 100:
            current_class = label
    return output


def _fallback_series(
    text: str,
    table: str,
    cursor: int,
    buffer: str,
    series_names: list[str],
) -> tuple[str | None, str]:
    """Resolve the fund name printed immediately before a statement table."""
    index = text.find(table, cursor)
    if index < 0:
        return None, buffer
    buffer = (buffer + " " + _plain_text(text[cursor:index]))[-20000:]
    matches: list[tuple[int, str]] = []
    for series in series_names:
        position = buffer.lower().rfind(series.lower())
        if position >= 0:
            matches.append((position, series))
    if matches:
        return max(matches)[1], buffer
    if len(series_names) == 1:
        return series_names[0], buffer
    return None, buffer


def _submissions(cik: str, *, refresh: bool) -> dict[str, Any]:
    path = SUBMISSIONS / f"CIK{cik}.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text())
    payload = _request(f"https://data.sec.gov/submissions/CIK{cik}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return json.loads(payload)


def _filing_rows(submissions: dict[str, Any]) -> list[dict[str, str]]:
    recent = (submissions.get("filings") or {}).get("recent") or {}
    columns = ("form", "filingDate", "reportDate", "accessionNumber", "primaryDocument")
    lengths = [len(recent.get(column) or []) for column in columns]
    rows = []
    for index in range(min(lengths) if lengths else 0):
        rows.append({column: (recent.get(column) or [""])[index] for column in columns})
    return rows


def _latest_filings(submissions: dict[str, Any]) -> list[dict[str, str]]:
    rows = [row for row in _filing_rows(submissions)
            if (row.get("form") or "").upper() in REPORT_FORMS and row.get("accessionNumber")]
    if not rows:
        return []
    dates = [row.get("reportDate") or row.get("filingDate") or "" for row in rows]
    latest = max(dates)
    return [row for row in rows if (row.get("reportDate") or row.get("filingDate") or "") == latest]


def _document_path(cik: str, accession: str, name: str, *, refresh: bool) -> Path:
    path = RAW / accession / name
    if path.exists() and not refresh:
        return path
    url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{name}"
    payload = _request(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def _tables_with_nav(text: str) -> list[str]:
    """Return tables whose visible text contains the filed NAV-per-share label.

    The label is frequently split by inline formatting tags, so the raw HTML
    cannot be searched directly.  Tables that do not mention net assets at all
    are skipped before the more expensive tag-stripping pass.
    """
    output: list[str] = []
    for match in re.finditer(r"<table\b.*?</table>", text, re.S | re.I):
        table = match.group(0)
        plain = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", table)).split()).lower()
        if re.search(r"net\s*asset\s*value", plain):
            output.append(table)
    return output


def _plain_text(chunk: str) -> str:
    """Return visible text with HTML entities decoded and whitespace collapsed."""
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", chunk)).split())


def _load_local(session: psycopg.Connection, ciks: list[str]) -> dict[str, dict[str, list[tuple[int, str, str]]]]:
    query = """
        SELECT f.sec_cik, f.id, s.payload->>'series_name', s.payload->>'class_name'
        FROM funds f
        JOIN fund_profile_snapshots s ON s.fund_id = f.id AND s.dataset = 'summary'
        WHERE f.domicile_country = 'US'
          AND f.sec_cik = ANY(%s)
          AND COALESCE(s.payload->>'series_name', '') <> ''
          AND COALESCE(s.payload->>'class_name', '') <> ''
    """
    with session.cursor() as cursor:
        cursor.execute(query, (ciks,))
        rows = cursor.fetchall()
    result: dict[str, dict[str, list[tuple[int, str, str]]]] = defaultdict(lambda: defaultdict(list))
    for cik, fund_id, series, class_name in rows:
        key = _class_key(class_name, series) or _class_key(class_name) or "default"
        result[cik][series].append((fund_id, class_name, key))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit-ciks", type=int, help="Process only the first N registrants")
    parser.add_argument("--cik", action="append", help="Process a specific CIK (repeatable)")
    parser.add_argument("--refresh", action="store_true", help="Redownload cached submissions and filings")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db_url = database_url().replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(db_url) as connection, connection.cursor() as cursor:
        cursor.execute("""
            WITH nav AS (SELECT fund_id FROM nav_observations WHERE nav > 0 GROUP BY 1),
                 reporting AS (
                     SELECT s.fund_id FROM fund_profile_snapshots s
                     WHERE s.dataset = 'filing_status'
                       AND (s.payload->>'reported_in_window')::boolean
                     GROUP BY 1)
            SELECT DISTINCT f.sec_cik
            FROM funds f
            LEFT JOIN nav ON nav.fund_id = f.id
            JOIN reporting r ON r.fund_id = f.id
            WHERE f.domicile_country = 'US'
              AND nav.fund_id IS NULL
              AND f.sec_cik IS NOT NULL
            ORDER BY f.sec_cik
        """)
        ciks = [row[0] for row in cursor.fetchall()]
        if args.cik:
            wanted = {cik.zfill(10) for cik in args.cik}
            ciks = [cik for cik in ciks if cik in wanted]
        if args.limit_ciks:
            ciks = ciks[:args.limit_ciks]
        print(json.dumps({"registrants_targeted": len(ciks)}), flush=True)

        local = _load_local(connection, ciks)
        pending: dict[tuple[int, date], tuple[float, str, str]] = {}
        stats = defaultdict(int)
        for index, cik in enumerate(ciks, 1):
            before = stats["candidates"]
            try:
                submissions = _submissions(cik, refresh=args.refresh)
            except Exception as error:  # noqa: BLE001 - continue other registrants
                stats["submission_errors"] += 1
                print(f"submission error {cik}: {error}", flush=True)
                continue
            filings = _latest_filings(submissions)
            if not filings:
                stats["no_report"] += 1
                print(f"skip {cik}: no N-CSR/N-CSRS in recent filings", flush=True)
                continue
            series_map = local.get(cik, {})
            if not series_map:
                stats["no_local_series"] += 1
                print(f"skip {cik}: no local summary series", flush=True)
                continue
            series_names = list(series_map)
            for filing in filings:
                report_date_text = filing.get("reportDate") or filing.get("filingDate") or ""
                try:
                    report_date = date.fromisoformat(report_date_text[:10])
                except ValueError:
                    stats["bad_report_date"] += 1
                    continue
                name = filing.get("primaryDocument") or ""
                if not name.lower().endswith((".htm", ".html", ".xml")):
                    stats["non_html"] += 1
                    continue
                try:
                    path = _document_path(cik, filing["accessionNumber"], name, refresh=args.refresh)
                except Exception as error:  # noqa: BLE001
                    stats["download_errors"] += 1
                    print(f"download error {cik} {filing['accessionNumber']}: {error}", flush=True)
                    continue
                try:
                    text = path.read_text(errors="replace")
                except OSError:
                    stats["read_errors"] += 1
                    continue
                table_cursor = 0
                plain_buffer = ""
                for table in _tables_with_nav(text):
                    table_index = text.find(table, table_cursor)
                    if table_index < 0:
                        continue
                    fallback, plain_buffer = _fallback_series(
                        text, table, table_cursor, plain_buffer, series_names,
                    )
                    table_cursor = table_index + len(table)
                    table_parser = _TableParser()
                    table_parser.feed(table)
                    grid = _grid(table_parser.rows)
                    header = _header_row(grid, series_names)
                    if header:
                        header_index, header_spans = header
                        candidates = _nav_rows(grid[header_index + 1:], header_spans)
                    elif fallback:
                        candidates = (
                            _class_column_nav_rows(grid, fallback)
                            + _offering_price_nav_rows(grid, fallback)
                        )
                    else:
                        continue
                    for _text, _start, _end, series, label, nav in candidates:
                        key = _class_key(label, series)
                        if not key and len(series_map.get(series, [])) == 1:
                            key = series_map[series][0][2]
                        matches = [row for row in series_map.get(series, []) if row[2] == key]
                        if len(matches) != 1:
                            stats["unmatched_class"] += 1
                            continue
                        fund_id, _class_name, _key = matches[0]
                        source_url = (
                            f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
                            f"{filing['accessionNumber'].replace('-', '')}/{name}"
                        )
                        current = pending.get((fund_id, report_date))
                        if current is None or nav > current[0]:
                            pending[(fund_id, report_date)] = (nav, source_url, filing["accessionNumber"])
                        stats["candidates"] += 1
            if stats["candidates"] == before:
                print(f"skip {cik}: no parsed class NAV in latest report", flush=True)
            if index % 10 == 0 or index == len(ciks):
                print(json.dumps({"processed": index, "total": len(ciks), "candidates": len(pending), **stats}), flush=True)

        print(json.dumps({"candidates": len(pending), **stats}, indent=2), flush=True)
        if args.dry_run:
            connection.rollback()
            return
        if not pending:
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
            CREATE TEMP TABLE stg_ncsr_nav (
                fund_id integer, valuation_date date, nav numeric,
                currency text, source_id text, source_url text, ohlc_basis text
            ) ON COMMIT DROP
        """)
        rows = [
            (fund_id, valuation_date, nav, "USD", SOURCE_ID, source_url,
             "filed_period_end_nav")
            for (fund_id, valuation_date), (nav, source_url, _accession) in pending.items()
        ]
        with cursor.copy("COPY stg_ncsr_nav FROM STDIN") as copy:
            for row in rows:
                copy.write_row(row)
        cursor.execute("""
            INSERT INTO nav_observations
                (fund_id, valuation_date, nav, currency, source_id, source_url, ohlc_basis)
            SELECT fund_id, valuation_date, nav, currency, source_id, source_url, ohlc_basis
            FROM stg_ncsr_nav
            ON CONFLICT (fund_id, valuation_date, currency) DO NOTHING
        """)
        written = cursor.rowcount
        connection.commit()
        print(json.dumps({"nav_rows_written": written, "candidates": len(pending)}, indent=2))


if __name__ == "__main__":
    main()
