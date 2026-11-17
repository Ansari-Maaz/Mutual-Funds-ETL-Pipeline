from datetime import date
from decimal import Decimal

import pytest

from app.holdings.sec_nport_bulk import latest_quarter
from app.holdings.us_issuer_nav import (
    _decimal,
    _graniteshares_history_url,
    _graniteshares_rows,
)


GRANITESHARES_PAGE = b"""
<script>
  var PRODUCT_ID = 1086;
  var NAV_HISTORY_URL = "https://example.test/api/ProductNavHistory/invoke/" + PRODUCT_ID +
    "?api-version=2022-05-01&sp=%2Ftriggers%2Frun&sv=1.0&sig=abc";
</script>
"""

GRANITESHARES_HISTORY = b"""[{"Price": 24.992049, "PriceDate": "2022-08-08", "AUM": 0.0},
 {"Price": 25.5, "PriceDate": "2026-11-11", "AUM": 17473853.59},
 {"Price": null, "PriceDate": "2026-11-12", "AUM": 1},
 {"Price": 25.75, "PriceDate": "2026-11-12", "AUM": 17500000.0}]"""


def test_graniteshares_history_url_resolves_signed_product_endpoint():
    url = _graniteshares_history_url(GRANITESHARES_PAGE, ticker="AAPB")
    assert url == (
        "https://example.test/api/ProductNavHistory/invoke/1086"
        "?api-version=2022-05-01&sp=%2Ftriggers%2Frun&sv=1.0&sig=abc"
    )


def test_graniteshares_history_url_rejects_missing_endpoint():
    with pytest.raises(ValueError):
        _graniteshares_history_url(b"<html>no endpoint</html>", ticker="AAPB")


def test_graniteshares_rows_skips_invalid_and_limits_window():
    rows = _graniteshares_rows(GRANITESHARES_HISTORY, history_days=2)
    assert [row["valuation_date"] for row in rows] == [date(2026, 11, 11), date(2026, 11, 12)]
    assert rows[1]["nav"] == Decimal("25.75")
    assert rows[1]["net_assets"] == Decimal("17500000.0")


def test_us_issuer_decimal_normalizes_formatted_values():
    assert _decimal("$1,234.50") == Decimal("1234.50")
    assert _decimal("N/A") is None
    assert _decimal("0") is None


def test_latest_quarter_uses_publication_lag():
    assert latest_quarter(date(2026, 11, 15)) == "2026q3"
    assert latest_quarter(date(2026, 1, 20)) == "2025q4"
