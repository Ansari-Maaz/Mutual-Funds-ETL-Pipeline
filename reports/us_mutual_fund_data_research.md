# U.S. mutual-fund data research

## Requirement

The U.S. load must identify every active U.S. open-end mutual-fund share class and retain, where published, ticker, currency, ISIN, category, and end-of-day NAV. A source is only considered complete when it provides an authoritative universe and a licensed daily valuation feed that can be joined to that universe.

## What the current SEC import provides

The existing connector uses the SEC [Investment Company Series and Class Information](https://www.sec.gov/data-research/sec-markets-data/investment-company-series-class-information) CSV and filters `Entity Org Type = 30`, the SEC code for Form N-1A/open-end mutual-fund filers.

| Field | Availability from current SEC CSV |
|---|---|
| Active registered fund/share-class universe | Yes, subject to SEC's stated data-quality caveat |
| SEC series ID and class ID | Yes |
| Fund and share-class names | Yes |
| Ticker | Yes when the filer supplies one; the SEC says this field is not required |
| Currency | No |
| ISIN | No |
| Investment category | No |
| Daily NAV | No |

The SEC says its report covers active registered series/classes that have received SEC IDs, that most are open-end mutual funds, and that the report can also include pre-launch or not-yet-reclassified inactive records. It also says the ticker field is optional. This makes it the right public master file, but not a full NAV/reference-data source.

## Official public NAV exception: money-market funds

The SEC's [Form N-MFP](https://www.sec.gov/files/formn-mfp.pdf) requires daily NAV per share at both series and class level for money-market funds. The [N-MFP data-set readme](https://www.sec.gov/files/nmfp_readme.pdf) documents the series and class daily NAV tables. This can provide daily NAV for money-market funds, but it does not cover the full U.S. open-end mutual-fund universe.

## Complete U.S. source required for the assignment

For all U.S. mutual funds and the requested ticker, ISIN, category, currency, and daily NAV fields, this project needs a licensed feed. The most suitable options found are:

| Provider | Published coverage | Relevant fields | Delivery |
|---|---|---|---|
| [Nasdaq Fund Network](https://nasdaqtrader.com/Trader.aspx?id=AgreementsTradingNFN) | Daily valuations submitted for mutual funds, money-market funds, UITs, and related products | Daily NAV; instrument registration includes ticker and identifier changes | Licensed NFN Data Service / daily list |
| [Exchange Data International U.S. Mutual Funds](https://www.exchange-data.com/product/us-mutual-funds/) | 31,000+ U.S. mutual funds, plus UIT and interval-fund coverage | ISIN, ticker, issuer, corporate actions, and daily end-of-day pricing | Licensed online/SFTP files |
| [XigniteNAVs](https://www.xignite.com/product/mutual-fund-NAVs) | U.S. open-end and closed-end mutual funds, money-market funds, UITs, and annuities | Symbol, CIK, CUSIP, ISIN where available; daily and historical NAV | Licensed API |

Nasdaq documents that its public symbol directory has fund symbol, fund name, fund family, type, and a high-level category code. It does **not** provide ISIN or daily NAV in that public directory. See [Nasdaq mutual-fund symbol-directory definitions](https://www.nasdaqtrader.com/trader.aspx?id=symboldirdefs).

## Implementation decision

1. Keep the SEC Form N-1A class file as the authoritative public U.S. master and use its SEC class ID as the stable source key.
2. Add the public Nasdaq directory only as a secondary ticker/family/high-level-type enrichment, with an explicit match-confidence audit.
3. Import N-MFP daily NAV only for money-market funds, marked as that scope.
4. Use a licensed Nasdaq NFN, EDI, or Xignite feed for the full U.S. daily NAV and ISIN/category enrichment. The connector will join by provider identifiers first, then SEC class ID/ticker under auditable matching rules.

## Current blocker

No credential or redistribution license for a complete U.S. fund/NAV vendor has been supplied. Without one, importing values from search pages or guessing NAV, ISIN, currency, or category would create inaccurate records and would not meet the recruiter's requirement.
