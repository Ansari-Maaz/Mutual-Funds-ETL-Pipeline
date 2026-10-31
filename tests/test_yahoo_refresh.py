import csv
import importlib.util
from pathlib import Path

script_path = Path(__file__).resolve().parents[1] / "scripts" / "refresh_us_yahoo_batch_navs.py"
spec = importlib.util.spec_from_file_location("refresh_us_yahoo_batch_navs", script_path)
refresh_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(refresh_module)
load_existing_rows = refresh_module.load_existing_rows
write_rows = refresh_module.write_rows


def test_yahoo_refresh_loader_preserves_existing_rows(tmp_path):
    snapshot = tmp_path / "yahoo.csv"
    with snapshot.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["ticker", "valuation_date", "nav", "source_url"])
        writer.writeheader()
        writer.writerow({"ticker": "AAA", "valuation_date": "2026-10-30", "nav": "12.5", "source_url": "https://example.test/aaa"})
        writer.writerow({"ticker": "BBB", "valuation_date": "2026-10-30", "nav": "20", "source_url": "https://example.test/bbb"})

    rows = load_existing_rows(snapshot)

    assert set(rows) == {"AAA", "BBB"}
    assert rows["AAA"]["nav"] == "12.5"


def test_yahoo_refresh_loader_accepts_missing_snapshot(tmp_path):
    assert load_existing_rows(tmp_path / "missing.csv") == {}


def test_yahoo_refresh_writes_merged_rows_as_a_complete_snapshot(tmp_path):
    snapshot = tmp_path / "yahoo.csv"
    rows = {
        "AAA": {"ticker": "AAA", "valuation_date": "2026-10-30", "nav": "12.5", "source_url": "https://example.test/aaa"},
        "BBB": {"ticker": "BBB", "valuation_date": "2026-10-31", "nav": "21", "source_url": "https://example.test/bbb"},
    }

    write_rows(snapshot, rows)

    assert load_existing_rows(snapshot) == rows
    assert not snapshot.with_suffix(".csv.tmp").exists()
