from app.etl import orchestrator


class FakeSession:
    def __init__(self, run_state=None, history=None):
        self.run_state = run_state if run_state is not None else {}
        self.history = history if history is not None else []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def execute(self, _statement):
        return None

    def add(self, run):
        run.id = 41
        self.run_state["run"] = run

    def commit(self):
        run = self.run_state["run"]
        self.history.append((run.status, run.source_id))

    def rollback(self):
        self.history.append(("rollback", self.run_state["run"].source_id))

    def get(self, model, run_id):
        assert run_id == 41
        return self.run_state["run"]


class FailingConnector:
    def get_source_metadata(self):
        return {
            "country_code": "US",
            "organization": "Example Registry",
            "source_name": "Example source",
        }

    def check_availability(self):
        raise RuntimeError("upstream is unavailable")


def test_failure_for_unregistered_source_is_persisted_after_source_and_run_commit(monkeypatch):
    history = []
    run_state = {}
    initial_session = FakeSession(run_state=run_state, history=history)
    failure_session = FakeSession(run_state=run_state, history=history)
    sessions = iter([initial_session, failure_session])
    monkeypatch.setattr(orchestrator, "SessionLocal", lambda: next(sessions))

    result = orchestrator.run_connector("previously_unregistered_source", FailingConnector)

    assert result["status"] == "Failed"
    assert result["error"] == "RuntimeError: upstream is unavailable"
    assert history == [
        ("In Progress", "previously_unregistered_source"),
        ("rollback", "previously_unregistered_source"),
        ("Failed", "previously_unregistered_source"),
    ]
    assert run_state["run"].status == "Failed"
    assert run_state["run"].finished_at is not None


class RejectingConnector:
    source_id = "rejecting"

    def get_source_metadata(self):
        return {"country_code": "US", "organization": "O", "source_name": "S"}

    def check_availability(self):
        return {"available": True}

    def extract_funds(self, start_date=None, end_date=None):
        return [{"source_fund_id": "1", "name": "Fund", "_navs": [
            {"valuation_date": "2026-01-01", "nav": "0", "currency": "USD"},
            {"valuation_date": "2026-01-02", "nav": "-1", "currency": "USD"}]}]


def test_run_fails_and_persists_reject_count_above_threshold(monkeypatch):
    run_state = {}
    sessions = iter([FakeSession(run_state=run_state), FakeSession(run_state=run_state)])
    monkeypatch.setattr(orchestrator, "SessionLocal", lambda: next(sessions))
    monkeypatch.setattr(orchestrator, "upsert_funds_batch", lambda *a, **k: {"1": 7})
    monkeypatch.setattr(orchestrator, "upsert_navs_batch", lambda *a, **k: None)
    result = orchestrator.run_connector("rejecting", RejectingConnector)
    assert result["status"] == "Failed"
    assert "Reject rate" in result["error"]
    assert run_state["run"].records_rejected == 2
