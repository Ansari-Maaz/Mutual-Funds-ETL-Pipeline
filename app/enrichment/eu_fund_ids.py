"""Attach share-class ISINs, LEIs and register data to Irish and Luxembourg funds from official EU/UK sources.

Sources (all free, no key):
* ESMA FIRDS full "C" (collective investment) instrument file: ISIN, CFI, currency, issuer LEI, venue, first
  trading date for share classes traded or admitted on EU venues.
* ESMA cross-border funds register (Solr): UCITS/AIF records for IE and LU with fund LEI, manager, status,
  legal framework and marketing countries.
* HMRC offshore reporting funds list (ODS): ISIN per share class with parent (umbrella) and sub-fund name,
  published under the UK Open Government Licence.

Matching is deliberately conservative: Luxembourg joins on LEI (BDE LEI == FIRDS issuer LEI); Ireland has no LEI
in the national register so it joins on exact normalised sub-fund name only and never on umbrella names.
"""
from __future__ import annotations

import collections
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import timeout_seconds, user_agent
from app.db.session import SessionLocal
from app.models.schema import Fund, FundIdentifier, FundProfileSnapshot

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "eu_isin"
FIRDS_INDEX = ("https://registers.esma.europa.eu/solr/esma_registers_firds_files/select?"
               "q=file_name:FULINS_C*&sort=publication_date+desc&rows=1&wt=json&fl=file_name,publication_date,download_link")
CBDIF = "https://registers.esma.europa.eu/solr/esma_registers_funds_cbdif/select"
HMRC_PAGE = "https://www.gov.uk/government/publications/offshore-funds-list-of-reporting-funds"
SOURCE_FIRDS, SOURCE_HMRC, SOURCE_CBDIF = "esma_firds_funds", "hmrc_reporting_funds", "esma_cbdif_funds"
ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}\d$")
_TABLE = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
_UMBRELLA_NAME = re.compile(r"\b(plc|icav|umbrella|sicav|fcp|funds? (?:plc|icav))\s*$", re.I)


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": user_agent(), "Accept": "*/*"})
    with urllib.request.urlopen(request, timeout=max(timeout_seconds(), 120)) as response:
        return response.read()


def norm_name(value: str | None) -> str:
    """Casefolded, punctuation- and legal-form-free fund name used as a conservative join key."""
    text = (value or "").casefold().replace("&", " and ")
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    text = re.sub(r"\b(plc|icav|the|ucits|etf|fund|funds|sub|class)\b", " ", text)
    return " ".join(text.split())


def strip_share_class(name: str) -> str:
    return re.sub(r"\s*[-–]?\s*(class\s+)?[a-z]{0,3}\s*(acc|dist|inc|accumulating|distributing|accumulation|distribution)\b.*$",
                  "", name, flags=re.I)


# ---------------------------------------------------------------- FIRDS

def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_firds(path: Path) -> dict[str, dict[str, Any]]:
    """Stream a FULINS_C zip into {isin: record}; venue rows of one ISIN are merged."""
    records: dict[str, dict[str, Any]] = {}
    with zipfile.ZipFile(path) as archive, archive.open(archive.namelist()[0]) as stream:
        for _event, element in ET.iterparse(stream, events=("end",)):
            if _local(element.tag) != "RefData":
                continue
            general = next((c for c in element if _local(c.tag) == "FinInstrmGnlAttrbts"), None)
            venue = next((c for c in element if _local(c.tag) == "TradgVnRltdAttrbts"), None)
            if general is not None:
                fields = {_local(c.tag): (c.text or "") for c in general}
                isin = fields.get("Id", "")
                if ISIN_RE.match(isin):
                    issuer = next((c.text for c in element if _local(c.tag) == "Issr"), None)
                    mic = first = None
                    if venue is not None:
                        mic = next((c.text for c in venue if _local(c.tag) == "Id"), None)
                        first = next((c.text for c in venue if _local(c.tag) == "FrstTradDt"), None)
                    record = records.setdefault(isin, {"isin": isin, "name": fields.get("FullNm"), "cfi": fields.get("ClssfctnTp"),
                                                       "currency": fields.get("NtnlCcy") or None, "lei": issuer, "venues": [], "first_trade": first})
                    if mic and mic not in record["venues"]:
                        record["venues"].append(mic)
                    if first and (not record["first_trade"] or first < record["first_trade"]):
                        record["first_trade"] = first
            element.clear()
    return records


def download_firds(*, refresh: bool = False) -> Path:
    RAW.mkdir(parents=True, exist_ok=True)
    target = RAW / "FULINS_C_latest.zip"
    if refresh or not target.exists():
        index = json.loads(_get(FIRDS_INDEX))
        link = index["response"]["docs"][0]["download_link"]
        payload = _get(link)
        if not payload.startswith(b"PK"):
            raise ValueError("ESMA FIRDS download was not a ZIP archive")
        target.write_bytes(payload)
    return target


# ---------------------------------------------------------------- ESMA cross-border register

def fetch_cbdif(domicile: str, *, page_size: int = 1000) -> list[dict[str, Any]]:
    fields = ("funds_lei,funds_national_name,funds_legal_framework_name,funds_manager_nat_name,funds_manager_lei,"
              "funds_status_code_name,funds_domicile_cou_code,funds_created_date,funds_last_update_date,"
              "funds_mgmnt_structure_code_name,funds_host_country_codes")
    out: list[dict[str, Any]] = []
    start = 0
    while True:
        query = {"q": f"funds_domicile_cou_code:{domicile}", "fq": "entity_type:funds_report", "rows": str(page_size),
                 "start": str(start), "wt": "json", "fl": fields, "sort": "id asc"}
        data = json.loads(_get(CBDIF + "?" + urllib.parse.urlencode(query)))
        docs = data["response"]["docs"]
        out.extend(docs)
        start += len(docs)
        if not docs or start >= data["response"]["numFound"]:
            return out


def load_cbdif(*, refresh: bool = False) -> list[dict[str, Any]]:
    RAW.mkdir(parents=True, exist_ok=True)
    cache = RAW / "esma_cbdif_ie_lu.json"
    if refresh or not cache.exists():
        cache.write_text(json.dumps(fetch_cbdif("IE") + fetch_cbdif("LU")))
    return json.loads(cache.read_text())


# ---------------------------------------------------------------- HMRC reporting funds

def iter_ods_rows(path: Path) -> Iterator[list[str]]:
    with zipfile.ZipFile(path) as archive, archive.open("content.xml") as stream:
        for _event, element in ET.iterparse(stream, events=("end",)):
            if element.tag != _TABLE + "table-row":
                continue
            row: list[str] = []
            for cell in element:
                if cell.tag not in (_TABLE + "table-cell", _TABLE + "covered-table-cell"):
                    continue
                repeat = min(int(cell.get(_TABLE + "number-columns-repeated", "1")), 50)
                text = "".join("".join(p.itertext()) for p in cell if p.tag.endswith("}p"))
                row.extend([text] * repeat)
            if any(row):
                yield row
            element.clear()


def parse_hmrc(path: Path) -> list[dict[str, str]]:
    rows = iter_ods_rows(path)
    header = next(rows, [])
    if len(header) < 9 or "ISIN" not in header[5]:
        raise ValueError(f"Unexpected HMRC reporting-funds columns: {header[:9]}")
    out = []
    for row in rows:
        if len(row) >= 9 and ISIN_RE.match(row[5].strip()):
            out.append({"parent": row[2], "class_ref": row[3], "sub": row[4], "isin": row[5].strip(),
                        "reporting_from": row[7], "ceased": row[8]})
    return out


def download_hmrc(*, refresh: bool = False) -> Path:
    RAW.mkdir(parents=True, exist_ok=True)
    target = RAW / "hmrc_master_weblist.ods"
    if refresh or not target.exists():
        page = _get(HMRC_PAGE).decode("utf-8", errors="replace")
        match = re.search(r"https://assets\.publishing\.service\.gov\.uk/[^\"']*\.ods", page)
        if not match:
            raise ValueError("HMRC reporting-funds page did not expose the ODS list")
        payload = _get(match.group(0))
        if not payload.startswith(b"PK"):
            raise ValueError("HMRC download was not an ODS file")
        target.write_bytes(payload)
    return target


# ---------------------------------------------------------------- matching (pure functions)

def match_lu(funds: Iterable[tuple[int, str | None]], firds: dict[str, dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    """funds = (fund_id, lei). Luxembourg: BDE LEI equals the FIRDS issuer LEI."""
    by_lei: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for record in firds.values():
        if record["isin"].startswith("LU") and record["lei"]:
            by_lei[record["lei"]].append(record)
    return {fund_id: by_lei[lei] for fund_id, lei in funds if lei and lei in by_lei}


def match_ie(funds: Iterable[tuple[int, str]], firds: dict[str, dict[str, Any]],
             hmrc: list[dict[str, str]]) -> dict[int, dict[str, dict[str, Any]]]:
    """Ireland: exact normalised sub-fund name; umbrella-style names and ambiguous names are never used."""
    by_name: dict[str, set[int]] = collections.defaultdict(set)
    for fund_id, name in funds:
        if name and not _UMBRELLA_NAME.search(name.strip()):
            key = norm_name(name)
            if key:
                by_name[key].add(fund_id)
    unique = {key: next(iter(ids)) for key, ids in by_name.items() if len(ids) == 1}
    out: dict[int, dict[str, dict[str, Any]]] = collections.defaultdict(dict)
    for row in hmrc:
        if not row["isin"].startswith("IE"):
            continue
        for key in (norm_name(row["sub"]), norm_name(strip_share_class(row["sub"])), norm_name(f"{row['parent']} {row['sub']}")):
            if key in unique:
                out[unique[key]][row["isin"]] = {"isin": row["isin"], "name": row["sub"], "source": SOURCE_HMRC,
                    "attributes": {"parent_fund": row["parent"], "hmrc_class_ref": row["class_ref"],
                                   "reporting_fund_from": row["reporting_from"], "reporting_fund_ceased": row["ceased"] or None}}
                break
    for record in firds.values():
        if record["isin"].startswith("IE"):
            key = norm_name(strip_share_class(record["name"] or ""))
            if key in unique:
                out[unique[key]].setdefault(record["isin"], {"isin": record["isin"], "name": record["name"], "source": SOURCE_FIRDS,
                    "currency": record["currency"], "attributes": {"cfi": record["cfi"], "issuer_lei": record["lei"],
                    "venues": record["venues"], "first_trade": record["first_trade"]}})
    return out


# ---------------------------------------------------------------- load

def _record_for_lu(record: dict[str, Any]) -> dict[str, Any]:
    return {"isin": record["isin"], "name": record["name"], "source": SOURCE_FIRDS, "currency": record["currency"],
            "attributes": {"cfi": record["cfi"], "issuer_lei": record["lei"], "venues": record["venues"],
                           "first_trade": record["first_trade"]}}


def _primary_isin(isins: list[dict[str, Any]]) -> str:
    """Deterministic representative share-class ISIN: earliest first trade, else lowest ISIN."""
    def key(item: dict[str, Any]) -> tuple[str, str]:
        return ((item.get("attributes") or {}).get("first_trade") or "9999", item["isin"])
    return min(isins, key=key)["isin"]


def sync_eu_fund_ids(*, refresh: bool = False, dry_run: bool = False) -> dict[str, Any]:
    firds = parse_firds(download_firds(refresh=refresh))
    hmrc = parse_hmrc(download_hmrc(refresh=refresh))
    cbdif = load_cbdif(refresh=refresh)
    now = datetime.now(timezone.utc)
    stats: dict[str, Any] = {"firds_isins": len(firds), "hmrc_isins": len(hmrc), "cbdif_records": len(cbdif)}
    with SessionLocal() as session:
        lu_rows = session.execute(select(Fund.id, FundProfileSnapshot.payload["legal_entity_identifier"].astext)
            .join(FundProfileSnapshot, (FundProfileSnapshot.fund_id == Fund.id) & (FundProfileSnapshot.dataset == "summary"))
            .where(Fund.source_id == "lu_bde_nonmonetary_funds")).all()
        ie_rows = session.execute(select(Fund.id, Fund.name).where(Fund.domicile_country == "IE")).all()
        matches: dict[int, dict[str, dict[str, Any]]] = collections.defaultdict(dict)
        for fund_id, records in match_lu(lu_rows, firds).items():
            for record in records:
                matches[fund_id][record["isin"]] = _record_for_lu(record)
        for fund_id, isins in match_ie(ie_rows, firds, hmrc).items():
            matches[fund_id].update(isins)
        stats["funds_with_isin"] = len(matches)
        stats["isins_attached"] = sum(len(v) for v in matches.values())
        lu_ids = {row[0] for row in lu_rows}
        stats["lu_funds_matched"] = sum(1 for fid in matches if fid in lu_ids)
        stats["ie_funds_matched"] = stats["funds_with_isin"] - stats["lu_funds_matched"]

        # Register data: LEI-based for LU, exact-name for IE.
        cb_by_lei = {r["funds_lei"]: r for r in cbdif if r.get("funds_lei")}
        ie_by_name: dict[str, list[int]] = collections.defaultdict(list)
        for fund_id, name in ie_rows:
            ie_by_name[norm_name(name)].append(fund_id)
        register: dict[int, dict[str, Any]] = {}
        for fund_id, lei in lu_rows:
            if lei and lei in cb_by_lei:
                register[fund_id] = cb_by_lei[lei]
        for record in cbdif:
            if record.get("funds_domicile_cou_code") == "IE":
                ids = ie_by_name.get(norm_name(record.get("funds_national_name")), [])
                if len(ids) == 1:
                    register[ids[0]] = record
        stats["funds_with_register_data"] = len(register)
        if dry_run:
            return stats
        fund_sources = dict(session.execute(select(Fund.id, Fund.source_id).where(Fund.id.in_(list(register)))).all())

        for fund_id, isins in matches.items():
            values = [{"fund_id": fund_id, "id_type": "ISIN", "value": item["isin"], "source_id": item["source"],
                       "share_class": item.get("name"), "currency": item.get("currency"),
                       "attributes": item.get("attributes"), "source_url": None, "retrieved_at": now}
                      for item in isins.values()]
            for offset in range(0, len(values), 500):
                stmt = pg_insert(FundIdentifier.__table__).values(values[offset:offset + 500])
                session.execute(stmt.on_conflict_do_update(constraint="uq_fund_identifier", set_={
                    "share_class": stmt.excluded.share_class, "currency": stmt.excluded.currency,
                    "attributes": stmt.excluded.attributes, "retrieved_at": stmt.excluded.retrieved_at}))
            # Representative share-class ISIN on the fund row (only when empty); all ISINs stay in fund_identifiers.
            session.execute(update(Fund).where(Fund.id == fund_id, Fund.isin.is_(None)).values(isin=_primary_isin(list(isins.values()))))
        for fund_id, record in register.items():
            values: dict[str, Any] = {}
            if record.get("funds_manager_nat_name"):
                values["manager"] = record["funds_manager_nat_name"][:300]
            if values:
                session.execute(update(Fund).where(Fund.id == fund_id, Fund.manager.is_(None)).values(**values))
            payload = {k: record.get(k) for k in ("funds_lei", "funds_legal_framework_name", "funds_manager_lei",
                       "funds_status_code_name", "funds_mgmnt_structure_code_name", "funds_host_country_codes",
                       "funds_created_date", "funds_last_update_date") if record.get(k) is not None}
            stmt = pg_insert(FundProfileSnapshot.__table__).values(fund_id=fund_id, source_id=fund_sources[fund_id],
                dataset="esma_cross_border_register", source_report_date=None, snapshot_key="esma_cbdif",
                payload=payload, source_url=CBDIF, retrieved_at=now)
            session.execute(stmt.on_conflict_do_update(constraint="uq_fund_profile_source_snapshot",
                set_={"payload": stmt.excluded.payload, "retrieved_at": stmt.excluded.retrieved_at}))
        session.commit()
    return stats
