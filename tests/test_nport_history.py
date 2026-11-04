import json
from collections import defaultdict
from datetime import date

from app.holdings.sec_nport import _keep_latest_report_period, _recent_filings


def test_latest_amendment_wins_without_discarding_older_report_dates():
    found = defaultdict(dict)
    original = {"series_id": "S000000001", "report_date": date(2026, 6, 30),
                "accession_number": "0001-26-000001", "holdings": ["original"]}
    amendment = {"series_id": "S000000001", "report_date": date(2026, 6, 30),
                 "accession_number": "0001-26-000002", "holdings": ["amended"]}
    prior_period = {"series_id": "S000000001", "report_date": date(2026, 3, 31),
                    "accession_number": "0001-26-000003", "holdings": ["prior"]}

    _keep_latest_report_period(found, amendment, "2026-07-29")
    _keep_latest_report_period(found, original, "2026-07-02")
    _keep_latest_report_period(found, prior_period, "2026-04-29")

    assert found["S000000001"][date(2026, 6, 30)][1]["holdings"] == ["amended"]
    assert found["S000000001"][date(2026, 3, 31)][1]["holdings"] == ["prior"]


def test_recent_filings_respects_lookback_and_keeps_amended_nport(monkeypatch):
    payload = {
        "filings": {"recent": {
            "form": ["NPORT-P", "NPORT-P/A", "N-CSR"],
            "filingDate": ["2026-10-01", "2026-10-20", "2026-10-21"],
            "primaryDocument": ["one.xml", "two.xml", "three.xml"],
            "accessionNumber": ["0001-26-000001", "0001-26-000002", "0001-26-000003"],
            "reportDate": ["2026-09-30", "2026-09-30", "2026-09-30"],
        }}
    }
    monkeypatch.setattr("app.holdings.sec_nport._request", lambda _url: json.dumps(payload).encode())

    results = _recent_filings("0000000001", max_age_days=60)

    assert [row["accession"] for row in results] == ["0001-26-000002", "0001-26-000001"]
