"""Shared run tracking and cross-process locking for every ingestion path.

* ``etl_lock`` takes the same Postgres advisory lock the Express API uses
  (``LOCK_ID`` in ``api/src/services/runStore.js``), so a CLI/GitHub Actions
  run and an API-launched run can never write concurrently.
* ``tracked_run`` records an ``etl_runs`` row for jobs that bypass the
  connector orchestrator (SEC bulk imports, enrichment), so every writer is
  auditable in one place.
"""
from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Callable, Iterator

from sqlalchemy import text

from app.db.session import SessionLocal, engine
from app.models.schema import EtlRun

# Must match LOCK_ID in api/src/services/runStore.js.
LOCK_ID = 7123094102


def _wait_seconds() -> float:
    try:
        return float(os.getenv("ETL_LOCK_WAIT_SECONDS", "600"))
    except ValueError:
        return 600.0


@contextmanager
def etl_lock(wait_seconds: float | None = None) -> Iterator[None]:
    """Hold the global ETL advisory lock, waiting up to ``wait_seconds``.

    Re-entrant within a process: nested use (a tracked job that calls another
    tracked job) is a no-op instead of a deadlock.
    """
    if os.getenv("ETL_LOCK_HELD_BY_PARENT") == "1":
        # The Express API already holds the lock for this child process.
        yield
        return
    if _held.get("depth"):
        _held["depth"] += 1
        try:
            yield
        finally:
            _held["depth"] -= 1
        return
    deadline = time.monotonic() + (_wait_seconds() if wait_seconds is None else wait_seconds)
    with engine.connect() as connection:
        while True:
            if connection.execute(text("SELECT pg_try_advisory_lock(:id)"), {"id": LOCK_ID}).scalar():
                break
            if time.monotonic() >= deadline:
                raise RuntimeError("Another ETL run is already active on this database (advisory lock held)")
            time.sleep(5)
        _held["depth"] = 1
        try:
            yield
        finally:
            _held["depth"] = 0
            connection.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": LOCK_ID})
            connection.commit()


_held: dict[str, int] = {}


def _count(result: Any, *keys: str) -> int:
    if isinstance(result, dict):
        for key in keys:
            value = result.get(key)
            if isinstance(value, int):
                return value
    return 0


def close_stale_runs(max_age_hours: float | None = None) -> int:
    """Mark abandoned ``In Progress`` rows as Failed and return how many closed.

    A process killed mid-run (reboot, CI timeout, container restart) leaves its
    row open, so the dashboard reports a run that can never finish. Only call
    this while holding ``etl_lock``: then no live job can be closed by mistake.
    """
    try:
        hours = float(os.getenv("ETL_STALE_RUN_HOURS", "12"))
    except ValueError:
        hours = 12.0
    if max_age_hours is not None:
        hours = max_age_hours
    with SessionLocal() as session:
        rows = session.execute(
            text("""
                UPDATE etl_runs
                   SET status = 'Failed',
                       finished_at = now(),
                       error = COALESCE(error, :message)
                 WHERE status = 'In Progress'
                   AND COALESCE(started_at, now()) < now() - make_interval(secs => :age)
             RETURNING id
            """),
            {"message": f"Interrupted: no finish recorded within {hours:g} hours; closed by a later run",
             "age": hours * 3600},
        ).all()
        session.commit()
        return len(rows)


def tracked_run(job_name: str, job: Callable[[], Any]) -> Any:
    """Run ``job`` under the ETL lock and persist an ``etl_runs`` row for it.

    ``job_name`` is stored in the run's error/summary text; the run has no
    source because bulk jobs span many sources. A job that raises is recorded
    as Failed and the exception is re-raised.
    """
    with etl_lock():
        close_stale_runs()
        with SessionLocal() as session:
            run = EtlRun(source_id=None, status="In Progress")
            session.add(run)
            session.commit()
            run_id = run.id
        try:
            result = job()
        except Exception as exc:
            _finish(run_id, "Failed", error=f"{job_name}: {type(exc).__name__}: {str(exc)[:900]}")
            raise
        _finish(run_id, "Succeeded", result=result, summary=job_name)
        return result


def _finish(run_id: int, status: str, *, error: str | None = None, result: Any = None,
            summary: str | None = None) -> None:
    with SessionLocal() as session:
        run = session.get(EtlRun, run_id)
        if run is None:
            return
        run.status = status
        run.finished_at = datetime.now(timezone.utc)
        run.records_loaded = _count(result, "holding_rows_inserted", "funds_updated", "navs_loaded",
                                    "rows_inserted", "records_loaded", "inception_filled", "navs_stored")
        run.records_extracted = _count(result, "holding_rows_read", "filings_imported", "records_extracted")
        if error:
            run.error = error
        elif summary:
            run.error = None
            # Keep a short machine-readable note of what ran, for audit.
            try:
                run.error = None if result is None else f"[{summary}] " + json.dumps(result, default=str)[:900]
            except (TypeError, ValueError):
                run.error = f"[{summary}]"
        session.commit()
