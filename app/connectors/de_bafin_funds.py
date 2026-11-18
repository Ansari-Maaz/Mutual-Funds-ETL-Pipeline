"""BaFin Investmentfonds-Datenbank: German-domiciled public investment funds with ISIN where published.

Source: https://portal.mvp.bafin.de/database/FondsInfo/ (CSV export per initial letter, ';' separated, UTF-8 BOM).
Content may be stored and reproduced with a clear source reference: (c) Bundesanstalt fuer Finanzdienstleistungsaufsicht /
www.bafin.de (BaFin terms of use). Only rows whose home country is Germany are loaded here; funds from other
home states that are marketed in Germany belong to their own country's sources.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import time
import urllib.request
from datetime import date, datetime, timezone
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any, Iterable

from app.config import timeout_seconds, user_agent
from app.connectors.base import BaseConnector
from app.enrichment.eu_fund_ids import norm_name

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "germany"
REPORTS = ROOT / "reports"
BASE = "https://portal.mvp.bafin.de/database/FondsInfo/"
EXPORT = BASE + "sucheFonds.do?d-16544-e=1&letterFonds={letter}&6578706f7274=1"
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
HEADER = ["BaFin-Id", "Fonds", "Land", "Struktur", "Umbrella", "Auflegungsdatum/ Vertriebsbeginn", "Fondsart", "Verwalt. Ges.", "Repräsentant", "ISIN"]
ATTRIBUTION = "(c) Bundesanstalt für Finanzdienstleistungsaufsicht / www.bafin.de"


def download_bafin(*, refresh: bool = False, delay: float = 1.0) -> dict[str, Any]:
    RAW.mkdir(parents=True, exist_ok=True)
    target = RAW / "bafin_investmentfonds.csv"
    downloaded = refresh or not target.exists()
    if downloaded:
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
        headers = {"User-Agent": user_agent(), "Accept": "text/csv,*/*"}
        opener.open(urllib.request.Request(BASE + "sucheFonds.do?letterFonds=A", headers=headers), timeout=timeout_seconds()).read()
        rows: list[list[str]] = []
        for letter in LETTERS:
            payload = opener.open(urllib.request.Request(EXPORT.format(letter=letter), headers=headers),
                                  timeout=max(timeout_seconds(), 90)).read().decode("utf-8-sig")
            reader = csv.reader(io.StringIO(payload), delimiter=";")
            header = next(reader, [])
            if [h.strip() for h in header[:3]] != HEADER[:3]:
                raise ValueError(f"Unexpected BaFin export header for letter {letter}: {header[:4]}")
            rows.extend(row for row in reader if any(row))
            time.sleep(delay)
        with target.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream, delimiter=";")
            writer.writerow(HEADER)
            writer.writerows(rows)
    payload = target.read_bytes()
    manifest = {"source_id": "de_bafin_investmentfonds", "url": BASE, "path": str(target.relative_to(ROOT)),
                "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(), "downloaded": downloaded,
                "attribution": ATTRIBUTION, "checked_at": datetime.now(timezone.utc).isoformat()}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "de_bafin_dataset_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def existing_german_names() -> set[str]:
    """Normalised names of German funds already loaded from other sources (empty when the DB is unreachable)."""
    try:
        from sqlalchemy import select
        from app.db.session import SessionLocal
        from app.models.schema import Fund
        with SessionLocal() as session:
            rows = session.execute(select(Fund.name).where(Fund.domicile_country == "DE",
                                                           Fund.source_id != "de_bafin_investmentfonds")).scalars()
            return {norm_name(name) for name in rows}
    except Exception:  # noqa: BLE001 - connector must still run without a database
        return set()


def _date(value: str) -> str | None:
    value = (value or "").strip()
    try:
        day, month, year = value.split(".")
        return date(int(year), int(month), int(day)).isoformat()
    except ValueError:
        return None


def parse_rows(rows: Iterable[list[str]]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    records: dict[str, dict[str, Any]] = {}
    rejects: list[dict[str, str]] = []
    for row in rows:
        row = (list(row) + [""] * 10)[:10]
        bafin_id, name, land, structure, umbrella, launch, kind, manager, representative, isin = (v.strip() for v in row)
        if land != "Deutschland" or not name:
            continue
        if structure == "Umbrella":
            continue  # umbrella shell; its sub-funds (Teilfonds) are the investable funds
        key = bafin_id or "H" + hashlib.sha1(f"{name}|{umbrella}|{kind}".encode()).hexdigest()[:16]
        if key in records:
            rejects.append({"source_fund_id": key, "reason": "duplicate BaFin key"})
            continue
        records[key] = {"source_fund_id": key, "name": name, "legal_name": umbrella or None, "domicile_country": "DE",
                        "currency": None, "isin": isin if len(isin) == 12 else None,
                        "provider": manager or None, "manager": manager or None, "fund_type": kind or None,
                        "inception_date": _date(launch), "official_url": BASE,
                        "status": "Authorised for public distribution", "_navs": [],
                        "_profile_source_url": BASE,
                        "_profile_data": {"summary": {"structure": structure or None, "representative": representative or None,
                                                      "attribution": ATTRIBUTION}}}
    return list(records.values()), rejects


class DeBafinFundsConnector(BaseConnector):
    source_id = "de_bafin_investmentfonds"
    country_code = "DE"

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] | None = None
        self._rejects: list[dict[str, str]] = []

    def get_source_metadata(self) -> dict[str, Any]:
        return {"country_code": "DE", "organization": "Bundesanstalt für Finanzdienstleistungsaufsicht (BaFin)",
                "source_name": "BaFin Investmentfonds-Datenbank (German-domiciled public funds)", "endpoint_url": BASE,
                "license_status": f"Reuse with source reference: {ATTRIBUTION}"}

    def _load(self) -> None:
        download_bafin()
        with (RAW / "bafin_investmentfonds.csv").open(encoding="utf-8", newline="") as stream:
            reader = csv.reader(stream, delimiter=";")
            next(reader, None)
            records, self._rejects = parse_rows(reader)
        # Funds already loaded from the Banco de España list are enriched by merge_bafin_into_existing()
        # instead of being duplicated here.
        known = existing_german_names()
        self._records = [r for r in records if norm_name(r["name"]) not in known]
        if not records:
            raise ValueError("No German-domiciled funds parsed from the BaFin export")
        REPORTS.mkdir(parents=True, exist_ok=True)
        (REPORTS / "de_bafin_rejected_records.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in self._rejects))

    def check_availability(self) -> dict[str, Any]:
        self._load()
        return {"available": True, "fund_records": len(self._records or []), "rejected_records": len(self._rejects)}

    def extract_funds(self, start_date: date | None = None, end_date: date | None = None) -> Iterable[dict[str, Any]]:
        if self._records is None:
            self._load()
        return iter(self._records or [])
