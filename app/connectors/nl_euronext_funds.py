"""Public Euronext Amsterdam fund-list NAV/last-price snapshot."""
from pathlib import Path

from app.connectors.euronext_base import EuronextSnapshotConnector

ROOT = Path(__file__).resolve().parents[2]


class NlEuronextFundsConnector(EuronextSnapshotConnector):
    source_id = "nl_euronext_fund_navs"
    country_code = "NL"
    organization = "Euronext Amsterdam"
    source_name = "Public Amsterdam fund list and NAV/last price"
    endpoint_url = "https://live.euronext.com/nl/products/funds/list"
    raw_path = ROOT / "data/raw/netherlands/euronext_amsterdam_funds.csv"
    id_prefix = "NL-EURONEXT"
