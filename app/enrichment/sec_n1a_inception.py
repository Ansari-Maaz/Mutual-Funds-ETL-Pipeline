"""Fill share-class inception dates from N-1A prospectus narrative text.

The SEC risk/return XBRL data set (``sync-sec-rr-profiles``) publishes returns,
fees and tickers for a class but not the date the class began operations, and
the tailored shareholder report only carries ``PerfInceptionDate`` for some
filings. The prospectus itself is the official document that states it, and in
practice filers write either

    "Class A shares commenced operations on January 2, 2019"
    "The Fund has been in operation since June 30, 2011"

This module reads the primary document of the 485/497 filings already indexed
by the risk/return data set and records the date only when the sentence names
the class (or the series, when the series has a single class). It never guesses
from a year alone, from a performance period, or from a neighbouring fund.

Text is cached per accession under ``data/raw/united_states/n1a_docs`` so a
replay makes no network requests, and every value keeps the accession, filing
date and the sentence it came from.
"""
from __future__ import annotations

import csv
import gzip
import html
import json
import re
import zipfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

import urllib.request
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import user_agent
from app.db.session import SessionLocal
from app.models.schema import Fund, FundProfileSnapshot, Source

SOURCE_ID = "sec_n1a_prospectus_inception"
ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/united_states"
RR_RAW = RAW / "rr"
DOC_RAW = RAW / "n1a_docs"
SUBMISSION_RAW = RAW / "edgar_submissions"
SOURCE_PAGE = "https://www.sec.gov/data-research/sec-markets-data/information-about-registered-investment-companies"

MONTHS = ("January|February|March|April|May|June|July|August|September|October|November|December")
DATE_TEXT = rf"(?:{MONTHS})\s+\d{{1,2}},\s+\d{{4}}"

# Each pattern anchors on the event and its full calendar date. The subject is
# taken from the same sentence before the verb, so the regex stays linear on
# multi-megabyte prospectuses. A bare year is deliberately not accepted.
EVENTS = [
    ("commenced_operations", re.compile(
        rf"(?:commenced|began|started)\s+(?:investment\s+)?operations\s+(?:on|as of)\s+({DATE_TEXT})",
        re.I)),
    ("in_operation_since", re.compile(
        rf"(?:has|have)\s+been\s+in\s+operation\s+since\s+({DATE_TEXT})", re.I)),
    ("since_inception", re.compile(
        rf"(?:since|from)\s+(?:its|the)\s+inception\s+(?:on|in)\s+({DATE_TEXT})", re.I)),
    ("established_on", re.compile(
        rf"was\s+(?:established|organized|formed)\s+(?:on|in)\s+({DATE_TEXT})", re.I)),
]

_PLACEHOLDER = {"N/A", "NA", "N.A.", "NONE", "-", "--"}
_NOT_STARTED = re.compile(r"\b(?:has|have|had)\s+not\s+(?:yet\s+)?commenced", re.I)
_SENTENCE_TABLE = re.compile(r"[$]|[%]|\b\d{1,2}/\d{1,2}/\d{2,4}\b")


def _clean(value: Any) -> str | None:
    text = " ".join(str(value or "").split())
    return text or None


def _normalized(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def _archive_key(path: Path) -> tuple[int, int, int]:
    """Sort RR archives newest first across ``2026q3`` and ``2026-10`` names."""
    name = path.name
    year = int(re.search(r"(\d{4})", name).group(1))
    month = re.search(r"q([1-4])", name)
    if month:
        return (year, int(month.group(1)) * 3, 0)
    month = re.search(r"-(\d{2})_", name)
    if month:
        return (year, int(month.group(1)), 1)
    return (year, 0, 2)


def rr_archives(limit: int | None = None) -> list[Path]:
    archives = sorted(RR_RAW.glob("*_rr1.zip"), key=_archive_key, reverse=True)
    return archives[:limit] if limit else archives


def _zip_rows(archive: Path, member: str) -> Iterator[dict[str, str]]:
    if not archive.exists():
        return iter(())
    with zipfile.ZipFile(archive) as bundle:
        if member not in bundle.namelist():
            return iter(())
        with bundle.open(member) as raw:
            stream = (line.decode("utf-8", "replace") for line in raw)
            yield from csv.DictReader(stream, delimiter="\t")


def _date(value: str | None) -> date | None:
    text = (value or "").strip()
    if not text:
        return None
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _sentence(text: str, start: int, end: int) -> str:
    """Return the sentence around a match without splitting the whole document."""
    left = max(text.rfind(". ", 0, start), text.rfind("; ", 0, start),
               text.rfind("? ", 0, start), text.rfind("! ", 0, start),
               text.rfind("\n", 0, start))
    right_candidates = [pos + 1 for pos in (text.find(". ", end), text.find("; ", end),
                                            text.find("\n", end)) if pos != -1]
    right = min(right_candidates) if right_candidates else len(text)
    return _clean(text[left + 1:right]) or ""


_TABLE_MARKERS = re.compile(r"[%]|[$]|\b\d{4}\b|\bpast\b|\byears\b|\bchart\b|\bquarter\b", re.I)


def _clean_subject(text: str) -> str:
    """Return the short phrase immediately before a verb, or '' for table text.

    A sentence-like subject cannot contain percentages, dollar amounts, years
    or performance-table headers. Those only appear when the 160-character
    window has crossed into a neighbouring row of a prospectus table.
    """
    subject = _clean(text)
    if not subject or len(subject) > 120 or _TABLE_MARKERS.search(subject):
        return ""
    return subject


def find_candidates(text: str) -> list[dict[str, Any]]:
    """Return every dated inception sentence, with the subject before the verb."""
    candidates: list[dict[str, Any]] = []
    for name, pattern in EVENTS:
        for match in pattern.finditer(text):
            parsed = _date(match.group(1))
            if parsed is None:
                continue
            start = match.start()
            left = max(text.rfind(". ", 0, start), text.rfind("; ", 0, start),
                       text.rfind("\n", 0, start))
            subject = _clean_subject(text[max(left + 1, start - 120):start])
            if not subject:
                continue
            sentence = _sentence(text, start, match.end())
            if (_NOT_STARTED.search(sentence)
                    and not re.search(r"(?:has|have|had)\s+been\s+in\s+operation", sentence, re.I)):
                continue
            # A prose inception sentence is short and free of table noise. Long
            # stretches with currency or percentage figures are financial-table
            # context, not a class commencement statement.
            if len(sentence) > 320 or _SENTENCE_TABLE.search(sentence):
                continue
            candidates.append({
                "pattern": name, "subject": subject, "date": parsed,
                "offset": start, "snippet": (sentence or subject)[:400],
            })
    candidates.sort(key=lambda item: item["offset"])
    return candidates


# Class labels that carry no distinguishing meaning on their own.
_GENERIC_LABELS = {"shares", "share", "class", "fund", "portfolio"}


def _class_matches(subject: str, class_name: str | None) -> bool:
    """True when the sentence subject is the class, not a nearby fund.

    The subject is the short phrase immediately before the verb. A genuine
    class label sits at its start ("Class A shares of the Fund ...") or at its
    end ("Investor Shares ..."). Matching anywhere in the phrase would attribute
    another class's statement to this one.
    """
    token = _normalized(class_name)
    if not token or token in _GENERIC_LABELS or len(token) < 5:
        return False
    normalized = _normalized(subject)
    if not normalized:
        return False
    if normalized.endswith(token) or normalized.startswith(token):
        return True
    # "Class A shares of the Fund" — allow a few trailing generic words.
    if token.startswith("class"):
        return bool(re.match(rf"^{re.escape(token)}(?:shares?|ofthefund|ofthetrust)?$", normalized))
    return False


def _names_the_fund(subject: str, series_tokens: list[str]) -> bool:
    """True when a short subject names this series and mentions no share class."""
    if len(subject) > 80:
        return False
    if "class" in subject or "shares" in subject:
        return False
    return any(token and token in subject for token in series_tokens)


def _series_tokens(series_name: str | None) -> list[str]:
    name = _clean(series_name)
    if not name:
        return []
    normalized = _normalized(name)
    tokens = {normalized}
    stripped = re.sub(r"(fund|portfolio|trust|series)$", "", normalized).strip()
    if len(stripped) >= 8:
        tokens.add(stripped)
    return [token for token in tokens if len(token) >= 8]


def resolve(candidates: Iterable[dict[str, Any]], *, class_name: str | None,
            series_name: str | None, single_class: bool,
            filed: date | None) -> dict[str, Any] | None:
    """Pick the candidate that names this class, else the series when unique."""
    series_tokens = _series_tokens(series_name)
    class_match = None
    series_match = None
    for item in candidates:
        if filed and item["date"] > filed:
            continue
        subject = _normalized(item["subject"])
        if not subject:
            continue
        if _class_matches(item["subject"], class_name):
            class_match = item
            break
        if series_match is None and _names_the_fund(subject, series_tokens):
            series_match = item
    if class_match:
        return {**class_match, "scope": "share_class"}
    if series_match and single_class:
        return {**series_match, "scope": "series"}
    return None


def _unwrapped(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text)))


def _request(url: str) -> bytes:
    headers = {"User-Agent": user_agent(), "Accept-Encoding": "gzip, deflate"}
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=180) as response:
        payload = response.read()
        if response.headers.get("Content-Encoding") == "gzip":
            payload = gzip.decompress(payload)
    return payload


def _submissions(cik: int) -> dict[str, Any]:
    SUBMISSION_RAW.mkdir(parents=True, exist_ok=True)
    cache = SUBMISSION_RAW / f"CIK{cik:010d}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    payload = _request(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
    cache.write_bytes(payload)
    return json.loads(payload)


def _submission_blocks(cik: int) -> Iterator[dict[str, Any]]:
    """Yield the recent filing block, then each older page only on demand."""
    payload = _submissions(cik)
    yield payload["filings"]["recent"]
    for item in payload["filings"].get("files", []):
        name = item.get("name") or ""
        if not name:
            continue
        cache = SUBMISSION_RAW / f"CIK{cik:010d}_{name}.json"
        if cache.exists():
            yield json.loads(cache.read_text())
            continue
        body = _request(f"https://data.sec.gov/submissions/{name}")
        cache.write_bytes(body)
        yield json.loads(body)


def _primary_document(cik: int, accession: str) -> tuple[str | None, dict[str, Any]]:
    for block in _submission_blocks(cik):
        accessions = list(block.get("accessionNumber") or [])
        if accession in accessions:
            index = accessions.index(accession)
            return block["primaryDocument"][index], {}
    return None, {}


def document_text(cik: int, accession: str, *, refresh: bool = False) -> str | None:
    """Return cached plain text of the filing's primary document."""
    DOC_RAW.mkdir(parents=True, exist_ok=True)
    cache = DOC_RAW / f"{accession}.txt.gz"
    if cache.exists() and not refresh:
        return gzip.decompress(cache.read_bytes()).decode("utf-8")
    document, _ = _primary_document(cik, accession)
    if not document:
        return None
    url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/{document}"
    text = _unwrapped(_request(url).decode("utf-8", "replace"))
    cache.write_bytes(gzip.compress(text.encode("utf-8")))
    return text


def _targets() -> dict[str, dict[str, Any]]:
    """class id -> local fund row for funds that still need an inception date."""
    with SessionLocal() as session:
        rows = session.execute(
            select(Fund.id, Fund.source_fund_id, Fund.name, Fund.sec_series_id)
            .where(Fund.domicile_country == "US", Fund.inception_date.is_(None))).all()
        counts: dict[str, int] = defaultdict(int)
        for _, series in session.execute(select(Fund.id, Fund.sec_series_id).where(
                Fund.domicile_country == "US", Fund.sec_series_id.is_not(None))).all():
            counts[series] += 1
    return {
        class_id: {"fund_id": fund_id, "name": name, "series_id": series,
                   "class_count": counts.get(series, 0)}
        for fund_id, class_id, name, series in rows if class_id
    }


def _archive_index(archives: list[Path], targets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Map target class ids to their newest risk/return filing."""
    chosen: dict[str, dict[str, Any]] = {}
    filings: dict[str, dict[str, Any]] = {}
    for archive in archives:
        scn = list(_zip_rows(archive, "scn.tsv"))
        if not scn:
            continue
        submissions = {row["adsh"]: row for row in _zip_rows(archive, "sub.tsv")
                       if row.get("adsh")}
        for row in scn:
            class_id = (row.get("classid") or "").strip()
            if class_id not in targets or class_id in chosen:
                continue
            adsh = row.get("adsh")
            submission = submissions.get(adsh)
            if not adsh or not submission:
                continue
            chosen[class_id] = {
                "accession": adsh, "cik": int(submission["cik"]),
                "form": submission.get("form"), "filed": _date(submission.get("filed")),
                "series_id": row.get("seriesid"), "series_name": row.get("seriesname"),
                "class_name": row.get("classname"),
            }
            filings[adsh] = chosen[class_id]
    return {"classes": chosen, "filings": filings}


def _ensure_source(session) -> None:
    source = {"source_id": SOURCE_ID, "country_code": "US",
              "organization": "U.S. Securities and Exchange Commission",
              "source_name": "Form N-1A prospectus narrative (485/497 primary documents)",
              "endpoint_url": SOURCE_PAGE,
              "verification_status": "Usable Fund Data Confirmed",
              "integration_status": "Integrated", "license_status": "Public domain"}
    session.execute(pg_insert(Source).values(**source).on_conflict_do_update(
        index_elements=[Source.source_id],
        set_={key: value for key, value in source.items() if key != "source_id"}))


def sync_sec_n1a_inception(*, archives: int = 4, workers: int = 6, dry_run: bool = False,
                           refresh: bool = False, limit: int | None = None) -> dict[str, Any]:
    """Record class inception dates stated in N-1A prospectuses."""
    targets = _targets()
    index = _archive_index(rr_archives(archives), targets)
    filings = index["filings"]
    if limit:
        keep = set(list(filings)[:limit])
        filings = {key: value for key, value in filings.items() if key in keep}
        index["classes"] = {key: value for key, value in index["classes"].items()
                            if value["accession"] in keep}
    result: dict[str, Any] = {
        "source_id": SOURCE_ID, "archives": archives, "funds_targeted": len(targets),
        "filings_indexed": len(filings), "classes_indexed": len(index["classes"]),
        "documents_read": 0, "documents_with_candidates": 0, "classes_resolved": 0,
        "funds_updated": 0, "snapshots_written": 0, "errors": [], "dry_run": dry_run,
    }

    texts: dict[str, str | None] = {}

    def fetch(accession: str) -> tuple[str, str | None]:
        try:
            return accession, document_text(filings[accession]["cik"], accession, refresh=refresh)
        except Exception as error:  # noqa: BLE001 - one bad filing must not stop the run
            return accession, f"__error__:{type(error).__name__}: {error}"

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for accession, text in pool.map(fetch, list(filings)):
            if text and text.startswith("__error__:"):
                result["errors"].append({"accession": accession, "error": text[10:]})
                continue
            texts[accession] = text
    result["documents_read"] = sum(1 for text in texts.values() if text)

    candidates = {accession: find_candidates(text) for accession, text in texts.items() if text}
    result["documents_with_candidates"] = sum(1 for items in candidates.values() if items)

    resolved: dict[str, dict[str, Any]] = {}
    for class_id, target in targets.items():
        filing = index["classes"].get(class_id)
        if not filing:
            continue
        items = candidates.get(filing["accession"]) or []
        if not items:
            continue
        choice = resolve(items, class_name=filing["class_name"],
                         series_name=filing["series_name"],
                         single_class=target["class_count"] <= 1, filed=filing["filed"])
        if not choice:
            continue
        resolved[class_id] = {**choice, "filing": filing, "target": target}

    result["classes_resolved"] = len(resolved)
    if dry_run:
        result["samples"] = [
            {"class_id": class_id, "date": item["date"].isoformat(),
             "scope": item["scope"], "class_name": item["filing"]["class_name"],
             "snippet": (item["snippet"] or "")[:180]}
            for class_id, item in list(resolved.items())[:8]]
        return result

    if not resolved:
        return result

    with SessionLocal() as session:
        _ensure_source(session)
        snapshots: list[dict[str, Any]] = []
        updates: list[dict[str, Any]] = []
        for class_id, item in resolved.items():
            filing = item["filing"]
            fund_id = item["target"]["fund_id"]
            source_url = (f"https://www.sec.gov/Archives/edgar/data/{filing['cik']}/"
                          f"{filing['accession'].replace('-', '')}/")
            snapshots.append({
                "fund_id": fund_id, "source_id": SOURCE_ID,
                "dataset": "n1a_inception",
                "source_report_date": filing["filed"],
                "snapshot_key": f"{class_id}:n1a_inception"[:64],
                "payload": {
                    "inception_date": item["date"].isoformat(),
                    "scope": item["scope"],
                    "class_id": class_id,
                    "class_name": filing["class_name"],
                    "series_id": filing["series_id"],
                    "series_name": filing["series_name"],
                    "statement": item["snippet"],
                    "detection": item["pattern"],
                    "form": filing["form"],
                    "filed": filing["filed"].isoformat() if filing["filed"] else None,
                    "accession_number": filing["accession"],
                    "basis": ("share-class commencement date stated in the prospectus"
                              if item["scope"] == "share_class" else
                              "series commencement date stated in the prospectus; the series has one share class"),
                },
                "source_url": source_url,
            })
            updates.append({"id": fund_id, "inception_date": item["date"]})
        for offset in range(0, len(snapshots), 400):
            chunk = snapshots[offset:offset + 400]
            statement = pg_insert(FundProfileSnapshot.__table__).values(chunk)
            session.execute(statement.on_conflict_do_update(
                constraint="uq_fund_profile_source_snapshot",
                set_={"source_report_date": statement.excluded.source_report_date,
                      "payload": statement.excluded.payload,
                      "source_url": statement.excluded.source_url,
                      "retrieved_at": datetime.now(timezone.utc)}))
        result["snapshots_written"] = len(snapshots)

        applied = 0
        for item in updates:
            outcome = session.execute(
                update(Fund).where(Fund.id == item["id"], Fund.inception_date.is_(None))
                .values(inception_date=item["inception_date"]))
            applied += outcome.rowcount or 0
        session.commit()
        result["funds_updated"] = applied
    return result
