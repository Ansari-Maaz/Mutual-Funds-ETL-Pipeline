"""ISO 4217 domicile-level fallback codes for records lacking class currency.

These are defaults inferred from fund domicile, not a claim about the currency
of a particular share class. Prefer a currency explicitly published by a source.
"""

DOMICILE_CURRENCY = {
    "CH": "CHF",  # Swiss franc
    "CN": "CNY",  # Renminbi (yuan)
    "DK": "DKK",  # Danish krone
    "GB": "GBP",  # Pound sterling
    "SE": "SEK",  # Swedish krona
    "ZA": "ZAR",  # South African rand
    "DE": "EUR",
    "ES": "EUR",
    "FR": "EUR",
    "IE": "EUR",
    "IT": "EUR",
    "LU": "EUR",
    "NL": "EUR",
}


def currency_for_domicile(country_code: str | None) -> str | None:
    """Return a country-level ISO code, or None when no safe default is mapped."""
    if not country_code:
        return None
    return DOMICILE_CURRENCY.get(country_code.upper())
