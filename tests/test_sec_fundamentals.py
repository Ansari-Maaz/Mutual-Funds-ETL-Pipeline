from datetime import date
from decimal import Decimal

from app.holdings.sec_fundamentals import annual_eps


def test_annual_eps_uses_latest_annual_10k_duration():
    payload = {
        "units": {
            "USD/shares": [
                {"start": "2024-09-29", "end": "2025-09-27", "val": 6.11,
                 "form": "10-K", "filed": "2025-10-31", "fy": 2025},
                {"start": "2025-09-28", "end": "2026-09-26", "val": 8.98,
                 "form": "10-K", "filed": "2026-11-03", "fy": 2026},
                # Quarterly facts and short durations are never accepted.
                {"start": "2026-06-29", "end": "2026-09-26", "val": 1.85,
                 "form": "10-Q", "filed": "2026-10-31", "fy": 2026},
            ]
        }
    }
    result = annual_eps(payload)
    assert result is not None
    assert result["eps"] == Decimal("8.98")
    assert result["period_end"] == date(2026, 9, 26)
    assert result["filed"] == date(2026, 11, 3)
    assert result["fiscal_year"] == 2026


def test_annual_eps_rejects_missing_or_non_annual_facts():
    assert annual_eps(None) is None
    assert annual_eps({"units": {}}) is None
    assert annual_eps({"units": {"USD/shares": [
        {"start": "2026-01-01", "end": "2026-03-31", "val": 1.0,
         "form": "10-Q", "filed": "2026-05-01"}
    ]}}) is None
