# United Kingdom mutual-fund import

## Sources

1. **FCA authorised/approved fund register** — official FCA CSV. This is the broad UK fund master used by the existing connector.
2. **FundsLibrary public unit-price table** — public fund-price table containing fund name, SEDOL, Investment Association sector, status, price date and NAV price in pence.

The FCA register is the regulator source for the UK-authorised/approved master. FundsLibrary is used for a public NAV snapshot because the FCA register does not publish daily NAVs. The public FundsLibrary table is a platform/issuer catalogue and is not the complete UK market universe.

## Imported result

| Source | Funds | NAV observations | Latest NAV date |
|---|---:|---:|---|
| FCA authorised/approved register | 3,975 | 0 | — |
| FundsLibrary public NAV table | 33 | 33 | 2026-10-23 |

FundsLibrary NAV prices are published in pence and are converted to pounds (GBP) before loading. Investment Association sector values are retained as `category`.

Raw file: `data/raw/united_kingdom/fundslibrary_unit_prices.csv`

Connectors:

- `app/connectors/fca.py`
- `app/connectors/uk_fundslibrary.py`

Re-run:

```bash
./.venv/bin/python -m app.cli run --source fca_authorised_funds
./.venv/bin/python -m app.cli run --source uk_fundslibrary_unit_prices
```

## Coverage limitation

The FCA register provides broad fund identity coverage but no NAV. The public FundsLibrary page provides NAV and IA categories for the rows visible in that public branded catalogue, not every FCA-authorised fund. A complete all-manager UK NAV feed requires licensed FE fundinfo, Morningstar, LSEG, or direct manager feeds.

