from __future__ import annotations
import argparse, json, re
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
import yaml
from app.catalog import country_rows, discovered_rows
from app.connectors.registry import all_connectors
from app.config import timeout_seconds, user_agent
from app.etl.runs import tracked_run, etl_lock
import httpx

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"

def catalogue() -> list[dict]:
    candidates = (yaml.safe_load((ROOT / "config/sources.yaml").read_text()) or []) + discovered_rows()
    verification_path=REPORTS/"source_verification.json"
    if verification_path.exists():
        verified={r["source_id"]:r for r in json.loads(verification_path.read_text())}
        for source in candidates:
            result=verified.get(source["source_id"])
            if result:
                source["verification_status"]=result["verification_status"]
                source["last_checked_at"]=result["checked_at"]
                source["http_status"]=result["http_status"]
                source["usable_fund_data_confirmed"]=result["usable_fund_data_confirmed"]
                if result.get("error"): source["failure_reason"]=result["error"]
    run_path=REPORTS/"latest_run.json"
    if run_path.exists():
        try: run_document=json.loads(run_path.read_text()); run_rows=run_document.get("results",[])
        except (OSError,ValueError): run_document={}; run_rows=[]
    else: run_document={}; run_rows=[]
    run_by_id={row.get("source_id"):row for row in run_rows}
    for source in candidates:
        result=run_by_id.get(source.get("source_id"))
        if not result: continue
        source["records_extracted"]=result.get("records_extracted",0)
        source["records_loaded"]=result.get("records_loaded",0)
        source["nav_observations_loaded"]=result.get("navs_loaded",0)
        source["rejected_records"]=result.get("rejected_records",0)
        if result.get("status")=="Succeeded":
            source["integration_status"]="Integrated"
            source["verification_status"]="Usable Fund Data Confirmed"
            source["usable_fund_data_confirmed"]=True
            source["last_successful_ingestion_at"]=run_document.get("generated_at","")
            source["last_checked_at"]=run_document.get("generated_at","")
            source["failure_reason"]=""
        elif result.get("status")=="Failed":
            source["integration_status"]="Failed"
            source["failure_reason"]=result.get("error", "ETL run failed")
    # Keep the inventory's integration state tied to persisted database rows,
    # even when latest_run.json describes only a single-source execution.
    try:
        from sqlalchemy import func, select
        from app.db.session import SessionLocal
        from app.models.schema import Fund, FundProfileSnapshot, NavObservation
        with SessionLocal() as session:
            fund_counts=dict(session.execute(select(Fund.source_id,func.count()).group_by(Fund.source_id)).all())
            nav_counts=dict(session.execute(select(Fund.source_id,func.count()).select_from(NavObservation).join(Fund,NavObservation.fund_id==Fund.id).group_by(Fund.source_id)).all())
            nav_source_counts=dict(session.execute(select(NavObservation.source_id,func.count()).where(NavObservation.source_id.is_not(None)).group_by(NavObservation.source_id)).all())
            profile_counts=dict(session.execute(select(FundProfileSnapshot.source_id,func.count()).group_by(FundProfileSnapshot.source_id)).all())
        for source in candidates:
            source_id=source.get("source_id")
            if profile_counts.get(source_id,0):
                source["integration_status"]="Integrated"
                source["verification_status"]="Usable Fund Data Confirmed"
                source["usable_fund_data_confirmed"]=True
                source["fund_profile_snapshots_loaded"]=profile_counts[source_id]
                source["records_loaded"]=max(source.get("records_loaded",0),profile_counts[source_id])
            if nav_source_counts.get(source_id,0):
                source["integration_status"]="Integrated"
                source["verification_status"]="Usable Fund Data Confirmed"
                source["usable_fund_data_confirmed"]=True
                source["nav_observations_loaded"]=nav_source_counts[source_id]
                source["records_loaded"]=max(source.get("records_loaded",0),nav_source_counts[source_id])
            if fund_counts.get(source_id,0):
                source["integration_status"]="Integrated"
                source["verification_status"]="Usable Fund Data Confirmed"
                source["usable_fund_data_confirmed"]=True
                source["records_loaded"]=fund_counts[source_id]
                source["nav_observations_loaded"]=nav_counts.get(source_id,0)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Could not read current database coverage: %s", exc)
    researched_codes={r["country_code"] for r in candidates}
    return country_rows(researched_codes)+candidates

def verify_sources() -> None:
    result=[]
    for src in catalogue():
        url=src.get("endpoint_url", "")
        row={"source_id":src["source_id"],"country_code":src["country_code"],"url":url,
             "checked_at":datetime.now(timezone.utc).isoformat(),"http_status":None,
             "content_type":None,"response_size":None,"preview":None,
             "verification_status":"Unavailable","usable_fund_data_confirmed":False,"error":None}
        try:
            if urlsplit(url).scheme not in {"http","https"} or not urlsplit(url).netloc:
                raise ValueError("Invalid HTTP(S) endpoint")
            response=httpx.get(url, timeout=timeout_seconds(), follow_redirects=True,
                headers={"User-Agent":user_agent(),"Accept":"application/json, text/csv, application/xml, text/html"})
            body=response.content
            preview=re.sub(r"(?i)(api[_-]?key|token|password)=([^&\s]+)",r"\1=[REDACTED]",body[:500].decode("utf-8",errors="replace"))
            ct=response.headers.get("content-type","")
            row.update(http_status=response.status_code,content_type=ct,response_size=len(body),preview=preview)
            if response.status_code in (401,403): row["verification_status"]="Authentication Required"
            elif response.status_code==429: row["verification_status"]="Blocked"
            elif response.status_code>=400: row["verification_status"]="Unavailable"
            elif "text/html" in ct: row["verification_status"]="Reachable" if "<html" in preview.lower() else "Accessible — No Fund Data"
            else: row["verification_status"]="Reachable"
            # Never infer usable fund data from an HTTP success or homepage response.
        except (httpx.HTTPError, ValueError) as exc:
            row["error"]=f"{type(exc).__name__}: {str(exc)[:300]}"
        result.append(row)
    REPORTS.mkdir(exist_ok=True)
    (REPORTS/"source_verification.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    lines=["# Source verification", "", f"Generated at {datetime.now(timezone.utc).isoformat()}", "",
      "A reachable homepage is not confirmation of fund-level data. No source is marked usable without a provider-specific parser and evidence.", "",
      "| Source | Country | Status | HTTP | Type | Bytes | Error |", "|---|---|---|---:|---|---:|---|"]
    for x in result: lines.append(f"| {x['source_id']} | {x['country_code']} | {x['verification_status']} | {x['http_status'] or ''} | {x['content_type'] or ''} | {x['response_size'] if x['response_size'] is not None else ''} | {(x['error'] or '').replace('|','/')} |")
    (REPORTS/"source_verification.md").write_text("\n".join(lines)+"\n")
    print(f"Checked {len(result)} candidate endpoints; report: reports/source_verification.json")

def generate_workbook() -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.formatting.rule import FormulaRule
    from openpyxl.worksheet.table import Table, TableStyleInfo
    from openpyxl.chart import BarChart, Reference
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.utils import get_column_letter
    rows=catalogue(); REPORTS.mkdir(exist_ok=True); path=REPORTS/"global_mutual_fund_source_inventory.xlsx"
    wb=Workbook(); dash=wb.active; dash.title="Dashboard"
    dash.append(["Global Mutual Fund ETL — Inventory Summary"])
    dash.append(["Metric","Count"])
    researched_codes={r.get("country_code") for r in rows if r.get("verification_status")!="Undiscovered"}
    dash.append(["Countries in required scope",24]); dash.append(["Countries with candidate research documented",len(researched_codes)]); dash.append(["Countries with discovery pending",24-len(researched_codes)])
    dash.append(["Candidate source records",len(rows)]); dash.append(["Usable sources confirmed",sum(r.get("usable_fund_data_confirmed") is True for r in rows)])
    dash.append(["Integrated sources",sum(r.get("integration_status")=="Integrated" for r in rows)])
    dash.append(["Verification status", "Count"])
    for status in ["Undiscovered","Discovered","Reachable","Authentication Required","Blocked","Unavailable","Accessible — No Fund Data","Usable Fund Data Confirmed"]:
        dash.append([status,sum(r.get("verification_status")==status for r in rows)])
    regional={"Asia-Pacific":("Asia-Pacific",["JP","CN","KR","AU","SG","HK","TW"]),"Europe":("Europe",["GB","DE","FR","IT","CH","NL","DK","SE","LU","IE"]),"North America":("North America",["US","CA","MX"]),"Other Markets":("Other markets",["RU","BR","AE","ZA"])}
    columns=["Source ID","Country","ISO country code","Region","Organization","Source name","Official website","API endpoint or download URL","API documentation URL","Source category","Access method","Authentication required","Data format","Fund master data available","Current NAV available","Historical NAV available","Holdings available","Currency information available","Available identifiers","Historical data coverage","Update frequency","Rate limits","Licensing status","Commercial reuse status","Endpoint verification status","Usable fund data confirmed","ETL implementation status","Integration test status","Last checked timestamp","Last successful ingestion timestamp","Records extracted","Records loaded","Error or blocker","Evidence URL","Research notes"]
    mapping={"Source ID":"source_id","Country":"country_name","ISO country code":"country_code","Region":"region","Organization":"organization","Source name":"source_name","Official website":"official_website","API endpoint or download URL":"endpoint_url","API documentation URL":"documentation_url","Source category":"source_category","Access method":"access_method","Authentication required":"authentication_required","Data format":"response_format","Fund master data available":"fund_master_available","Current NAV available":"current_nav_available","Historical NAV available":"historical_nav_available","Holdings available":"holdings_available","Currency information available":"available_currency_fields","Available identifiers":"available_identifiers","Historical data coverage":"historical_coverage","Update frequency":"update_frequency","Rate limits":"rate_limit_notes","Licensing status":"license_status","Commercial reuse status":"commercial_reuse_status","Endpoint verification status":"verification_status","Usable fund data confirmed":"usable_fund_data_confirmed","ETL implementation status":"integration_status","Integration test status":"integration_test_status","Last checked timestamp":"last_checked_at","Last successful ingestion timestamp":"last_successful_ingestion_at","Records extracted":"records_extracted","Records loaded":"records_loaded","Error or blocker":"failure_reason","Evidence URL":"evidence_url","Research notes":"notes"}
    sheets={"Asia-Pacific":"Asia-Pacific","Europe":"Europe","North America":"North America","Other Markets":"Other markets"}
    for title,region in sheets.items():
        ws=wb.create_sheet(title); ws.append(columns)
        header_columns = {name: index for index, name in enumerate(columns, start=1)}
        for row in rows:
            if row.get("region")==region: ws.append([row.get(mapping[c], "") for c in columns])
        ws.freeze_panes="A2"; ws.auto_filter.ref=ws.dimensions
        for row in ws.iter_rows(min_row=2):
            for name in ("Official website", "API endpoint or download URL", "API documentation URL", "Evidence URL"):
                cell=row[header_columns[name]-1]
                if isinstance(cell.value,str) and cell.value.startswith(("https://","http://")):
                    cell.hyperlink=cell.value; cell.style="Hyperlink"
        if ws.max_row>1:
            table=Table(displayName=title.replace(" ","")+"Sources",ref=ws.dimensions); table.tableStyleInfo=TableStyleInfo(name="TableStyleMedium2",showRowStripes=True,showColumnStripes=False); ws.add_table(table)
            for column, formula in [("Commercial reuse status",'"Permitted,Restricted,Permission Required,Unknown"'),("Endpoint verification status",'"Undiscovered,Discovered,Reachable,Authentication Required,Blocked,Unavailable,Accessible — No Fund Data,Usable Fund Data Confirmed"'),("ETL implementation status",'"Not Started,In Progress,Implemented,Tested,Integrated,Failed"')]:
                column = header_columns[column]
                dv=DataValidation(type="list",formula1=formula,allow_blank=True); ws.add_data_validation(dv); dv.add(f"{ws.cell(2,column).coordinate}:{ws.cell(ws.max_row,column).coordinate}")
            last=ws.max_row
            verification_col = get_column_letter(header_columns["Endpoint verification status"])
            integration_col = get_column_letter(header_columns["ETL implementation status"])
            ws.conditional_formatting.add(f"{verification_col}2:{verification_col}{last}",FormulaRule(formula=[f'OR({verification_col}2="Usable Fund Data Confirmed",{verification_col}2="Reachable")'],fill=PatternFill("solid",fgColor="C6EFCE")))
            ws.conditional_formatting.add(f"{verification_col}2:{verification_col}{last}",FormulaRule(formula=[f'OR({verification_col}2="Blocked",{verification_col}2="Unavailable")'],fill=PatternFill("solid",fgColor="FFC7CE")))
            ws.conditional_formatting.add(f"{integration_col}2:{integration_col}{last}",FormulaRule(formula=[f'{integration_col}2="Integrated"'],fill=PatternFill("solid",fgColor="C6EFCE")))
            ws.conditional_formatting.add(f"{integration_col}2:{integration_col}{last}",FormulaRule(formula=[f'OR({integration_col}2="Failed",{integration_col}2="Not Started")'],fill=PatternFill("solid",fgColor="FFEB9C")))
        for col in ws.columns:
            letter=col[0].column_letter; ws.column_dimensions[letter].width=min(42,max(14,max(len(str(c.value or "")) for c in col)+2))
        for cell in ws[1]: cell.font=Font(bold=True,color="FFFFFF"); cell.fill=PatternFill("solid",fgColor="17365D"); cell.alignment=Alignment(wrap_text=True)
    log=wb.create_sheet("Source Verification Log"); log.append(["Source ID","Country","Checked at","HTTP status","Format","Fund data confirmed","Status","Error","Evidence"])
    vp=REPORTS/"source_verification.json"
    if vp.exists():
        for x in json.loads(vp.read_text()): log.append([x.get("source_id"),x.get("country_code"),x.get("checked_at"),x.get("http_status"),x.get("content_type"),x.get("usable_fund_data_confirmed"),x.get("verification_status"),x.get("error"),x.get("url")])
    etl=wb.create_sheet("ETL Integration Status"); etl.append(["Source ID","Country","Connector","Integration status","Last successful run","Records extracted","Records loaded","Errors"])
    registered=all_connectors()
    for r in rows:
        etl.append([r.get("source_id"),r.get("country_code"),
          "Implemented" if r.get("source_id") in registered else "Not implemented",
          r.get("integration_status"),r.get("last_successful_ingestion_at",""),
          r.get("records_extracted",0),r.get("records_loaded",0),r.get("failure_reason","")])
    dd=wb.create_sheet("Data Dictionary"); dd.append(["Field","Meaning / accepted values"])
    for k,v in [("Country code","ISO 3166-1 alpha-2"),("Verification status","Undiscovered; Discovered; Reachable; Authentication Required; Blocked; Unavailable; Accessible — No Fund Data; Usable Fund Data Confirmed"),("Integration status","Not Started; In Progress; Implemented; Tested; Integrated; Failed"),("Licensing status","Permitted; Restricted; Permission Required; Unknown"),("Usable fund data confirmed","True only after actual fund-level records are inspected")]: dd.append([k,v])
    for ws in wb.worksheets:
        ws.freeze_panes="A2"
        for cell in ws[1]: cell.font=Font(bold=True,color="FFFFFF"); cell.fill=PatternFill("solid",fgColor="17365D"); cell.alignment=Alignment(wrap_text=True)
        ws.auto_filter.ref=ws.dimensions
    chart=BarChart(); chart.type="bar"; chart.style=10; chart.title="Sources by verification status"; chart.y_axis.title="Status"; chart.x_axis.title="Sources"
    status_header_row = next(cell.row for cell in dash["A"] if cell.value == "Verification status")
    chart.add_data(Reference(dash,min_col=2,min_row=status_header_row,max_row=dash.max_row),titles_from_data=True); chart.set_categories(Reference(dash,min_col=1,min_row=status_header_row+1,max_row=dash.max_row)); chart.height=7; chart.width=14; dash.add_chart(chart,"D2")
    wb.save(path); print(path)

def export_catalogue() -> None:
    REPORTS.mkdir(exist_ok=True)
    (REPORTS/"source_catalogue.json").write_text(json.dumps(catalogue(),indent=2,ensure_ascii=False)+"\n")
    if not (REPORTS/"sample_funds.json").exists(): (REPORTS/"sample_funds.json").write_text("[]\n")
    if not (REPORTS/"sample_nav.json").exists(): (REPORTS/"sample_nav.json").write_text("[]\n")

def export_database_samples() -> dict[str,int]:
    from sqlalchemy import select, func
    from app.db.session import SessionLocal
    from app.models.schema import Fund,NavObservation
    REPORTS.mkdir(exist_ok=True)
    with SessionLocal() as session:
        source_ids=session.scalars(select(Fund.source_id).distinct().order_by(Fund.source_id)).all()
        funds_json=[]; nav_json=[]; counts={"funds":0,"nav_observations":0,"by_source":{}}
        for source_id in source_ids:
            funds=session.scalars(select(Fund).where(Fund.source_id==source_id).order_by(Fund.source_fund_id).limit(100)).all()
            nav_rows=session.execute(select(Fund.source_fund_id,Fund.name,NavObservation.valuation_date,
              NavObservation.nav,NavObservation.currency,NavObservation.source_id,NavObservation.source_url).join(NavObservation,NavObservation.fund_id==Fund.id)
              .where(Fund.source_id==source_id).order_by(NavObservation.valuation_date.desc(),Fund.source_fund_id).limit(1000)).all()
            funds_json.extend({"source_id":f.source_id,"source_fund_id":f.source_fund_id,"name":f.name,
              "domicile_country":f.domicile_country,"currency":f.currency,"isin":f.isin} for f in funds)
            nav_json.extend({"source_id":source_id,"source_fund_id":row[0],"fund_name":row[1],
              "valuation_date":row[2].isoformat(),"nav":str(row[3]),"currency":row[4],
              "observation_source_id":row[5],"source_url":row[6]} for row in nav_rows)
            fund_count=session.scalar(select(func.count()).select_from(Fund).where(Fund.source_id==source_id)) or 0
            nav_count=session.scalar(select(func.count()).select_from(NavObservation).join(Fund,NavObservation.fund_id==Fund.id).where(Fund.source_id==source_id)) or 0
            counts["by_source"][source_id]={"funds":fund_count,"nav_observations":nav_count}
            counts["funds"]+=fund_count; counts["nav_observations"]+=nav_count
    (REPORTS/"sample_funds.json").write_text(json.dumps(funds_json,indent=2,ensure_ascii=False)+"\n")
    (REPORTS/"sample_nav.json").write_text(json.dumps(nav_json,indent=2,ensure_ascii=False)+"\n")
    return counts

def write_latest_run_report(run: dict,counts: dict[str,int]) -> None:
    from app.config import database_url
    timestamp=run.get("generated_at","")
    rows=run.get("results",[])
    lines=["# Latest execution report","",f"Generated at: {timestamp}","",
      "## Ingestion results","","| Source | Status | Funds extracted | Funds loaded | NAV observations upserted | Rejected rows | Error |",
      "|---|---|---:|---:|---:|---:|---|"]
    for row in rows:
        lines.append(f"| {row.get('source_id','')} | {row.get('status','')} | {row.get('records_extracted',0)} | {row.get('records_loaded',0)} | {row.get('navs_loaded',0)} | {row.get('rejected_records',0)} | {(row.get('error') or '').replace('|','/')} |")
    db_url=database_url()
    storage_note=("Temporary PostgreSQL validation cluster under /tmp; records are not in the configured Docker database." if "/tmp/mfetl-sock" in db_url else "Configured project PostgreSQL database.")
    lines += ["","## Database counts","","| Source | Funds | NAV observations |","|---|---:|---:|"]
    for source_id,source_counts in counts.get("by_source",{}).items():
        lines.append(f"| {source_id} | {source_counts['funds']} | {source_counts['nav_observations']} |")
    lines += [f"| **Total** | **{counts['funds']}** | **{counts['nav_observations']}** |",
      f"- Database used: {storage_note}",
      "- Raw snapshots are ignored by Git; source manifests record URLs, checksums, and sizes.",
      "- Source rejects are recorded in source-specific JSONL files under `reports/`.",
      "- Sample exports contain actual database rows: `sample_funds.json` and `sample_nav.json`.",
      "- Commercial reuse rights require separate review for all providers.",""]
    (REPORTS/"latest_run.md").write_text("\n".join(lines))

def sync_sources() -> None:
    from sqlalchemy.dialects.postgresql import insert
    from app.db.session import SessionLocal
    from app.models.schema import Source
    values=[]
    rows=catalogue()
    for row in rows:
        values.append({"source_id":row["source_id"],"country_code":row["country_code"],
          "organization":str(row.get("organization","Unknown")),"source_name":row.get("source_name","Unknown"),
          "endpoint_url":row.get("endpoint_url") or None,
          "verification_status":row.get("verification_status","Undiscovered"),
          "integration_status":row.get("integration_status","Not Started"),
          "license_status":row.get("license_status","Unknown")})
    with SessionLocal() as session:
        for row in values:
            stmt=insert(Source).values(**row).on_conflict_do_update(index_elements=[Source.source_id],set_={k:v for k,v in row.items() if k!="source_id"})
            session.execute(stmt)
        session.commit()
    print(f"Synchronized {len(values)} catalog source/country rows.")

# source_id -> (module, function, extra positional args). Imported lazily so the CLI starts fast.
_DOWNLOADERS={
    "dk_bde_nonmonetary_funds":("app.connectors.denmark_bde_funds","download_denmark_fund_list",()),
    "de_bde_nonmonetary_funds":("app.connectors.bde_european_funds","download_bde_fund_list",("DE",)),
    "it_bde_nonmonetary_funds":("app.connectors.bde_european_funds","download_bde_fund_list",("IT",)),
    "nl_bde_nonmonetary_funds":("app.connectors.bde_european_funds","download_bde_fund_list",("NL",)),
    "lu_bde_nonmonetary_funds":("app.connectors.bde_european_funds","download_bde_fund_list",("LU",)),
    "hk_sfc_authorised_unit_trusts":("app.connectors.hk_sfc_funds","download_hk_sfc_fund_list",()),
    "amf_geco":("app.connectors.amf_geco","download_amf_geco",()),
    "cbi_authorised_ucits":("app.connectors.central_bank_ireland","download_ireland_ucits_register",()),
    "fi_sweden_ucits_holdings":("app.connectors.fi_sweden","download_fi_sweden",()),
    "cnmv_spanish_fund_register":("app.connectors.cnmv","download_cnmv_fund_register",()),
    "sec_open_end_fund_classes":("app.connectors.sec","download_sec_series_classes",()),
    "fca_authorised_funds":("app.connectors.fca","download_fca_fund_register",()),
    "finma_swiss_fund_list":("app.connectors.finma","download_finma_fund_list",()),
    "asisa_cis_fund_list":("app.connectors.asisa","download_asisa_fund_list",()),
    "jp_imaj_nisa_growth_funds":("app.connectors.japan_funds","download_imaj_growth_funds",()),
    "jp_fsa_tsumitate_funds":("app.connectors.japan_funds","download_fsa_tsumitate_funds",()),
    "jp_imaj_new_funds":("app.connectors.japan_funds","download_imaj_new_funds",()),
    "kr_ibk_fund_information":("app.connectors.korea_funds","download_ibk_funds",()),
    "gsfm_unit_prices":("app.connectors.gsfm","download_gsfm_prices",()),
    "csrc_public_fund_index":("app.connectors.csrc","download_csrc_index",()),
}

def _download_handler(source: str):
    """Return a ``fn(refresh=...)`` downloader for ``source``, or None if it uses the CVM path."""
    entry=_DOWNLOADERS.get(source)
    if entry is None: return None
    import importlib
    module,name,extra=entry
    function=getattr(importlib.import_module(module),name)
    return lambda refresh: function(*extra,refresh=refresh)

def main() -> None:
    parser=argparse.ArgumentParser(prog="mfetl"); sub=parser.add_subparsers(dest="cmd",required=True)
    sub.add_parser("verify-sources"); sub.add_parser("inventory"); sub.add_parser("sync-sources")
    sec_holdings=sub.add_parser("sync-sec-holdings"); sec_holdings.add_argument("--fund-id", type=int, action="append", help="Limit the sync to a local US fund ID; repeat to select multiple funds")
    sec_holdings.add_argument("--history-days", type=int, default=450, help="Import all N-PORT report periods filed within this rolling window (default: 450)")
    sec_holdings.add_argument("--latest-only", action="store_true", help="Import only the newest available N-PORT report per series")
    sec_holdings.add_argument("--cache-downloads", action="store_true", help="Save SEC filing bodies under data/raw/united_states/nport_filings")
    sec_bulk=sub.add_parser("sync-sec-nport-bulk", help="Import the official SEC Form N-PORT quarterly bulk data set for all matched US series")
    sec_bulk.add_argument("--quarter", help="Data set quarter such as 2026q3 (default: newest safely published quarter)")
    sec_bulk.add_argument("--only-missing", action="store_true", help="Only import funds that currently have no stored holdings")
    sec_bulk.add_argument("--refresh", action="store_true", help="Redownload the SEC archive even if it is already cached")
    sec_bulk.add_argument("--no-identifiers", action="store_true", help="Skip the reported ISIN/ticker identifier join")
    sec_nmfp=sub.add_parser("sync-sec-nmfp", help="Import official SEC money-market class NAV history (currency remains unassigned)")
    sec_nmfp.add_argument("--fund-id", type=int, action="append", help="Limit to local US fund IDs; repeat to select multiple funds")
    sec_nmfp.add_argument("--lookback-days", type=int, default=450, help="Look back this many days in SEC filing history")
    sec_nmfp_bulk=sub.add_parser("sync-sec-nmfp-bulk", help="Import official SEC N-MFP monthly bulk holdings, adviser/administrator profiles and optional USD class NAV")
    sec_nmfp_bulk.add_argument("--months", type=int, default=1, help="Number of newest monthly N-MFP bulk archives to download (default: 1)")
    sec_nmfp_bulk.add_argument("--all", action="store_true", help="Include funds that already have holdings instead of only funds with no stored holdings")
    sec_nmfp_bulk.add_argument("--assign-usd-nav", action="store_true", help="Store class daily NAV as USD observations for U.S. domiciled money-market funds")
    sec_nmfp_bulk.add_argument("--no-profiles", action="store_true", help="Skip manager, administrator and category profile updates")
    sec_nmfp_bulk.add_argument("--refresh", action="store_true", help="Redownload and re-extract cached monthly archives")
    sec_ncen=sub.add_parser("sync-sec-ncen-bulk", help="Import SEC N-CEN annual bulk data (fees, NAV snapshot, adviser/administrator, classification)")
    sec_ncen.add_argument("--quarters", type=int, default=8, help="Number of newest quarterly N-CEN archives to scan (default: 8)")
    sec_ncen.add_argument("--refresh", action="store_true", help="Redownload and re-extract cached quarterly archives")
    sec_ncen.add_argument("--no-profiles", action="store_true", help="Skip manager, administrator and net-assets fund-field updates")
    sec_ncen.add_argument("--no-nav", action="store_true", help="Skip canonical NAV rows for single-class series")
    sec_ncsr=sub.add_parser("sync-sec-ncsr-tsr", help="Import SEC N-CSR/N-CSRS Tailored Shareholder Report XBRL (ticker, inception, fees, returns, sector weights)")
    sec_ncsr.add_argument("--since-days", type=int, default=420, help="Only read N-CSR/N-CSRS filings from this rolling window (default: 420)")
    sec_ncsr.add_argument("--max-filings", type=int, default=8, help="Maximum N-CSR/N-CSRS filings per registrant CIK (default: 8)")
    sec_ncsr.add_argument("--limit", type=int, help="Process only the first N registrant CIKs (for a dry run)")
    sec_ncsr.add_argument("--cik", action="append", help="Limit to a registrant CIK; repeat to select multiple")
    sec_ncsr.add_argument("--only-gaps", action="store_true", help="Only select funds missing ticker, inception or net assets")
    sec_ncsr.add_argument("--refresh", action="store_true", help="Redownload submissions, indexes and XBRL instances")
    sec_ncsr.add_argument("--no-profiles", action="store_true", help="Write profile snapshots without updating fund fields")
    sec_ncsr.add_argument("--dry-run", action="store_true", help="Parse and report fills without writing to the database")
    sec_ncsr.add_argument("--workers", type=int, default=4, help="Parallel registrant fetch/parse workers (default: 4)")
    sec_ncsr.add_argument("--batch-size", type=int, default=100, help="Commit after this many registrants (default: 100)")
    sec_rr=sub.add_parser("sync-sec-rr-profiles", help="Fill US class inception dates and tickers from SEC N-1A risk/return XBRL data sets")
    sec_rr.add_argument("--quarters", type=int, default=8, help="Number of newest quarterly archives to scan (default: 8; use 60 for the full history)")
    sec_rr.add_argument("--refresh", action="store_true", help="Redownload cached archives")
    sec_rr.add_argument("--no-tickers", action="store_true", help="Only fill inception dates")
    sec_rr.add_argument("--dry-run", action="store_true", help="Report what would be filled without writing")
    sec_profiles=sub.add_parser("sync-sec-class-profiles", help="Import cached SEC fund class metadata into profile snapshots")
    sec_profiles.add_argument("--fund-id", type=int, action="append", help="Limit to local US fund IDs; repeat to select multiple funds")
    sec_profiles.add_argument("--dry-run", action="store_true", help="Report exact matches without writing to the database")
    sec_cache=sub.add_parser("sync-cached-sec-history", help="Import already cached SEC N-PORT history for selected US funds; makes no network requests")
    sec_cache.add_argument("--fund-id", type=int, action="append", required=True, help="Local US fund ID; repeat to select multiple funds")
    snapshot=sub.add_parser("fetch-snapshot", help="Fetch one reproducible file-based source export")
    snapshot.add_argument("--source", required=True, choices=["it_borsa_navs","fr_lacotebleue_navs","nl_euronext_fund_navs","lu_euronext_fund_navs","lu_allianz_daily_navs"])
    snapshot.add_argument("--url", required=True, help="Direct CSV export URL published by the source")
    eu_ids=sub.add_parser("sync-eu-fund-ids", help="Attach share-class ISINs, LEIs and register data to IE/LU funds from ESMA FIRDS, the ESMA cross-border register and the HMRC reporting-funds list"); eu_ids.add_argument("--refresh", action="store_true", help="Re-download source files"); eu_ids.add_argument("--dry-run", action="store_true")
    fi_se_holdings=sub.add_parser("sync-fi-sweden-holdings", help="Import FI quarterly UCITS holdings, fees, benchmark and risk for Swedish funds from the downloaded XML")
    cvm_holdings=sub.add_parser("sync-cvm-holdings"); cvm_holdings.add_argument("--month", required=True, help="CVM CDA reporting month in YYYYMM format"); cvm_holdings.add_argument("--archive", action="append", default=None, help="Manually downloaded CDA zip (repeatable); use when CVM blocks automated downloads")
    enrich_us=sub.add_parser("enrich-us-funds", help="Enrich US mutual fund net assets, tickers, ISINs, Vanguard profiles, and official issuer NAVs")
    enrich_us.add_argument("--all", action="store_true", help="Run all enrichment adapters sequentially")
    enrich_us.add_argument("--net-assets", action="store_true", help="Enrich net assets and net assets dates from SEC N-PORT bulk")
    enrich_us.add_argument("--tickers", action="store_true", help="Enrich tickers from official live SEC endpoint")
    enrich_us.add_argument("--isins", action="store_true", help="Enrich CUSIPs and ISINs from verified N-PORT holdings")
    enrich_us.add_argument("--vanguard", action="store_true", help="Sync Vanguard directory profiles, inception dates, and expense ratios")
    enrich_us.add_argument("--issuer-navs", action="store_true", help="Sync official issuer NAVs (Vanguard, Capital Group, SSGA/SPDR, GraniteShares)")
    enrich_us.add_argument("--issuer-navs-missing", action="store_true", help="Sync issuer NAVs only for funds that still have no NAV observation")
    enrich_us.add_argument("--dry-run", action="store_true", help="Simulate without committing database changes")
    enrich_us.add_argument("--no-audit", action="store_true", help="Skip running post-enrichment audit")
    sub.add_parser("audit-us-coverage", help="Run comprehensive US fund data completeness audit")
    download=sub.add_parser("download"); download.add_argument("--source",default="cvm_open_fund_data"); download.add_argument("--start-date"); download.add_argument("--end-date"); download.add_argument("--refresh",action="store_true")
    run=sub.add_parser("run"); run.add_argument("--all",action="store_true"); run.add_argument("--country"); run.add_argument("--source", action="append"); run.add_argument("--start-date"); run.add_argument("--end-date")
    args=parser.parse_args()
    if args.cmd=="verify-sources": verify_sources()
    elif args.cmd=="inventory":
        export_catalogue(); generate_workbook()
    elif args.cmd=="sync-sources": sync_sources()
    elif args.cmd=="fetch-snapshot":
        from app.connectors.snapshots import fetch_snapshot
        print(json.dumps(fetch_snapshot(args.source, args.url), indent=2))
    elif args.cmd=="sync-sec-holdings":
        from app.holdings.sec_nport import sync_sec_holdings
        print(json.dumps(tracked_run("sec-nport-filings", lambda: sync_sec_holdings(set(args.fund_id) if args.fund_id else None,
            history_days=args.history_days,cache_downloads=args.cache_downloads,
            latest_only=args.latest_only)),indent=2))
    elif args.cmd=="sync-sec-nport-bulk":
        from app.holdings.sec_nport_bulk import import_nport_bulk
        print(json.dumps(tracked_run("sec-nport-bulk", lambda: import_nport_bulk(
            args.quarter, only_missing=args.only_missing, refresh=args.refresh,
            include_identifiers=not args.no_identifiers)), indent=2))
    elif args.cmd=="sync-sec-nmfp":
        from app.holdings.sec_nmfp import sync_sec_nmfp
        print(json.dumps(tracked_run("sec-nmfp", lambda: sync_sec_nmfp(set(args.fund_id) if args.fund_id else None,
            lookback_days=args.lookback_days)),indent=2))
    elif args.cmd=="sync-sec-nmfp-bulk":
        from app.holdings.sec_nmfp_bulk import sync_sec_nmfp_bulk
        print(json.dumps(tracked_run("sec-nmfp-bulk", lambda: sync_sec_nmfp_bulk(months=args.months, only_missing=not args.all,
            assign_usd_nav=args.assign_usd_nav, update_profiles=not args.no_profiles,
            refresh=args.refresh)),indent=2))
    elif args.cmd=="sync-sec-ncen-bulk":
        from app.enrichment.sec_ncen_bulk import sync_sec_ncen_bulk
        print(json.dumps(tracked_run("sec-ncen-bulk", lambda: sync_sec_ncen_bulk(quarters=args.quarters, refresh=args.refresh,
            update_profiles=not args.no_profiles, write_nav=not args.no_nav)), indent=2))
    elif args.cmd=="sync-sec-rr-profiles":
        from app.enrichment.sec_rr_profile import sync_sec_rr_profiles
        job=lambda: sync_sec_rr_profiles(quarters=args.quarters,refresh=args.refresh,dry_run=args.dry_run,fill_tickers=not args.no_tickers)
        print(json.dumps(job() if args.dry_run else tracked_run("sec-rr-profiles",job),indent=2,default=str))
    elif args.cmd=="sync-sec-ncsr-tsr":
        from app.enrichment.sec_ncsr_tsr import sync_sec_ncsr_tsr
        job=lambda: sync_sec_ncsr_tsr(
            since_days=args.since_days, max_filings=args.max_filings,
            limit=args.limit, ciks=set(args.cik) if args.cik else None,
            refresh=args.refresh, update_profiles=not args.no_profiles,
            only_gaps=args.only_gaps, dry_run=args.dry_run,
            batch_size=args.batch_size, workers=args.workers)
        print(json.dumps(job() if args.dry_run else tracked_run("sec-ncsr-tsr",job),indent=2,default=str))
    elif args.cmd=="sync-sec-class-profiles":
        from app.holdings.sec_class_profiles import sync_sec_class_profiles
        print(json.dumps(sync_sec_class_profiles(set(args.fund_id) if args.fund_id else None,
            dry_run=args.dry_run),indent=2))
    elif args.cmd=="sync-cached-sec-history":
        from app.holdings.sec_nport import sync_cached_sec_history
        print(json.dumps(sync_cached_sec_history(set(args.fund_id)),indent=2))
    elif args.cmd=="sync-eu-fund-ids":
        from app.enrichment.eu_fund_ids import sync_eu_fund_ids
        print(json.dumps(sync_eu_fund_ids(refresh=args.refresh, dry_run=args.dry_run) if args.dry_run else tracked_run("eu-fund-ids", lambda: sync_eu_fund_ids(refresh=args.refresh)),indent=2,default=str))
    elif args.cmd=="sync-fi-sweden-holdings":
        from app.holdings.fi_sweden import sync_fi_sweden_holdings
        from app.connectors.fi_sweden import download_fi_sweden
        download_fi_sweden()
        print(json.dumps(tracked_run("fi-sweden-holdings", sync_fi_sweden_holdings),indent=2))
    elif args.cmd=="sync-cvm-holdings":
        from app.holdings.cvm_cda import sync_cvm_holdings
        print(json.dumps(tracked_run("cvm-cda-holdings", lambda: sync_cvm_holdings(args.month, [Path(a) for a in args.archive] if args.archive else None)),indent=2))
    elif args.cmd=="audit-us-coverage":
        from scripts.audit_complete_us_coverage import run_audit
        res = run_audit()
        print(f"Audit completed: {res['total_us_funds']:,} US funds evaluated.")
    elif args.cmd=="enrich-us-funds":
        from app.enrichment.us_fund_enricher import (
            enrich_net_assets_from_nport_bulk,
            enrich_tickers_from_sec_live,
            enrich_isins_from_holdings,
            enrich_from_vanguard_directory,
            enrich_official_issuer_navs,
            run_us_fund_enrichment,
        )
        if args.all or not (args.net_assets or args.tickers or args.isins or args.vanguard or args.issuer_navs or args.issuer_navs_missing):
            res = tracked_run("enrich-us-funds", lambda: run_us_fund_enrichment(dry_run=args.dry_run, run_audit_after=not args.no_audit))
        else:
            res = {}
            if args.net_assets:
                res["net_assets"] = enrich_net_assets_from_nport_bulk(dry_run=args.dry_run)
            if args.tickers:
                res["tickers"] = enrich_tickers_from_sec_live(dry_run=args.dry_run)
            if args.isins:
                res["isins"] = enrich_isins_from_holdings(dry_run=args.dry_run)
            if args.vanguard:
                res["vanguard"] = enrich_from_vanguard_directory(dry_run=args.dry_run)
            if args.issuer_navs:
                res["issuer_navs"] = enrich_official_issuer_navs(only_missing=False)
            if args.issuer_navs_missing:
                res["issuer_navs_missing"] = enrich_official_issuer_navs(only_missing=True)
            if not args.no_audit and not args.dry_run:
                from scripts.audit_complete_us_coverage import run_audit
                res["post_audit"] = run_audit()
        print(json.dumps(res, indent=2, default=str))
    elif args.cmd=="download":
        handler=_download_handler(args.source)
        if handler is not None:
            print(json.dumps(handler(refresh=args.refresh),indent=2,ensure_ascii=False))
            return
        if args.source!="cvm_open_fund_data": raise SystemExit(f"No downloader registered for {args.source!r}.")
        from app.connectors.cvm import download_cvm_data
        today=datetime.now(timezone.utc).date()
        start=date.fromisoformat(args.start_date) if args.start_date else date(today.year,today.month,1)
        end=date.fromisoformat(args.end_date) if args.end_date else today
        if start>end: raise SystemExit("--start-date must be on or before --end-date")
        months=[]; year,month=start.year,start.month
        while (year,month)<=(end.year,end.month):
            months.append(f"{year:04d}{month:02d}"); month+=1
            if month==13: year,month=year+1,1
        results=download_cvm_data(months,refresh=args.refresh)
        print(json.dumps(results,indent=2))
    else:
        candidates=all_connectors()
        skipped_results=[]
        if args.source:
            selected=set(args.source)
            missing=selected-candidates.keys()
            if missing: raise SystemExit(f"No connector registered for source(s) {', '.join(sorted(missing))}; no ingestion was performed.")
            candidates={k:v for k,v in candidates.items() if k in selected}
        elif args.country:
            codes={r[0] for r in __import__("app.catalog",fromlist=["COUNTRIES"]).COUNTRIES if r[0]==args.country.upper()}
            ids={r["source_id"] for r in catalogue() if r.get("country_code") in codes}
            candidates={k:v for k,v in candidates.items() if k in ids}
            if not candidates: raise SystemExit(f"No connector registered for country {args.country.upper()}; no ingestion was performed.")
        elif not args.all:
            raise SystemExit("Select --all, --country, or one or more --source options.")
        elif args.all:
            # Never make a clean checkout's scheduled run fail because a
            # source-specific local export was not supplied. Report every skip.
            required_files = {
                "au_user_managed_funds": [ROOT / "data/raw/australia/australian_managed_funds.csv"],
                "us_qqqm_etf": [ROOT / "data/raw/united_states/qqqm_nav.csv"],
                "scotia_canada_daily_nav": [ROOT / "data/raw/canada/scotia_daily_nav.xlsx"],
                "bmv_mexico_funds": [ROOT / "data/raw/mexico/bmv_mexico_funds.csv", ROOT / "data/raw/mexico/bmv_mexico_navs.csv"],
                "de_bundesanzeiger_navs": [ROOT / "data/raw/germany/bundesanzeiger_fund_prices.csv"],
                "it_borsa_navs": [ROOT / "data/raw/italy/borsa_italiana_daily_nav.csv"],
                "fr_lacotebleue_navs": [ROOT / "data/raw/france/lacote_bleue_navs.csv"],
                "nl_euronext_fund_navs": [ROOT / "data/raw/netherlands/euronext_amsterdam_funds.csv"],
                "lu_euronext_fund_navs": [ROOT / "data/raw/luxembourg/euronext_luxembourg_funds.csv"],
                "lu_allianz_daily_navs": [ROOT / "data/raw/luxembourg/allianz_luxembourg_daily_nav.csv"],
                "uk_fundslibrary_unit_prices": [ROOT / "data/raw/united_kingdom/fundslibrary_unit_prices.csv"],
                "uk_ft_morningstar_prices": [ROOT / "data/raw/united_kingdom/ft_morningstar_fund_prices.csv"],
                "de_bundesanzeiger_navs": [ROOT / "data/raw/germany/bundesanzeiger_fund_prices.csv"],
            }
            for source_id, paths in required_files.items():
                if source_id in candidates and not all(path.is_file() for path in paths):
                    candidates.pop(source_id)
                    skipped_results.append({"source_id": source_id, "status": "Skipped",
                        "error": "Required local snapshot is absent; see docs/RAW_SNAPSHOTS.md for retrieval steps."})
        if not candidates:
            raise SystemExit("No runnable provider connectors are registered; no ingestion was performed.")
        from app.etl.orchestrator import run_many
        with etl_lock():
            run_results=run_many(candidates,start_date=date.fromisoformat(args.start_date) if args.start_date else None,end_date=date.fromisoformat(args.end_date) if args.end_date else None)
        results=skipped_results+run_results
        REPORTS.mkdir(exist_ok=True)
        run_report={"generated_at":datetime.now(timezone.utc).isoformat(),"results":results}
        (REPORTS/"latest_run.json").write_text(json.dumps(run_report,indent=2)+"\n")
        if any(row.get("status")=="Succeeded" for row in results):
            counts=export_database_samples()
            write_latest_run_report(run_report,counts)
        print(json.dumps(results,indent=2))
        failed=any(row.get("status")=="Failed" for row in results)
        succeeded=any(row.get("status")=="Succeeded" for row in results)
        if failed and (not args.all or not succeeded):
            raise SystemExit(1)

if __name__=="__main__": main()
