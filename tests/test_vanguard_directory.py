import pytest

from scripts.sync_vanguard_directory import parse_directory
from scripts.audit_us_fund_completeness import MASTER_FIELDS, _field_value, _status


def test_vanguard_directory_keeps_provider_records_and_checks_identity():
    row = {"portId": "0540", "ticker": "VFIAX", "identifier": "VFIAX",
           "longName": "Vanguard 500 Index Fund Admiral Shares"}
    assert parse_directory({"0540": row}) == [row]


def test_vanguard_directory_rejects_duplicate_or_conflicting_tickers():
    with pytest.raises(ValueError, match="Duplicate ticker"):
        parse_directory({"1": {"portId": "1", "ticker": "VFIAX"},
                         "2": {"portId": "2", "ticker": "vfiax"}})
    with pytest.raises(ValueError, match="identifier differs"):
        parse_directory({"1": {"portId": "1", "ticker": "VFIAX", "identifier": "VFIAX-A"}})


def test_vanguard_directory_rejects_port_id_mismatch():
    with pytest.raises(ValueError, match="port ID mismatch"):
        parse_directory({"1": {"portId": "2", "ticker": "VFIAX"}})


def test_master_completeness_checks_share_class_and_source_documents_individually():
    row = {
        "name": "Fund Class A",
        "profile_summary": {
            "shareClass": "Class A",
            "factsheet_url": "https://fund.example/factsheet.pdf",
            "distribution_schedule": "Quarterly",
        },
    }
    assert "share_class" in MASTER_FIELDS
    assert _field_value(row, "share_class") == "Class A"
    assert _field_value(row, "factsheet_url") == "https://fund.example/factsheet.pdf"
    assert _field_value(row, "distribution_option") is None
    # Distribution frequency is not a distribution/reinvestment option.
    assert _status({**row, "nav_rows": 0, "holding_rows": 0}, "scheme_master") == "partially_available"


def test_nmfp_history_is_reported_as_partial_source_history():
    assert _status({"profile_nav_history": 2}, "money_market_nav_history") == "partially_available"
    assert _status({"profile_nav_history": 0}, "money_market_nav_history") == "requires_verification"
