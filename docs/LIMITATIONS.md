# Limitations

- Seventeen source connectors have been executed. Brazil (CVM) and Australia (GSFM) provide NAV observations; the other 15 integrations are fund-master snapshots without NAV in the imported fields.
- Current core-market source coverage includes US, GB, DE, FR, IT, CH, NL, DK, SE, CN, AU, HK market-authorized products and BR. Canada, Mexico, Japan, South Korea, Singapore, Taiwan and Russia remain without imports. Luxembourg, Ireland and South Africa are present as expansion markets; the UAE remains outstanding.
- The five Banco de España country-list imports cover open-ended non-monetary investment fund products in DE, IT, NL, DK and LU. Those registers include both UCITS and AIFs, so they are broader than a strict UCITS-only mutual-fund universe. They publish no currency or NAV.
- The Hong Kong SFC source lists funds authorized for public offering in Hong Kong, including overseas-domiciled products. Domicile is therefore left null; this dataset represents market availability, not a Hong Kong-domiciled universe.
- Brazil's CVM connector ingests a selected month or an explicitly requested range of up to 12 monthly archives. An all-history backfill is not performed by default.
- Brazil's official CVM CDA archive is the structured portfolio-holdings source; it can omit confidential positions and its CSV field layout varies across archive groups.
- France's AMF GECO registry provides fund/share-class identities and documents, but no central structured portfolio-holdings feed. French holdings require issuer-specific report adapters and are not represented as complete national coverage.
- GSFM's combined price export has no currency column. The connector loads only the record explicitly labelled `(AUD)`, so Australian NAV coverage is one fund and one observation.
- CSRC, ASISA and FINMA snapshots do not provide NAV or currency in the fields used here. The project preserves null values and does not manufacture these fields.
- Taiwan's government catalog documents daily NAV and currency, but the publisher CSV host timed out during repeated attempts. No Taiwan rows were imported.
- All raw snapshots are local under `data/raw/` and ignored by Git. Source-specific manifests in `reports/` record URLs and SHA-256 hashes.
- Commercial reuse rights have not been reviewed for all providers. Check each provider's terms before redistribution or commercial use.
- PostgreSQL 16 runs in the project's persistent Docker container on port 5433.
