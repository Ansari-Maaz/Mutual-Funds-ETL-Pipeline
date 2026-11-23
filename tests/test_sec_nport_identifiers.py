from app.holdings.sec_nport_identifiers import (
    cusip_is_plausible, sector_for_sic,
)


def test_placeholder_cusips_are_rejected():
    assert cusip_is_plausible("037833100") is True
    assert cusip_is_plausible("000000000") is False
    assert cusip_is_plausible("999999999") is False
    assert cusip_is_plausible("111111111") is False
    assert cusip_is_plausible("N/A") is False
    assert cusip_is_plausible("03783310") is False


def test_sic_codes_group_into_sectors_with_official_fallbacks():
    assert sector_for_sic("3674", "Semiconductors") == "Information Technology"
    assert sector_for_sic("2834", "Pharmaceutical preparations") == "Health Care"
    assert sector_for_sic("6022", "State commercial banks") == "Financials"
    assert sector_for_sic("6726", "Investment offices") == "Funds"
    assert sector_for_sic("6798", "Real estate investment trusts") == "Real Estate"
    assert sector_for_sic("4813", "Telephone communications") == "Communication Services"
    # Codes outside the mapped ranges keep the official SEC description.
    assert sector_for_sic("9000", "Custom classification") == "Custom classification"
    assert sector_for_sic("", "Custom description") == "Custom description"
    assert sector_for_sic(None, None) is None
