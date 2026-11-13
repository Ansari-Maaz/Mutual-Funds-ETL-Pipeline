# FundFlow Report Evidence Notes

Report snapshot date: 2026-10-28 (Asia/Kolkata). Do not interpret this as evidence of current production deployment.

| Evidence | What it establishes | Status / limitation |
|---|---|---|
| `/tmp/fundflow-stats.json` local API response | 183,169 funds; 283,590 NAV rows; 24 configured countries; 51 sources; 30 integrated; latest `python-277` success timestamp | Saved endpoint snapshot; API was stopped/unavailable at final verification |
| `/tmp/fundflow-countries.json` | 25 registry country codes and country-level fund/NAV/source counts | Saved endpoint snapshot, not a live final fetch |
| `/tmp/fundflow-sources.json` | 51 source records and verification, integration, licensing, access metadata | Registry classification, not live source verification |
| Prior read-only local PostgreSQL queries | 57,135 funds with NAV; 5,433,511 holdings rows across 17,487 US funds and 19 report dates; 355 optional holding-metric rows; DB size about 2.57 GiB; ETL run history and quality counts | Direct connection could not be repeated on this report turn |
| Repository source inspection | SQLAlchemy entities, Python connectors/loader, Node API routes, frontend and workflow | Source-level verification |
| `npm run build` in `frontend/` | Production frontend bundle generated successfully | Passed 2026-10-28 |
| `npm test` in `api/` | API tests attempted | 2 passed, 15 blocked by sandbox localhost bind `EPERM`; not a clean pass |
| `curl localhost:3001` and direct DB connection | Final live service/DB reachability | Unavailable during report generation |
| Render production | Current production service/data | Unverified; user earlier reported deleting Render services |
| Screenshot capture | Real UI was previously inspected visually | Current capture tool could display but did not expose a file-save operation; no screenshot file is claimed |

No credentials, database URL, or secret values were printed. All percentages and charts derive from recorded counts, not estimates. Country holdings values are only nonzero for US because only US holdings were found in the prior local snapshot.
