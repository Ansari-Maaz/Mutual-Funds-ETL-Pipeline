"""Public Euronext Luxembourg-listed fund NAV/last-price snapshot."""
from pathlib import Path

from app.connectors.euronext_base import EuronextSnapshotConnector

ROOT = Path(__file__).resolve().parents[2]


class LuEuronextFundsConnector(EuronextSnapshotConnector):
    source_id = "lu_euronext_fund_navs"
    country_code = "LU"
    organization = "Euronext Luxembourg"
    source_name = "Public Luxembourg fund list and NAV/last price"
    endpoint_url = "https://live.euronext.com/en/products/funds/list"
    raw_path = ROOT / "data/raw/luxembourg/euronext_luxembourg_funds.csv"
    id_prefix = "LU-EURONEXT"
