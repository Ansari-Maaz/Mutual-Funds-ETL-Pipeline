"""Tests for the SEC N-CEN bulk enrichment parser."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.enrichment import sec_ncen_bulk as ncen


def test_sec_date_formats():
    assert ncen._sec_date("31-MAY-2026") == date(2026, 5, 31)
    assert ncen._sec_date("2026-05-31") == date(2026, 5, 31)
    assert ncen._sec_date("05/31/2026") == date(2026, 5, 31)
    assert ncen._sec_date("") is None


def test_decimal_cleaning():
    assert ncen._decimal(" 1,234.50 ") == Decimal("1234.50")
    assert ncen._decimal("N/A") is None
    assert ncen._decimal("") is None


def _row(**overrides):
    row = {
        "MANAGEMENT_FEE": "0.0400", "NET_OPERATING_EXPENSES": "0.0410",
        "MONTHLY_AVG_NET_ASSETS": "1234567.89", "DAILY_AVG_NET_ASSETS": "",
        "NAV_PER_SHARE": "12.34", "MARKET_PRICE_PER_SHARE": "",
        "RETURN_AFTR_FEES_AND_EXPENSES": "-0.0010",
        "STDV_AFTR_FEES_AND_EXPENSES": "0.0020",
        "IS_ETF": "N", "IS_INDEX": "Y", "IS_MONEY_MARKET": "N",
    }
    row.update(overrides)
    return row


def _snapshots(row, **overrides):
    return list(ncen._snapshots(
        "0001-26-000001", row, adviser=overrides.get("adviser", {}),
        administrator=overrides.get("administrator"), custodian=None, transfer_agent=None,
        pricing_service=None, accountant=None, underwriter=None,
        report_date=date(2026, 5, 31), source_url="https://example.test/filing"))


def test_snapshots_are_labelled_as_percent_of_net_assets():
    snapshots = _snapshots(_row(), adviser={"name": "Adviser LLC", "start_date": date(2010, 1, 1)},
                           administrator="Admin LLC")
    payloads = {}
    for dataset, payload in snapshots:
        payloads.setdefault(dataset, []).append(payload)
    fees = {item["measure"]: item for item in payloads["expense_ratio_history"]}
    assert fees["advisory_fee"]["unit"] == "percent"
    assert fees["net_operating_expenses"]["reported_value"] == "0.0410"
    assert payloads["aum_history"][0]["basis"] == "monthly_average_net_assets"
    assert payloads["nav_snapshot"][0]["nav_per_share"] == "12.34"
    assert payloads["classification"][0]["index_fund"] is True
    assert payloads["classification"][0]["exchange_traded_fund"] is False
    assert payloads["service_providers"][0]["adviser"]["name"] == "Adviser LLC"
    assert payloads["service_providers"][0]["administrator"] == "Admin LLC"
    # Index tracking figures must not be presented as absolute fund returns.
    assert payloads["performance"][0]["metric"] == "index_tracking_difference_after_fees"


def test_snapshots_skip_absent_values():
    snapshots = _snapshots(_row(MANAGEMENT_FEE="", NET_OPERATING_EXPENSES="",
                                MONTHLY_AVG_NET_ASSETS="", NAV_PER_SHARE="",
                                MARKET_PRICE_PER_SHARE="",
                                RETURN_AFTR_FEES_AND_EXPENSES="",
                                STDV_AFTR_FEES_AND_EXPENSES="",
                                IS_ETF="", IS_INDEX="", IS_MONEY_MARKET=""))
    assert snapshots == []


def test_advisers_skip_sub_and_terminated_roles(tmp_path):
    (tmp_path / "ADVISER.tsv").write_text(
        "FUND_ID\tSOURCE\tADVISER_TYPE\tADVISER_NAME\tFILE_NUM\tCRD_NUM\tADVISER_LEI\tSTATE\tCOUNTRY\tIS_AFFILIATED\tIS_ADVISOR_HIRED\tADVISOR_START_DATE\tADVISOR_TERMINATED_DATE\n"
        "a1\tPart C\tSubadvisor\tSub Co\t\t\t\t\t\t\t\t\t\n"
        "a1\tPart C\tAdvisor\tPrimary Co\t801-1\t1\tLEI1\tUS-MA\tUS\t\t\t01-JAN-2010\t\n"
        "a2\tPart C\tTerminated Advisor\tOld Co\t\t\t\t\t\t\t\t\t\n",
        encoding="utf-8")
    advisers = ncen._advisers(tmp_path)
    assert advisers["a1"]["name"] == "Primary Co"
    assert advisers["a1"]["start_date"] == date(2010, 1, 1)
    assert "a2" not in advisers


def test_class_tickers_skip_placeholders_and_invalid_symbols(tmp_path):
    (tmp_path / "SHARES_OUTSTANDING.tsv").write_text(
        "FUND_ID\tACCESSION_NUMBER\tCLASS_ID\tCLASS_NAME\tTICKER\tSHARES_OUTSTANDING\n"
        "a1\tacc\tC000000001\tClass A\tABCDX\t100\n"
        "a1\tacc\tC000000002\tClass C\tN/A\t100\n"
        "a1\tacc\tC000000003\tClass I\tnone\t100\n"
        "a1\tacc\tC000000004\tClass R\tabcdefghijklmnop\t100\n",
        encoding="utf-8")
    tickers = ncen._class_tickers(tmp_path)
    assert tickers == {"C000000001": ("ABCDX", "Class A")}
