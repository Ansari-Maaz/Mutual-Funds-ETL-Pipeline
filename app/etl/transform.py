from app.schemas.canonical import CanonicalFund, CanonicalNav
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
    return CanonicalFund.model_validate({"source_id": source_id, **values})

def nav_from_source(source_id: str, record: dict) -> CanonicalNav:
    return CanonicalNav.model_validate({"source_id": source_id, **record})
