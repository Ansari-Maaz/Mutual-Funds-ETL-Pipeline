from app.schemas.canonical import CanonicalFund, CanonicalNav

def fund_from_source(source_id: str, record: dict) -> CanonicalFund:
    """Validate a provider-mapped record without guessing its native fields."""
    return CanonicalFund.model_validate({"source_id": source_id, **record})

def nav_from_source(source_id: str, record: dict) -> CanonicalNav:
    return CanonicalNav.model_validate({"source_id": source_id, **record})
