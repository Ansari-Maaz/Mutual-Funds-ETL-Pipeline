# Limitations

- The dated local evidence snapshot (2026-10-28) records 51 registered source rows and 30 sources marked integrated. Country-level record counts are in the [coverage table](../README.md#country-and-market-coverage). Do not treat this local snapshot as the current production database.
- That snapshot has fund records in 18 of 24 target markets. Japan, South Korea, Singapore, Taiwan, Russia, and the UAE have no imported fund rows in the cited snapshot. Luxembourg, Ireland, and South Africa are expansion markets; Spain is additional to target scope.
- The five Banco de España country-list imports cover open-ended non-monetary investment fund products in DE, IT, NL, DK and LU. Those registers include both UCITS and AIFs, so they are broader than a strict UCITS-only mutual-fund universe. They publish no currency or NAV.
- The Hong Kong SFC source lists funds authorized for public offering in Hong Kong, including overseas-domiciled products. Domicile is therefore left null; this dataset represents market availability, not a Hong Kong-domiciled universe.
- Brazil's CVM connector ingests a selected month or an explicitly requested range of up to 12 monthly archives. An all-history backfill is not performed by default.
- Brazil's official CVM CDA archive is the structured portfolio-holdings source; it can omit confidential positions and its CSV field layout varies across archive groups.
- France's AMF GECO registry provides fund/share-class identities and documents, but no central structured portfolio-holdings feed. French holdings require issuer-specific report adapters and are not represented as complete national coverage.
- GSFM's combined price export has no currency column. The connector loads only rows explicitly labelled `(AUD)`; reported Australian fund and NAV coverage is in the dated coverage snapshot.
- CSRC, ASISA and FINMA snapshots do not provide NAV or currency in the fields used here. The project preserves null values and does not manufacture these fields.
- Taiwan's government catalog documents daily NAV and currency, but the publisher CSV host timed out during repeated attempts. No Taiwan rows were imported.
- Raw snapshots are intentionally excluded from Git. Use [RAW_SNAPSHOTS.md](RAW_SNAPSHOTS.md) to retrieve file-based data and write source URL, retrieval time, and SHA-256 provenance manifests.
- Commercial reuse rights have not been reviewed for all providers. Check each provider's terms before redistribution or commercial use.
- PostgreSQL 16 runs in the project's persistent Docker container on port 5433.
