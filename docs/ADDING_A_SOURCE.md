# Adding a source

1. Add an evidence-backed record to `config/sources.yaml`, keeping verification, licensing, and integration separate.
2. Implement `BaseConnector` in `app/connectors/providers/`, retaining native IDs and provenance and stating unsupported capabilities.
3. Map provider fields to canonical schemas using Decimal and correctly parsed dates.
4. Use bounded requests and documented pagination/rate limits; never bypass access controls.
5. Register the connector, implement transactional upserts, and add parser/idempotency tests with permitted fixtures.
6. Mark Integrated only after live extraction, transform, database load, and repeat-run checks.
