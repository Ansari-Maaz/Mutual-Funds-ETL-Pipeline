from datetime import date
from decimal import Decimal
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

class CanonicalFund(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str
    source_fund_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    domicile_country: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    currency_basis: str | None = None
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
    profile_data: dict[str, dict[str, Any]] | None = None
    profile_as_of_date: date | None = None
    profile_source_url: str | None = None

class CanonicalNav(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str
    source_fund_id: str
    valuation_date: date
    nav: Decimal = Field(gt=0)
    open: Decimal | None = Field(default=None, gt=0)
    high: Decimal | None = Field(default=None, gt=0)
    low: Decimal | None = Field(default=None, gt=0)
    close: Decimal | None = Field(default=None, gt=0)
    ohlc_basis: str | None = None
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    source_url: str | None = None
