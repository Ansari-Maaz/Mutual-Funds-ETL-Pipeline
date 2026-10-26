from app.connectors.base import BaseConnector

_CONNECTORS: dict[str, type[BaseConnector]] = {}

def register(source_id: str, connector: type[BaseConnector]) -> None:
    if source_id in _CONNECTORS:
        raise ValueError(f"Connector already registered: {source_id}")
    _CONNECTORS[source_id] = connector

def get(source_id: str) -> type[BaseConnector]:
    return _CONNECTORS[source_id]

def all_connectors() -> dict[str, type[BaseConnector]]:
    return dict(_CONNECTORS)

# Import built-in providers so CLI runs discover their connector classes.
from app.connectors.cvm import CvmConnector  # noqa: E402
from app.connectors.csrc import CsrcConnector  # noqa: E402
from app.connectors.gsfm import GsfmConnector  # noqa: E402
from app.connectors.asisa import AsisaConnector  # noqa: E402
from app.connectors.finma import FinmaConnector  # noqa: E402
from app.connectors.fca import FcaFundsConnector  # noqa: E402
from app.connectors.sec import SecFundsConnector  # noqa: E402
from app.connectors.cnmv import CnmvFundsConnector  # noqa: E402
from app.connectors.fi_sweden import FiSwedenConnector  # noqa: E402
from app.connectors.central_bank_ireland import CbiUcitsConnector  # noqa: E402
from app.connectors.amf_geco import AmfGecoConnector  # noqa: E402
from app.connectors.denmark_bde_funds import DenmarkBdeFundsConnector  # noqa: E402
from app.connectors.bde_european_funds import (  # noqa: E402
    BdeGermanyConnector, BdeItalyConnector, BdeNetherlandsConnector, BdeLuxembourgConnector,
)
from app.connectors.hk_sfc_funds import HkSfcFundsConnector  # noqa: E402
from app.connectors.australian_managed_funds import AustralianManagedFundsConnector  # noqa: E402
from app.connectors.us_qqqm import QqqmEtfConnector  # noqa: E402
from app.connectors.scotia_canada import ScotiaCanadaConnector  # noqa: E402
from app.connectors.bmv_mexico import BmvMexicoConnector  # noqa: E402
from app.connectors.uk_fundslibrary import UkFundsLibraryConnector  # noqa: E402
from app.connectors.uk_ft_morningstar import UkFtMorningstarConnector  # noqa: E402
from app.connectors.de_bundesanzeiger import DeBundesanzeigerConnector  # noqa: E402
from app.connectors.it_borsa_nav import ItBorsaNavConnector  # noqa: E402
from app.connectors.ch_six_fund_explorer import ChSixFundExplorerConnector  # noqa: E402

register(CvmConnector.source_id,CvmConnector)
register(CsrcConnector.source_id,CsrcConnector)
register(GsfmConnector.source_id,GsfmConnector)
register(AsisaConnector.source_id,AsisaConnector)
register(FinmaConnector.source_id,FinmaConnector)
register(FcaFundsConnector.source_id,FcaFundsConnector)
register(SecFundsConnector.source_id,SecFundsConnector)
register(CnmvFundsConnector.source_id,CnmvFundsConnector)
register(FiSwedenConnector.source_id,FiSwedenConnector)
register(CbiUcitsConnector.source_id,CbiUcitsConnector)
register(AmfGecoConnector.source_id,AmfGecoConnector)
register(DenmarkBdeFundsConnector.source_id,DenmarkBdeFundsConnector)
register(BdeGermanyConnector.source_id,BdeGermanyConnector)
register(BdeItalyConnector.source_id,BdeItalyConnector)
register(BdeNetherlandsConnector.source_id,BdeNetherlandsConnector)
register(BdeLuxembourgConnector.source_id,BdeLuxembourgConnector)
register(HkSfcFundsConnector.source_id,HkSfcFundsConnector)
register(AustralianManagedFundsConnector.source_id,AustralianManagedFundsConnector)
register(QqqmEtfConnector.source_id,QqqmEtfConnector)
register(ScotiaCanadaConnector.source_id,ScotiaCanadaConnector)
register(BmvMexicoConnector.source_id,BmvMexicoConnector)
register(UkFundsLibraryConnector.source_id,UkFundsLibraryConnector)
register(UkFtMorningstarConnector.source_id,UkFtMorningstarConnector)
register(DeBundesanzeigerConnector.source_id,DeBundesanzeigerConnector)
register(ItBorsaNavConnector.source_id,ItBorsaNavConnector)
register(ChSixFundExplorerConnector.source_id,ChSixFundExplorerConnector)
