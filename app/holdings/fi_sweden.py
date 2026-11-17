"""Import Finansinspektionen (FI) quarterly UCITS holdings and fund profile fields for Swedish funds.

The FI XML already downloaded by app.connectors.fi_sweden carries far more than the fund identity the
connector loads: full instrument-level holdings, fund net assets, management fees per share class,
benchmark, 24-month standard deviation and active risk. Amounts are in SEK (verified against the sample
files: instrument market value = quantity x price x exchange rate, and value / fund net assets = the
reported weight). FI reports no unit NAV, inception date or fund-level currency.
"""
from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.connectors.fi_sweden import INDEX_URL, RAW
from app.db.session import SessionLocal
from app.models.schema import Fund, FundProfileSnapshot, PortfolioHolding

SOURCE_ID = "fi_sweden_ucits_holdings"
DATA_SOURCE = "fi_sweden_quarterly_holdings"
DATASET = "fi_se_fund_report"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(node: ET.Element | None, name: str) -> ET.Element | None:
    if node is None:
        return None
    for child in node:
        if _local(child.tag) == name:
            return child
    return None


def _text(node: ET.Element | None, name: str) -> str | None:
    child = _child(node, name)
    value = (child.text or "").strip() if child is not None and child.text else ""
    return value or None


def _number(value: str | None) -> Decimal | None:
    if not value:
        return None
    try:
        parsed = Decimal(value.replace(",", "."))
    except InvalidOperation:
        return None
    return parsed if parsed.is_finite() else None


def _fees(fund: ET.Element) -> list[dict[str, Any]]:
    """Management fee per share class (percent p.a.), including any performance-fee terms."""
    fees: list[dict[str, Any]] = []
    for node in fund.iter():
        if _local(node.tag) != "Förvaltningsavgift" or _child(node, "Andelsklass_namn") is None:
            continue
        kind = _child(node, "Förvaltningsavgift_Typ")
        perf = _child(kind, "Förvaltningsavgift_Prestationsbaserad")
        fees.append({"share_class": _text(node, "Andelsklass_namn"),
                     "fixed_fee_percent": _text(kind, "Förvaltningsavgift_fast"),
                     "performance_fee": {"hurdle": _text(perf, "Avkastningströskel"),
                                         "share_of_excess_percent": _text(perf, "ProcentuelltUttag")} if perf is not None else None})
    return fees


def parse_fi_file(path: Path) -> dict[str, Any] | None:
    """Return the report for one fund file, or None when it holds no fund."""
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return None
    fund = next((n for n in root if _local(n.tag) == "Fondinformation" and len(n)), None)
    if fund is None:
        return None
    quarter = _text(_child(root, "Rapportinformation"), "Kvartalsslut")
    company = _child(root, "Bolagsinformation")
    positions = []
    instruments = _child(fund, "FinansiellaInstrument")
    for node in (instruments if instruments is not None else []):
        isin = _text(node, "ISIN-kod_instrument")
        positions.append({
            "security_name": (_text(node, "Instrumentnamn") or "")[:500] or None,
            "isin": isin[:12] if isin else None,
            "asset_class": _text(node, "Tillgångsslag_enligt_LVF_5_kap"),
            "issuer_country": _text(node, "Landkod_Emittent"),
            "instrument_currency": _text(node, "Valuta"),
            "quantity": _number(_text(node, "Antal")),
            "market_value": _number(_text(node, "Marknadsvärde_instrument")),
            "portfolio_weight": _number(_text(node, "Andel_av_fondförmögenhet_instrument")),
        })
    benchmarks = [n.text.strip() for n in fund.iter()
                  if _local(n.tag) == "Jämförelseindex" and len(n) == 0 and n.text and n.text.strip()
                  and n.text.strip().lower() != "jämförelseindex saknas"]  # FI's "benchmark missing" marker
    return {
        "fund_id": _text(fund, "Fond_institutnummer"), "name": _text(fund, "Fond_namn"),
        "status": _text(fund, "Fond_status"),
        "quarter_end": date.fromisoformat(quarter) if quarter else None,
        "profile": {
            "net_assets_sek": _text(fund, "Fondförmögenhet"), "cash_sek": _text(fund, "Likvida_medel"),
            "other_assets_liabilities_sek": _text(fund, "Övriga_tillgångar_och_skulder"),
            "standard_deviation_24m": _text(fund, "Standardavvikelse_24_månader"),
            "active_risk": _text(fund, "Aktiv_risk"),
            "benchmarks": benchmarks, "management_fees": _fees(fund),
            "management_company": _text(company, "Fondbolag_namn"),
            "management_company_lei": _text(company, "Fondbolag_LEI-kod"),
            "management_company_institute_number": _text(company, "Fondbolag_institutnummer"),
            "amount_currency": "SEK",
        },
        "positions": positions,
    }


def sync_fi_sweden_holdings(xml_dir: Path | None = None) -> dict[str, Any]:
    """Load holdings and profile snapshots for every Swedish fund found in the extracted FI XML files."""
    xml_dir = xml_dir or (RAW / "xml")
    reports = [r for r in (parse_fi_file(p) for p in sorted(xml_dir.glob("*.xml"))) if r and r["fund_id"]]
    if not reports:
        raise ValueError(f"No FI fund XML files found in {xml_dir}; run the fi_sweden download first")
    now = datetime.now(timezone.utc)
    stats = {"files": len(reports), "funds_matched": 0, "funds_with_holdings": 0,
             "holding_rows_loaded": 0, "profile_snapshots": 0}
    with SessionLocal() as session:
        ids = dict(session.execute(select(Fund.source_fund_id, Fund.id).where(
            Fund.source_id == SOURCE_ID)).all())
        for report in reports:
            fund_id = ids.get(report["fund_id"])
            quarter = report["quarter_end"]
            if fund_id is None or quarter is None:
                continue
            stats["funds_matched"] += 1
            payload = {**report["profile"], "fund_status": report["status"], "quarter_end": quarter.isoformat()}
            key = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:32]
            stmt = pg_insert(FundProfileSnapshot.__table__).values(
                fund_id=fund_id, source_id=SOURCE_ID, dataset=DATASET, source_report_date=quarter,
                snapshot_key=key, payload=payload, source_url=INDEX_URL, retrieved_at=now)
            session.execute(stmt.on_conflict_do_update(constraint="uq_fund_profile_source_snapshot",
                set_={"payload": stmt.excluded.payload, "source_report_date": stmt.excluded.source_report_date,
                      "retrieved_at": stmt.excluded.retrieved_at}))
            stats["profile_snapshots"] += 1
            company = report["profile"]["management_company"]
            fund_values: dict[str, Any] = {}
            if company:
                fund_values.update(manager=company[:300], provider=company[:300])
            net_assets = _number(report["profile"]["net_assets_sek"])
            if net_assets is not None:
                fund_values.update(net_assets=net_assets, net_assets_date=quarter)  # FI amounts are SEK
            if report["status"]:
                fund_values["status"] = "inactive" if "ej aktiv" in report["status"].lower() else "active"
            if fund_values:
                session.execute(update(Fund).where(Fund.id == fund_id).values(**fund_values))
            positions = report["positions"]
            if not positions:
                session.execute(update(Fund).where(Fund.id == fund_id).values(
                    holdings_status="unavailable", holdings_report_date=None))
                continue
            values = [{"fund_id": fund_id, "reporting_date": quarter, "holding_index": i,
                       "security_name": p["security_name"], "ticker": None, "isin": p["isin"], "cusip": None,
                       "quantity": p["quantity"], "market_value": p["market_value"],
                       "market_value_currency": "SEK" if p["market_value"] is not None else None,
                       "portfolio_weight": p["portfolio_weight"], "data_source": DATA_SOURCE,
                       "source_url": INDEX_URL, "accession_number": None, "retrieved_at": now}
                      for i, p in enumerate(positions)]
            table = PortfolioHolding.__table__
            for offset in range(0, len(values), 400):
                chunk = values[offset:offset + 400]
                stmt = pg_insert(table).values(chunk)
                session.execute(stmt.on_conflict_do_update(constraint="uq_fund_holding_report_item", set_={
                    k: getattr(stmt.excluded, k) for k in chunk[0]
                    if k not in {"id", "fund_id", "reporting_date", "holding_index"}}))
            session.execute(update(Fund).where(Fund.id == fund_id).values(
                holdings_status="available", holdings_report_date=quarter))
            stats["funds_with_holdings"] += 1
            stats["holding_rows_loaded"] += len(values)
        session.commit()
    return stats
