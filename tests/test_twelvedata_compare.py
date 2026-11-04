from scripts.compare_twelvedata import _fund_directory_match


def test_fund_directory_match_uses_exact_symbol_case_insensitively():
    payload = {"result": {"count": 2, "list": [
        {"symbol": "OTHER", "name": "Other Fund"},
        {"symbol": "VFIAX", "name": "Vanguard 500 Index Fund Admiral Shares", "type": "Mutual Fund"},
    ]}}
    assert _fund_directory_match(payload, "vfiax")["name"] == "Vanguard 500 Index Fund Admiral Shares"


def test_fund_directory_match_does_not_match_partial_ticker():
    payload = {"result": {"count": 1, "list": [{"symbol": "VFIAXX"}]}}
    assert _fund_directory_match(payload, "VFIAX") is None
