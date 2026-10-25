"""CVM Brazil daily NAV and fund/class registry connector."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import urllib.request
import zipfile
from copy import deepcopy
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

from app.connectors.base import BaseConnector
from app.config import timeout_seconds, user_agent

ROOT=Path(__file__).resolve().parents[2]
RAW=ROOT/"data"/"raw"/"cvm"
REPORTS=ROOT/"reports"
REGISTRY_URL="https://dados.cvm.gov.br/dados/FI/CAD/DADOS/registro_fundo_classe.zip"
CURRENT_CAD_URL="https://dados.cvm.gov.br/dados/FI/CAD/DADOS/cad_fi.csv"

def _monthly_url(month: str) -> str:
    return f"https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/inf_diario_fi_{month}.zip"

def _sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()

def _download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True,exist_ok=True)
    partial=destination.with_suffix(destination.suffix+".part")
    request=urllib.request.Request(url,headers={"User-Agent":user_agent(),"Accept":"*/*"})
    try:
        with urllib.request.urlopen(request,timeout=timeout_seconds()) as response, partial.open("wb") as out:
            while True:
                block=response.read(1024*1024)
                if not block: break
                out.write(block)
        if destination.suffix==".zip" and not zipfile.is_zipfile(partial):
            raise ValueError(f"Downloaded file is not a ZIP archive: {url}")
        partial.replace(destination)
    finally:
        partial.unlink(missing_ok=True)

def download_cvm_data(months: Iterable[str] | None=None, *, refresh: bool=False) -> list[dict[str, Any]]:
    """Download official CVM snapshots and write a checksummed provenance manifest."""
    RAW.mkdir(parents=True,exist_ok=True)
    months=list(months or [datetime.now(timezone.utc).strftime("%Y%m")])
    targets=[(_monthly_url(m),RAW/f"inf_diario_fi_{m}.zip") for m in months]
    targets += [(REGISTRY_URL,RAW/"registro_fundo_classe.zip"),
                (CURRENT_CAD_URL,RAW/"cad_fi.csv")]
    completed=[]
    for url,path in targets:
        did_download=refresh or not path.exists()
        if did_download:
            _download(url,path)
        completed.append({"url":url,"path":str(path.relative_to(ROOT)),"bytes":path.stat().st_size,
          "sha256":_sha256(path),"downloaded":did_download,"checked_at":datetime.now(timezone.utc).isoformat()})
    manifest_path=REPORTS/"cvm_dataset_manifest.json"
    old=[]
    if manifest_path.exists():
        try: old=json.loads(manifest_path.read_text())
        except (OSError,ValueError): old=[]
    by_path={row["path"]:row for row in old if isinstance(row,dict) and row.get("path")}
    for row in completed:
        if not row["downloaded"] and row["path"] in by_path:
            row["downloaded_at"]=by_path[row["path"]].get("downloaded_at")
        elif row["downloaded"]:
            row["downloaded_at"]=row["checked_at"]
        by_path[row["path"]]=row
    manifest_path.write_text(json.dumps(list(by_path.values()),indent=2,ensure_ascii=False)+"\n")
    return completed

def _digits(value: str | None) -> str:
    return "".join(c for c in (value or "") if c.isdigit())

class CvmConnector(BaseConnector):
    source_id="cvm_open_fund_data"
    country_code="BR"

    def __init__(self) -> None:
        self._fund_records: list[dict[str,Any]] | None=None
        self._rejects: list[dict[str,Any]]=[]
        self._date_range: tuple[date,date] | None=None

    def get_source_metadata(self) -> dict[str,Any]:
        return {"country_code":"BR","organization":"Comissão de Valores Mobiliários (CVM)",
          "source_name":"Fund registration and daily NAV (Informe Diário)",
          "endpoint_url":"https://dados.cvm.gov.br/dataset/fi-doc-inf_diario",
          "license_status":"Permitted"}

    def _load(self,start_date: date | None=None,end_date: date | None=None) -> None:
        today=datetime.now(timezone.utc).date()
        start=start_date or date(today.year,today.month,1)
        end=end_date or today
        if start>end: raise ValueError("start_date must be on or before end_date")
        month_list=[]
        year,month=start.year,start.month
        while (year,month)<=(end.year,end.month):
            month_list.append(f"{year:04d}{month:02d}")
            month+=1
            if month==13: year,month=year+1,1
        if len(month_list)>12:
            raise ValueError("CVM connector currently supports up to 12 monthly archives per run")
        download_cvm_data(month_list)

        registry_zip=zipfile.ZipFile(RAW/"registro_fundo_classe.zip")
        self._rejects=[]
        classes: dict[str,dict[str,str]]={}
        funds: dict[str,dict[str,str]]={}
        class_ids: dict[str,str]={}
        subclasses: dict[tuple[str,str],str]={}
        with io.TextIOWrapper(registry_zip.open("registro_fundo.csv"),encoding="latin-1",newline="") as f:
            for row in csv.DictReader(f,delimiter=";"):
                fund_id=(row.get("ID_Registro_Fundo") or "").strip()
                if fund_id:
                    funds[fund_id]=row
        with io.TextIOWrapper(registry_zip.open("registro_classe.csv"),encoding="latin-1",newline="") as f:
            for row in csv.DictReader(f,delimiter=";"):
                cnpj=_digits(row.get("CNPJ_Classe"))
                if cnpj:
                    classes[cnpj]=row
                    class_ids[cnpj]=row.get("ID_Registro_Classe","")
        with io.TextIOWrapper(registry_zip.open("registro_subclasse.csv"),encoding="latin-1",newline="") as f:
            for row in csv.DictReader(f,delimiter=";"):
                key=(row.get("ID_Registro_Classe", ""),row.get("ID_Subclasse", ""))
                name=(row.get("Denominacao_Social") or "").strip()
                if key[0] and key[1] and name:
                    subclasses[key]=name

        grouped: dict[str,dict[str,Any]]={}
        for cnpj, registry in classes.items():
            fund_registry=funds.get((registry.get("ID_Registro_Fundo") or "").strip(), {})
            fund_name=(registry.get("Denominacao_Social") or "").strip()
            if not fund_name:
                self._rejects.append({"reason":"class has no registered name","cnpj":cnpj})
                continue
            def parse_date(value: str | None) -> date | None:
                try:
                    return date.fromisoformat(value) if value else None
                except ValueError:
                    return None
            def decimal(value: str | None) -> str | None:
                value=(value or "").strip()
                if "," in value:
                    value=value.replace(".", "").replace(",", ".")
                try:
                    parsed=Decimal(value)
                    return str(parsed) if parsed.is_finite() else None
                except (InvalidOperation, ValueError):
                    return None
            grouped[cnpj]={
                "source_fund_id": cnpj,
                "name": fund_name,
                "legal_name": fund_name,
                "domicile_country": "BR",
                "currency": "BRL",
                "isin": None,
                "provider": (fund_registry.get("Gestor") or "").strip() or None,
                "manager": (fund_registry.get("Gestor") or "").strip() or None,
                "administrator": (fund_registry.get("Administrador") or "").strip() or None,
                "category": (registry.get("Classificacao") or registry.get("Classificacao_Anbima") or "").strip() or None,
                "fund_type": (registry.get("Tipo_Classe") or "").strip() or None,
                "inception_date": parse_date(registry.get("Data_Inicio") or registry.get("Data_Constituicao")),
                "status": (registry.get("Situacao") or "").strip() or None,
                "target_audience": (registry.get("Publico_Alvo") or "").strip() or None,
                "net_assets": decimal(registry.get("Patrimonio_Liquido")),
                "net_assets_date": parse_date(registry.get("Data_Patrimonio_Liquido")),
                "official_url": REGISTRY_URL,
                "_navs": [],
            }
        for month_text in month_list:
            archive=zipfile.ZipFile(RAW/f"inf_diario_fi_{month_text}.zip")
            csv_name=next((n for n in archive.namelist() if n.lower().endswith(".csv")),None)
            if not csv_name: raise ValueError(f"No CSV found in CVM archive for {month_text}")
            with io.TextIOWrapper(archive.open(csv_name),encoding="latin-1",newline="") as f:
                reader=csv.DictReader(f,delimiter=";")
                required={"CNPJ_FUNDO_CLASSE","ID_SUBCLASSE","DT_COMPTC","VL_QUOTA"}
                if not reader.fieldnames or not required.issubset(reader.fieldnames):
                    raise ValueError(f"Unexpected CVM daily report columns in {csv_name}: {reader.fieldnames}")
                for row in reader:
                    cnpj=_digits(row.get("CNPJ_FUNDO_CLASSE"))
                    native_sub=(row.get("ID_SUBCLASSE") or "").strip()
                    registry=classes.get(cnpj)
                    if not registry:
                        self._rejects.append({"reason":"class CNPJ absent from CVM class registry","cnpj":cnpj,"subclass_id":native_sub,"date":row.get("DT_COMPTC"),"nav":row.get("VL_QUOTA")})
                        continue
                    try: valuation_date=date.fromisoformat(row["DT_COMPTC"])
                    except (ValueError,TypeError):
                        self._rejects.append({"reason":"invalid valuation date","cnpj":cnpj,"subclass_id":native_sub,"date":row.get("DT_COMPTC"),"nav":row.get("VL_QUOTA")})
                        continue
                    if valuation_date<start or valuation_date>end: continue
                    try: nav=Decimal(row["VL_QUOTA"])
                    except (InvalidOperation,TypeError): nav=Decimal("0")
                    if not nav.is_finite() or nav<=0:
                        self._rejects.append({"reason":"NAV must be greater than zero","cnpj":cnpj,"subclass_id":native_sub,"date":valuation_date.isoformat(),"nav":row.get("VL_QUOTA")})
                        continue
                    source_fund_id=cnpj+(f":{native_sub}" if native_sub else "")
                    subname=subclasses.get((class_ids.get(cnpj,""),native_sub),"") if native_sub else ""
                    fund_name=(registry.get("Denominacao_Social") or "").strip()
                    if subname and subname.lower() not in fund_name.lower(): fund_name=f"{fund_name} — {subname}"
                    if not fund_name:
                        self._rejects.append({"reason":"class has no registered name","cnpj":cnpj,"subclass_id":native_sub,"date":valuation_date.isoformat()})
                        continue
                    if source_fund_id not in grouped:
                        record=deepcopy(grouped[cnpj])
                        record["source_fund_id"]=source_fund_id
                        record["name"]=fund_name
                        record["legal_name"]=fund_name
                        grouped[source_fund_id]=record
                    record=grouped[source_fund_id]
                    record["_navs"].append({"source_fund_id":source_fund_id,"valuation_date":valuation_date.isoformat(),
                      "nav":str(nav),"currency":"BRL"})
        self._date_range=(start,end)
        self._fund_records=list(grouped.values())
        REPORTS.mkdir(parents=True,exist_ok=True)
        rejects_path=REPORTS/"cvm_rejected_records.jsonl"
        with rejects_path.open("w",encoding="utf-8") as f:
            for row in self._rejects: f.write(json.dumps(row,ensure_ascii=False)+"\n")

    def check_availability(self) -> dict[str,Any]:
        self._load()
        return {"available":True,"source":"official CVM open-data download","fund_records":len(self._fund_records or []),
          "rejected_records":len(self._rejects),"date_range":self._date_range}

    def extract_funds(self,start_date: date | None=None,end_date: date | None=None) -> Iterable[dict[str,Any]]:
        if self._fund_records is None or self._date_range!=(start_date or self._date_range[0],end_date or self._date_range[1]):
            self._load(start_date,end_date)
        return iter(self._fund_records or [])

    def extract_nav_history(self,source_fund_id: str,start_date: date | None=None,end_date: date | None=None) -> Iterable[dict[str,Any]]:
        return ()
