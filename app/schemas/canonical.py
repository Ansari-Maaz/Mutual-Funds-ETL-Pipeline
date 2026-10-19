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

class CanonicalNav(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str
    source_fund_id: str
    valuation_date: date
    nav: Decimal = Field(gt=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
