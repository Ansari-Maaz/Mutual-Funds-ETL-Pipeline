# Mexico mutual-fund import

## Source research

This import uses the Bolsa Mexicana de Valores (BMV) public fund pages and their public JSON services:

- Fund/operator and series listing: `https://www.bmv.com.mx/es/Grupo_BMV/BmvJsonOperadora?pagina=consulta...`
- Per-operator fund listing: `https://www.bmv.com.mx/es/Grupo_BMV/BmvJsonOperadora?pagina=fondos...`
- Per-fund latest price table: `https://www.bmv.com.mx/es/Grupo_BMV/BmvJsonFondo?pagina=tabla&idFondo=...`
- Human-readable BMV fund catalogue: `https://www.bmv.com.mx/es/Grupo_BMV/informacion-de-fondos`

The BMV catalogue describes its “Precios Fondos de Inversión” product as daily prices for all listed investment funds. The public JSON response exposes fund keys, share series, operator, classification through names, and latest price values.

## Imported result

| Metric | Count |
|---|---:|
| Fund/share-class identities extracted | 5,151 |
| Fund/share-class identities loaded | 5,151 |
| Latest NAV/price observations loaded | 3,483 |
| Latest valuation date | 2026-10-23 |
| First valuation date in this snapshot | 2026-09-28 |
| Rejected records | 0 |

Raw files:

- `data/raw/mexico/bmv_mexico_funds.csv`
- `data/raw/mexico/bmv_mexico_navs.csv`

ETL source ID: `bmv_mexico_funds`.

## Field limitations

- BMV's public price JSON does not publish a currency field; the importer records `MXN`, the local market currency, and documents this normalization.
- ISIN is not present in the public listing response, so it is null rather than inferred.
- Categories are broad labels derived from the legal fund name (debt/fixed income, equity, or mixed/other). They are not a replacement for CNBV's detailed regulatory classification.
- This is the public BMV listed-fund universe. It should not be described as every Mexico-authorized fund if an unlisted CNBV fund is outside BMV's public catalogue.

## Re-running

The raw snapshot is loaded by `app/connectors/bmv_mexico.py` and can be reloaded with:

```bash
./.venv/bin/python -m app.cli run --source bmv_mexico_funds
```

