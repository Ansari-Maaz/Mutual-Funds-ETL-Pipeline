# FundFlow vs Twelve Data — Beta Review Summary

**Prepared:** 9 November 2026  
**Latest comparison date:** 5 November 2026  
**Coverage:** 10 US mutual-fund share classes; standard Twelve Data fund-directory and one-day time-series endpoints.

## Executive summary

The latest saved comparison completed for all 10 selected funds with no endpoint errors. Twelve Data and FundFlow daily prices agreed to the nearest cent for all 10 funds; 7 of 10 were exactly equal as serialized numeric values. A previous comparison for 30 October agreed to the nearest cent for 9 of 10 funds, with one 2-cent difference for VBTLX.

This is a vendor-to-vendor check. The FundFlow values in these snapshots came from Yahoo Finance and are not independently verified issuer NAVs. The sample and one-day price comparison are useful beta evidence, not proof of full-market coverage or production readiness.

## Price comparison

| Ticker | 30 Oct: Twelve Data | 30 Oct: FundFlow | Same to cent | 5 Nov: Twelve Data | 5 Nov: FundFlow | Same to cent |
|---|---:|---:|:---:|---:|---:|:---:|
| VFIAX | 699.87000 | 699.8700000000 | Yes | 679.020020 | 679.0200000000 | Yes |
| VTSAX | 180.85001 | 180.8500000000 | Yes | 175.48000 | 175.4800000000 | Yes |
| FXAIX | 263.5 | 263.5000000000 | Yes | 255.64999 | 255.6500000000 | Yes |
| SWPPX | 19.59000 | 19.5900000000 | Yes | 19.010000 | 19.0100000000 | Yes |
| FCNTX | 26.71000 | 26.7100000000 | Yes | 25.90000 | 25.9000000000 | Yes |
| DODGX | 17.89000 | 17.8900000000 | Yes | 17.89000 | 17.8900000000 | Yes |
| FBALX | 32.090000 | 32.0900000000 | Yes | 31.65000 | 31.6500000000 | Yes |
| VWELX | 46.64000 | 46.6400000000 | Yes | 46.0099983 | 46.0100000000 | Yes |
| VBTLX | 9.40000 | 9.3800000000 | **No** | 9.44000 | 9.4400000000 | Yes |
| VTIAX | 44.19000 | 44.1900000000 | Yes | 43.45000 | 43.4500000000 | Yes |

## Data coverage and interpretation

- On 5 November, all 10 requested funds returned comparison data; there were 0 endpoint errors.
- Price agreement to the nearest cent was 10/10 on 5 November, versus 9/10 on 30 October. Exact numeric equality was 7/10 and 8/10 respectively; differences below one cent explain the distinction.
- The 5 November report contains 200 field comparisons: 71 exact matches, 29 exact-value or label mismatches, 80 fields Twelve Data returned that FundFlow does not currently store, and 20 identifier fields unavailable under the current Twelve Data subscription. These are field-level counts, not 200 independent price checks.
- The most recent report recorded differences in naming punctuation/capitalization and fund-type labels. Exchange, MIC, timezone, and OHLC fields are not represented in FundFlow's current core profile/one-value-per-day NAV model.
- The 30 October VBTLX price differed by $0.02/share (Twelve Data $9.40, FundFlow $9.38). It matched on 5 November. This isolated discrepancy should be investigated before treating the feed as reconciled.
- The full-data mutual-fund endpoint was not called; the run used the standard directory and time-series endpoints only. No Twelve Data values were imported into the FundFlow database.

## Reproducibility

The comparison runner is `scripts/compare_twelvedata_us_sample.py`; its field-level implementation is `scripts/compare_twelvedata.py`. Run from the project root:

```bash
./.venv/bin/python scripts/compare_twelvedata_us_sample.py --date 2026-11-09
```

If no key is configured in the environment, the runner requests it through hidden terminal input. It writes a JSON result and a detailed Markdown report under `reports/`. The default sample makes two standard API requests per ticker with a 15-second delay between tickers; it does not call the premium full-data endpoint.

## Source reports

- [5 November detailed report](twelvedata_us_fund_comparison_2026-11-05.md) and [raw comparison data](twelvedata_us_fund_comparison_2026-11-05.json)
- [30 October detailed report](twelvedata_us_fund_comparison_2026-10-30.md) and [raw comparison data](twelvedata_us_fund_comparison_2026-10-30.json)

**Freshness note:** this summary consolidates the latest comparison already present in the project, dated 5 November 2026. It does not claim a new Twelve Data run on 9 November; run the command above with an authorized API key to refresh it.
