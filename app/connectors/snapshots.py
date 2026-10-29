"""Repeatable file snapshot download and source availability helpers."""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.config import timeout_seconds, user_agent

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIR = ROOT / "reports" / "source_manifests"
SNAPSHOTS = {
    "it_borsa_navs": ROOT / "data/raw/italy/borsa_italiana_daily_nav.csv",
    "fr_lacotebleue_navs": ROOT / "data/raw/france/lacote_bleue_navs.csv",
    "nl_euronext_fund_navs": ROOT / "data/raw/netherlands/euronext_amsterdam_funds.csv",
    "lu_euronext_fund_navs": ROOT / "data/raw/luxembourg/euronext_luxembourg_funds.csv",
    "lu_allianz_daily_navs": ROOT / "data/raw/luxembourg/allianz_luxembourg_daily_nav.csv",
}
REQUIRED_COLUMNS = {
    "it_borsa_navs": {"isin", "currency", "valuation_date", "nav"},
    "fr_lacotebleue_navs": {"isin", "name", "currency", "valuation_date", "nav"},
    "nl_euronext_fund_navs": {"isin", "name", "currency", "valuation_date", "nav"},
    "lu_euronext_fund_navs": {"isin", "name", "currency", "valuation_date", "nav"},
    "lu_allianz_daily_navs": {"isin", "name", "currency", "valuation_date", "nav", "share_class"},
}


def probe_snapshot(source_id: str, source_url: str, path: Path) -> dict:
    """Probe upstream and validate that an ingestible local CSV snapshot exists."""
    try:
        response = httpx.get(
            source_url, timeout=timeout_seconds(), follow_redirects=True,
            headers={"User-Agent": user_agent()},
        )
        response.raise_for_status()
        if not path.is_file():
            return {"available": False, "reason": f"Local snapshot missing: {path.relative_to(ROOT)}"}
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames or not REQUIRED_COLUMNS[source_id].issubset(reader.fieldnames):
                return {"available": False, "reason": "Snapshot CSV is missing required source columns"}
            if not next(reader, None):
                return {"available": False, "reason": "Snapshot CSV has no data rows"}
        return {"available": True, "http_status": response.status_code}
    except (httpx.HTTPError, OSError, UnicodeError, csv.Error) as exc:
        return {"available": False, "reason": f"{type(exc).__name__}: {exc}"}


def fetch_snapshot(source_id: str, source_url: str) -> dict:
    """Download a source's CSV export and record the exact retrieval provenance."""
    if source_id not in SNAPSHOTS:
        raise ValueError(f"Unsupported snapshot source: {source_id}")
    response = httpx.get(source_url, timeout=timeout_seconds(), follow_redirects=True,
                         headers={"User-Agent": user_agent(), "Accept": "text/csv,application/octet-stream,*/*"})
    response.raise_for_status()
    payload = response.content
    if not payload or b"\x00" in payload[:4096]:
        raise ValueError("Downloaded snapshot is empty or not a text CSV")
    path = SNAPSHOTS[source_id]
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    # Verify that the payload can be consumed as CSV before replacing the last good snapshot.
    with temporary.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if (not reader.fieldnames or not REQUIRED_COLUMNS[source_id].issubset(reader.fieldnames)
                or not next(reader, None)):
            temporary.unlink(missing_ok=True)
            raise ValueError("Downloaded file is not a non-empty CSV snapshot")
    temporary.replace(path)
    manifest = {
        "source_id": source_id,
        "url": str(response.url),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
        "path": str(path.relative_to(ROOT)),
        "content_type": response.headers.get("content-type"),
    }
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    (MANIFEST_DIR / f"{source_id}.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest
