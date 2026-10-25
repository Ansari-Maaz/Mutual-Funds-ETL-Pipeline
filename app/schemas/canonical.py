from datetime import date
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field

class CanonicalFund(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str
    source_fund_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    domicile_country: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    isin: str | None = None
    legal_name: str | None = None
    provider: str | None = None
    category: str | None = None
    fund_type: str | None = None
    inception_date: date | None = None
    status: str | None = None
    official_url: str | None = None
    ticker: str | None = None
    manager: str | None = None
    administrator: str | None = None
    net_assets: Decimal | None = None
    net_assets_date: date | None = None
    target_audience: str | None = None

class CanonicalNav(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str
    source_fund_id: str
    valuation_date: date
    nav: Decimal = Field(gt=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
