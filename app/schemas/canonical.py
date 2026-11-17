import re
from datetime import date
from decimal import Decimal
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator

def isin_check_digit_ok(isin: str) -> bool:
    """Validate an ISIN's Luhn check digit (letters expand to two digits)."""
    digits = "".join(str(int(ch, 36)) for ch in isin)
    total = 0
    for index, ch in enumerate(reversed(digits)):
        n = int(ch)
        if index % 2 == 1:
            n *= 2
            n = n - 9 if n > 9 else n
        total += n
    return total % 10 == 0


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

    @field_validator("isin")
    @classmethod
    def _validate_isin(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().upper()
        if not value:
            return None
        if not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", value):
            raise ValueError(f"Invalid ISIN: {value!r}")
        return value


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
