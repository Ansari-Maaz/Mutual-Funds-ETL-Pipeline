import csv
import io
import json
from decimal import Decimal

import pytest

from app.connectors import (
    ch_six_fund_explorer,
    fr_lacotebleue,
    it_borsa_nav,
    lu_allianz_daily_nav,
    lu_euronext_funds,
    nl_euronext_funds,
)
from app.schemas.canonical import CanonicalFund, CanonicalNav


def write_snapshot(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=row.keys())
        writer.writeheader()
        writer.writerow(row)
    return path


def assert_canonical(connector):
    funds = list(connector.extract_funds())
    assert len(funds) == 1
    fund = CanonicalFund.model_validate({"source_id": connector.source_id, **funds[0]})
    navs = list(connector.extract_nav_history(fund.source_fund_id))
    assert len(navs) == 1
    nav = CanonicalNav.model_validate({"source_id": connector.source_id, **navs[0]})
    assert nav.source_fund_id == fund.source_fund_id
    return fund, nav


def test_italian_borsa_snapshot_maps_fund_and_nav(tmp_path, monkeypatch):
    monkeypatch.setattr(it_borsa_nav, "RAW", write_snapshot(tmp_path / "it.csv", {
        "isin": "IT0000000001", "currency": "EUR", "valuation_date": "2026-10-23", "nav": "12.34",
    }))
    fund, nav = assert_canonical(it_borsa_nav.ItBorsaNavConnector())
    assert (fund.domicile_country, fund.isin, nav.nav) == ("IT", "IT0000000001", Decimal("12.34"))


def test_french_lacote_bleue_snapshot_preserves_provider_and_category(tmp_path, monkeypatch):
    monkeypatch.setattr(fr_lacotebleue, "RAW", write_snapshot(tmp_path / "fr.csv", {
        "isin": "FR0000000001", "name": "Example Equity Fund", "provider": "Example AM",
        "currency": "EUR", "valuation_date": "2026-10-23", "nav": "8.5",
    }))
    fund, nav = assert_canonical(fr_lacotebleue.FrLaCoteBleueConnector())
    assert (fund.domicile_country, fund.provider, fund.category, nav.currency) == ("FR", "Example AM", "Equity", "EUR")


@pytest.mark.parametrize(
    ("module", "connector_type", "country", "isin"),
    [
        (nl_euronext_funds, nl_euronext_funds.NlEuronextFundsConnector, "NL", "NL0000000001"),
        (lu_euronext_funds, lu_euronext_funds.LuEuronextFundsConnector, "LU", "LU0000000001"),
    ],
)
def test_euronext_country_snapshots_map_to_the_correct_market(tmp_path, monkeypatch, module, connector_type, country, isin):
    connector = connector_type()
    monkeypatch.setattr(connector, "raw_path", write_snapshot(tmp_path / f"{country}.csv", {
        "isin": isin, "name": "Example Global Equity Fund", "ticker": "EXM",
        "currency": "EUR", "valuation_date": "2026-10-23", "nav": "9.2",
    }))
    fund, nav = assert_canonical(connector)
    assert (fund.domicile_country, fund.isin, fund.ticker, nav.currency) == (country, isin, "EXM", "EUR")
    assert module.__name__ in {"app.connectors.nl_euronext_funds", "app.connectors.lu_euronext_funds"}


def test_allianz_sfdr_does_not_leak_into_target_audience(tmp_path, monkeypatch):
    monkeypatch.setattr(lu_allianz_daily_nav, "RAW", write_snapshot(tmp_path / "allianz.csv", {
        "isin": "LU0000000002", "name": "Example Sustainable Fund", "provider": "Allianz GI",
        "asset_class": "Equity", "sfdr_classification": "Article 8", "share_class": "A",
        "currency": "EUR", "valuation_date": "2026-10-23", "nav": "10.1",
    }))
    fund, nav = assert_canonical(lu_allianz_daily_nav.LuAllianzDailyNavConnector())
    assert fund.target_audience is None
    assert (fund.domicile_country, fund.category, nav.currency) == ("LU", "Equity", "EUR")


def test_six_connector_filters_non_swiss_rows_and_maps_published_nav(monkeypatch):
    names = [
        "FundLongName", "FundCurrency", "ISIN", "ClosingPrice", "MarketDate",
        "LegalStructureCountryCode", "AssetClassDesc", "IssuerLongNameDesc",
    ]
    rows = [
        ["Swiss Example Equity", "CHF", "CH0000000001", 102.5, "20261023", "CH", "Equity", "Example issuer"],
        ["Foreign Example Equity", "EUR", "IE0000000001", 99.0, "20261023", "IE", "Equity", "Other issuer"],
    ]
    payload = json.dumps({"colNames": names, "rowData": rows}).encode()

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    monkeypatch.setattr(ch_six_fund_explorer.urllib.request, "urlopen", lambda *_args, **_kwargs: Response(payload))
    connector = ch_six_fund_explorer.ChSixFundExplorerConnector()
    funds = list(connector.extract_funds())
    assert len(funds) == 1
    fund = CanonicalFund.model_validate({"source_id": connector.source_id, **funds[0]})
    navs = list(connector.extract_nav_history(fund.source_fund_id))
    nav = CanonicalNav.model_validate({"source_id": connector.source_id, **navs[0]})
    assert (fund.domicile_country, fund.isin, nav.valuation_date.isoformat(), nav.nav) == ("CH", "CH0000000001", "2026-10-23", Decimal("102.5"))
