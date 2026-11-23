import types
import sys

import pytest

from app import cli


def test_run_all_allows_partial_failures(monkeypatch, tmp_path):
    monkeypatch.setattr("sys.argv", ["mfetl", "run", "--all"])
    monkeypatch.setattr(cli, "REPORTS", tmp_path / "reports")
    monkeypatch.setattr(cli, "all_connectors", lambda: {"ok_source": object, "bad_source": object})
    fake_orchestrator = types.ModuleType("app.etl.orchestrator")
    fake_orchestrator.run_many = lambda *_args, **_kwargs: [
        {"source_id": "ok_source", "status": "Succeeded", "records_extracted": 1, "records_loaded": 1, "navs_loaded": 1},
        {"source_id": "bad_source", "status": "Failed", "error": "HTTPError: HTTP Error 404: Not Found"},
    ]
    monkeypatch.setitem(sys.modules, "app.etl.orchestrator", fake_orchestrator)
    monkeypatch.setattr(cli, "export_database_samples", lambda: {"funds": 1, "nav_observations": 1, "by_source": {}})
    monkeypatch.setattr(cli, "write_latest_run_report", lambda *_args, **_kwargs: None)

    cli.main()


def test_run_source_still_fails_when_connector_fails(monkeypatch, tmp_path):
    monkeypatch.setattr("sys.argv", ["mfetl", "run", "--source", "bad_source"])
    monkeypatch.setattr(cli, "REPORTS", tmp_path / "reports")
    monkeypatch.setattr(cli, "all_connectors", lambda: {"bad_source": object})
    fake_orchestrator = types.ModuleType("app.etl.orchestrator")
    fake_orchestrator.run_many = lambda *_args, **_kwargs: [
        {"source_id": "bad_source", "status": "Failed", "error": "HTTPError: HTTP Error 404: Not Found"},
    ]
    monkeypatch.setitem(sys.modules, "app.etl.orchestrator", fake_orchestrator)

    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1
