from datetime import date
from decimal import Decimal
import pytest
from pydantic import ValidationError
from app.etl.transform import fund_from_source, nav_from_source

def test_fund_validation_preserves_native_id_and_iso_codes():
    fund=fund_from_source("provider",{"source_fund_id":"000012","name":"Example","domicile_country":"AU","currency":"AUD"})
    assert fund.source_fund_id=="000012"
    assert fund.currency=="AUD"

def test_invalid_country_is_rejected():
    with pytest.raises(ValidationError): fund_from_source("p",{"source_fund_id":"x","name":"Bad","domicile_country":"AUS"})

def test_nav_uses_decimal_and_date():
    nav=nav_from_source("p",{"source_fund_id":"x","valuation_date":"2025-01-02","nav":"1.234500","currency":"USD"})
    assert nav.valuation_date==date(2025,1,2)
    assert nav.nav==Decimal("1.234500")

def test_nonpositive_nav_rejected():
    with pytest.raises(ValidationError): nav_from_source("p",{"source_fund_id":"x","valuation_date":"2025-01-02","nav":"0","currency":"USD"})
