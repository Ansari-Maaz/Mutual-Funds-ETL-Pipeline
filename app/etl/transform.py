import logging
import re
from app.schemas.canonical import CanonicalFund, CanonicalNav, isin_check_digit_ok
from app.country_currency import currency_for_domicile

def fund_from_source(source_id: str, record: dict) -> CanonicalFund:
    """Validate a provider-mapped record without guessing its native fields."""
    values = dict(record)
    values["profile_data"] = values.pop("_profile_data", values.get("profile_data"))
    values["profile_as_of_date"] = values.pop("_profile_as_of_date", values.get("profile_as_of_date"))
    values["profile_source_url"] = values.pop("_profile_source_url", values.get("profile_source_url"))
    if values.get("currency"):
        values.setdefault("currency_basis", "source_reported")
    else:
        fallback = currency_for_domicile(values.get("domicile_country"))
        if fallback:
            values["currency"] = fallback
            values["currency_basis"] = "domicile_default"
    isin = values.get("isin")
    if isin is not None:
        isin = str(isin).strip().upper() or None
        if isin and not (re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", isin) and isin_check_digit_ok(isin)):
            # A bad identifier must not reject an otherwise valid fund; drop it and say so.
            logging.getLogger(__name__).warning("Dropping invalid ISIN %r for %s/%s", isin, source_id, values.get("source_fund_id"))
            isin = None
        values["isin"] = isin
    return CanonicalFund.model_validate({"source_id": source_id, **values})

def nav_from_source(source_id: str, record: dict) -> CanonicalNav:
    return CanonicalNav.model_validate({"source_id": source_id, **record})
