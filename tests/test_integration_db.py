"""Real-PostgreSQL checks: migrations, upsert SQL, run tracking and the ETL lock.

Skipped unless INTEGRATION_DATABASE_URL points at an empty, disposable database.
"""
import os
import subprocess
import sys
from datetime import date
from decimal import Decimal

import pytest

URL = os.getenv("INTEGRATION_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="INTEGRATION_DATABASE_URL not set")


@pytest.fixture(scope="module")
def db():
    env = {**os.environ, "DATABASE_URL": URL}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True, env=env)
    os.environ["DATABASE_URL"] = URL
    from app.db.session import SessionLocal, engine
    return SessionLocal, engine


class Conn:
    source_id = "it_test"

    def get_source_metadata(self):
        return {"country_code": "US", "organization": "Org", "source_name": "Src"}

    def check_availability(self):
        return {"available": True}

    def extract_funds(self, start_date=None, end_date=None):
        yield {"source_fund_id": "A", "name": "Fund A", "domicile_country": "US", "_navs": [
            {"valuation_date": "2026-01-02", "nav": "10.5", "currency": "USD"},
            {"valuation_date": "2026-01-02", "nav": "10.6", "currency": "USD"},  # duplicate: last wins
            {"valuation_date": "2026-01-03", "nav": "0", "currency": "USD"}]}       # rejected


def test_orchestrator_is_idempotent_and_records_rejects(db):
    from sqlalchemy import select, func
    from app.etl.orchestrator import run_connector
    from app.models.schema import EtlRun, NavObservation
    SessionLocal, _ = db
    import os as _os
    _os.environ["ETL_MAX_REJECT_RATE"] = "0.9"
    first = run_connector("it_test", Conn)
    second = run_connector("it_test", Conn)
    assert first["status"] == second["status"] == "Succeeded"
    with SessionLocal() as s:
        rows = s.scalars(select(NavObservation)).all()
        assert len(rows) == 1 and rows[0].nav == Decimal("10.6") and rows[0].valuation_date == date(2026, 1, 2)
        assert s.scalar(select(func.max(EtlRun.records_rejected))) == 1


def test_tracked_run_records_and_lock_is_exclusive(db):
    from sqlalchemy import select
    from app.etl.runs import tracked_run, etl_lock
    from app.models.schema import EtlRun
    SessionLocal, _ = db
    assert tracked_run("noop", lambda: {"holding_rows_inserted": 3}) == {"holding_rows_inserted": 3}
    with pytest.raises(ValueError):
        tracked_run("boom", lambda: (_ for _ in ()).throw(ValueError("x")))
    with SessionLocal() as s:
        runs = s.scalars(select(EtlRun).order_by(EtlRun.id.desc()).limit(2)).all()
        assert runs[0].status == "Failed" and "boom" in runs[0].error
        assert runs[1].status == "Succeeded" and runs[1].records_loaded == 3
    # A second process-level holder must be refused while the lock is held.
    from sqlalchemy import text
    _, engine = db
    with etl_lock():
        with engine.connect() as other:
            assert other.execute(text("SELECT pg_try_advisory_lock(7123094102)")).scalar() is False


def test_holdings_status_check_constraint(db):
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError
    SessionLocal, _ = db
    with SessionLocal() as s:
        with pytest.raises(IntegrityError):
            s.execute(text("UPDATE funds SET holdings_status='bogus'"))
            s.execute(text("INSERT INTO funds(source_id,source_fund_id,name,holdings_status) VALUES('it_test','Z','Z','bogus')"))
            s.commit()
