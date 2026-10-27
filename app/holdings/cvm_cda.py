"""Load official CVM CDA portfolio-composition snapshots for Brazilian funds."""
from __future__ import annotations

import csv
import io
import re
import urllib.request
import zipfile
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import timeout_seconds, user_agent
from app.db.session import SessionLocal
from app.models.schema import Fund, PortfolioHolding, HoldingMetric

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "brazil"
BASE_URL = "https://dados.cvm.gov.br/dados/FI/DOC/CDA/DADOS"
DATASET_URL = "https://dados.cvm.gov.br/dataset/fi-doc-cda"


def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def _first(row: dict[str, str], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        if value is not None and value.strip():
            return value.strip()
    return None


def _number(value: str | None) -> Decimal | None:
    if not value or value.strip() in {"", "-", "N/A"}:
        return None
    raw = value.strip()
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    try:
        parsed = Decimal(raw)
        return parsed if parsed.is_finite() else None
    except InvalidOperation:
        return None


def _download(month: str) -> tuple[Path, str]:
    if not re.fullmatch(r"\d{6}", month):
        raise ValueError("CVM CDA month must use YYYYMM format")
    destination = RAW / f"cda_fi_{month}.zip"
    url = f"{BASE_URL}/cda_fi_{month}.zip"
    if not destination.exists():
        RAW.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(url, headers={"User-Agent": user_agent(), "Accept": "*/*"})
        partial = destination.with_suffix(".zip.part")
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds()) as response, partial.open("wb") as output:
                while block := response.read(1024 * 1024):
                    output.write(block)
            if not zipfile.is_zipfile(partial):
                raise ValueError(f"CVM response is not a ZIP archive: {url}")
            partial.replace(destination)
        finally:
            partial.unlink(missing_ok=True)
    return destination, url


def sync_cvm_holdings(month: str) -> dict[str, int | str]:
    """Import public CDA rows for one month; reruns update each report-date row."""
    archive_path, source_url = _download(month)
    with SessionLocal() as session:
        funds = session.execute(select(Fund.id, Fund.source_fund_id).where(
            Fund.source_id == "cvm_open_fund_data", Fund.domicile_country == "BR")).all()
    fund_ids: dict[str, list[int]] = {}
    funds_by_subclass: dict[tuple[str, str], list[int]] = {}
    base_funds: dict[str, list[int]] = {}
    for fund_id, source_fund_id in funds:
        native_id, separator, subclass_id = source_fund_id.partition(":")
        cnpj = _digits(native_id)
        if cnpj:
            fund_ids.setdefault(cnpj, []).append(fund_id)
            if separator and subclass_id:
                funds_by_subclass.setdefault((cnpj, subclass_id), []).append(fund_id)
            else:
                base_funds.setdefault(cnpj, []).append(fund_id)

    snapshots: dict[tuple[int, date], list[dict[str, Any]]] = {}
    pl_by_fund: dict[tuple[int, date], Decimal] = {}
    compatible_files = 0
    with zipfile.ZipFile(archive_path) as archive:
        csv_names = [name for name in archive.namelist()
                     if name.lower().endswith(".csv") and "confid" not in name.lower()]
        if not csv_names:
            raise ValueError(f"CVM CDA archive has no public block CSV files: {archive_path}")
        for csv_name in csv_names:
            with archive.open(csv_name) as binary, io.TextIOWrapper(binary, encoding="latin-1", newline="") as stream:
                reader = csv.DictReader(stream, delimiter=";")
                fields = set(reader.fieldnames or [])
                id_col = next((key for key in ("CNPJ_FUNDO_CLASSE", "CNPJ_FUNDO", "CNPJ_FDO") if key in fields), None)
                date_col = next((key for key in ("DT_COMPTC", "DT_COMPT") if key in fields), None)
                if not id_col or not date_col:
                    continue
                compatible_files += 1
                for row in reader:
                    cnpj = _digits(row.get(id_col))
                    if cnpj not in fund_ids:
                        continue
                    subclass_id = (row.get("ID_SUBCLASSE") or "").strip()
                    if subclass_id:
                        target_fund_ids = funds_by_subclass.get((cnpj, subclass_id), []) or base_funds.get(cnpj, [])
                    else:
                        # Class-level positions apply to a sole class record or explicitly registered base fund;
                        # shared positions are fanned out across subclasses only when the source has no subclass key.
                        target_fund_ids = base_funds.get(cnpj, []) or fund_ids[cnpj]
                    raw_date = row.get(date_col, "")
                    try:
                        report_date = date.fromisoformat(raw_date[:10]) if "-" in raw_date else date(int(raw_date[6:10]), int(raw_date[3:5]), int(raw_date[:2]))
                    except (ValueError, TypeError):
                        continue
                    value = _number(_first(row, "VL_MERC_POS_FINAL", "VL_MERC_POS", "VL_MERCADO", "VL_MERCADO_FINAL"))
                    quantity = _number(_first(row, "QT_POS_FINAL", "QT_POSICAO_FINAL", "QT_ATIVO"))
                    pl = _number(_first(row, "VL_PATRIM_LIQ", "VL_PL", "VL_PATRIMONIO_LIQUIDO"))
                    if pl is not None and pl > 0:
                        for target_fund_id in target_fund_ids:
                            pl_by_fund[(target_fund_id, report_date)] = pl
                    security_name = _first(row, "DS_ATIVO", "DS_TITULO", "NM_ATIVO", "NM_EMISSOR", "DENOM_SOCIAL", "DS_FUNDO")
                    ticker = _first(row, "CD_TICKER", "TICKER", "CD_NEGOCIACAO")
                    isin = _first(row, "CD_ISIN", "ISIN")
                    if not security_name and not ticker and not isin:
                        # Keep identifiable positions with no name; never invent one.
                        security_name = None
                    position = {
                        "security_name": security_name[:500] if security_name else None,
                        "ticker": ticker[:50] if ticker else None,
                        "isin": isin[:12] if isin else None,
                        "cusip": None,
                        "quantity": quantity,
                        "market_value": value,
                        "market_value_currency": "BRL" if value is not None else None,
                        "portfolio_weight": None,
                        "source_url": source_url,
                        "data_source": "cvm_open_data_cda",
                        "accession_number": None,
                    }
                    for target_fund_id in target_fund_ids:
                        snapshots.setdefault((target_fund_id, report_date), []).append(position)

    if compatible_files == 0:
        raise ValueError("CVM CDA archive contains CSV files, but none have recognized CNPJ and reporting-date columns; no fund status was changed")

    loaded_funds: set[int] = set()
    rows_loaded = 0
    now = datetime.now(timezone.utc)
    with SessionLocal() as session:
        session.execute(update(Fund).where(
            Fund.source_id == "cvm_open_fund_data", Fund.domicile_country == "BR").values(
                holdings_status="unavailable", holdings_report_date=None))
        for (fund_id, report_date), positions in snapshots.items():
            # Stable order within a source-file/report snapshot prevents duplicate rows on rerun.
            values = []
            for index, position in enumerate(positions):
                values.append({**position, "fund_id": fund_id, "reporting_date": report_date,
                               "holding_index": index, "retrieved_at": now})
            if not values:
                continue
            table = PortfolioHolding.__table__
            for offset in range(0, len(values), 400):
                chunk = values[offset:offset + 400]
                stmt = pg_insert(table).values(chunk)
                update_columns = {key: getattr(stmt.excluded, key) for key in chunk[0]
                                  if key not in {"id", "fund_id", "reporting_date", "holding_index"}}
                session.execute(stmt.on_conflict_do_update(
                    constraint="uq_fund_holding_report_item", set_=update_columns))
            # Portfolio weight is a derived metric: market value / reported fund net assets.
            pl = pl_by_fund.get((fund_id, report_date))
            if pl:
                rows = session.execute(select(PortfolioHolding.id, PortfolioHolding.market_value).where(
                    PortfolioHolding.fund_id == fund_id,
                    PortfolioHolding.reporting_date == report_date,
                    PortfolioHolding.data_source == "cvm_open_data_cda")).all()
                metric_values = []
                for holding_id, market_value in rows:
                    if market_value is None:
                        continue
                    weight = (Decimal(market_value) / pl) * Decimal(100)
                    metric_values.append({"holding_id": holding_id, "data_source": "cvm_cda_derived_weight",
                        "source_url": source_url, "as_of_date": report_date, "portfolio_weight": weight,
                        "calculation_basis": "Reported market value divided by reported fund net assets; percent."})
                for offset in range(0, len(metric_values), 400):
                    chunk = metric_values[offset:offset + 400]
                    stmt = pg_insert(HoldingMetric.__table__).values(chunk)
                    updates = {key: getattr(stmt.excluded, key) for key in chunk[0]
                               if key not in {"id", "holding_id", "data_source", "as_of_date"}}
                    session.execute(stmt.on_conflict_do_update(
                        constraint="uq_holding_metric_source_date", set_=updates))
            loaded_funds.add(fund_id)
            rows_loaded += len(values)
        if snapshots:
            latest_by_fund: dict[int, date] = {}
            for fund_id, report_date in snapshots:
                latest_by_fund[fund_id] = max(report_date, latest_by_fund.get(fund_id, report_date))
            for fund_id, report_date in latest_by_fund.items():
                session.execute(update(Fund).where(Fund.id == fund_id).values(
                    holdings_status="available", holdings_report_date=report_date))
        session.commit()
    return {"month": month, "funds_checked": len(funds), "funds_with_holdings": len(loaded_funds),
            "holding_rows_loaded": rows_loaded, "source_url": source_url}
