from datetime import date, datetime, timezone
from sqlalchemy.dialects.postgresql import insert
from pydantic import ValidationError
from app.db.session import SessionLocal
from app.etl.transform import fund_from_source, nav_from_source
from app.etl.load import upsert_funds_batch, upsert_navs_batch
from app.models.schema import Source, EtlRun

def run_connector(source_id: str, connector_type, *, start_date: date | None=None, end_date: date | None=None) -> dict:
    connector=connector_type()
    meta=connector.get_source_metadata()
    # Ensure the FK target and the run row are durable before extraction. A
    # connector failure must still leave an auditable failed run.
    with SessionLocal() as session:
        source_stmt=insert(Source).values(source_id=source_id,country_code=meta["country_code"],organization=meta["organization"],source_name=meta["source_name"],endpoint_url=meta.get("endpoint_url"),verification_status="Discovered",integration_status="In Progress",license_status=meta.get("license_status","Unknown"))
        source_stmt=source_stmt.on_conflict_do_update(index_elements=[Source.source_id],set_={"organization":source_stmt.excluded.organization,"source_name":source_stmt.excluded.source_name,"endpoint_url":source_stmt.excluded.endpoint_url})
        session.execute(source_stmt)
        run=EtlRun(source_id=source_id,status="In Progress"); session.add(run); session.commit()
        extracted=loaded=navs_loaded=0
        try:
            availability=connector.check_availability()
            if availability.get("available") is False: raise RuntimeError(availability.get("reason","Source unavailable"))
            batch=[]
            def load_batch(records):
                nonlocal extracted,loaded,navs_loaded
                prepared_by_id={}
                for raw in records:
                    extracted+=1
                    row=dict(raw)
                    nav_rows=row.pop("_navs",None)
                    fund=fund_from_source(source_id,row)
                    prepared_by_id[fund.source_fund_id]=(fund,nav_rows)
                prepared=list(prepared_by_id.values())
                fund_ids=upsert_funds_batch(session,source_id,[fund for fund,_ in prepared])
                nav_batch=[]
                for fund,nav_rows in prepared:
                    source_navs=nav_rows if nav_rows is not None else connector.extract_nav_history(fund.source_fund_id,start_date,end_date)
                    for nav_raw in source_navs:
                        try:
                            nav=nav_from_source(source_id,{**nav_raw,"source_fund_id":fund.source_fund_id})
                        except ValidationError as exc:
                            # A malformed/zero NAV must not discard an otherwise valid
                            # fund batch. Keep the rejection for source-level reporting.
                            getattr(connector,"_rejects",[]).append({
                                "record": {"source_fund_id": fund.source_fund_id, **nav_raw},
                                "error": str(exc),
                            })
                            continue
                        nav_batch.append((fund_ids[fund.source_fund_id],nav))
                    loaded+=1
                # Dedupe the full fund batch before chunking so duplicate
                # valuation keys are counted and written once (last wins).
                unique_navs={}
                for fund_id, nav in nav_batch:
                    unique_navs[(fund_id, nav.valuation_date, nav.currency)]=(fund_id, nav)
                nav_batch=list(unique_navs.values())
                for offset in range(0,len(nav_batch),4000):
                    upsert_navs_batch(session,nav_batch[offset:offset+4000])
                navs_loaded+=len(nav_batch)
            for raw in connector.extract_funds(start_date,end_date):
                batch.append(raw)
                if len(batch)>=300:
                    load_batch(batch); batch=[]
            if batch: load_batch(batch)
            run.status="Succeeded"; run.records_extracted=extracted; run.records_loaded=loaded; run.finished_at=datetime.now(timezone.utc)
            session.execute(insert(Source).values(source_id=source_id,country_code=meta["country_code"],organization=meta["organization"],source_name=meta["source_name"],endpoint_url=meta.get("endpoint_url"),verification_status="Usable Fund Data Confirmed" if extracted else "Accessible — No Fund Data",integration_status="Integrated" if extracted else "Tested",license_status=meta.get("license_status","Unknown")).on_conflict_do_update(index_elements=[Source.source_id],set_={"verification_status":"Usable Fund Data Confirmed" if extracted else "Accessible — No Fund Data","integration_status":"Integrated" if extracted else "Tested"}))
            session.commit()
            return {"source_id":source_id,"status":"Succeeded","records_extracted":extracted,"records_loaded":loaded,
              "navs_loaded":navs_loaded,"rejected_records":len(getattr(connector,"_rejects",[]))}
        except Exception as exc:
            session.rollback()
            with SessionLocal() as error_session:
                failed=error_session.get(EtlRun, run.id)
                if failed is not None:
                    failed.status="Failed"; failed.records_extracted=extracted
                    failed.records_loaded=loaded
                    failed.error=f"{type(exc).__name__}: {str(exc)[:1000]}"
                    failed.finished_at=datetime.now(timezone.utc)
                    error_session.commit()
            return {"source_id":source_id,"status":"Failed","records_extracted":extracted,"records_loaded":loaded,
              "navs_loaded":navs_loaded,"error":f"{type(exc).__name__}: {str(exc)[:300]}"}

def run_many(connectors: dict, *, start_date: date | None=None, end_date: date | None=None) -> list[dict]:
    results=[]
    for source_id,connector in connectors.items():
        try: results.append(run_connector(source_id,connector,start_date=start_date,end_date=end_date))
        except Exception as exc: results.append({"source_id":source_id,"status":"Failed","error":f"{type(exc).__name__}: {str(exc)[:300]}"})
    return results
