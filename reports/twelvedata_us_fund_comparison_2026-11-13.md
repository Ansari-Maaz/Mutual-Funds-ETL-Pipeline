# Twelve Data vs FundFlow US mutual fund comparison — 2026-11-13

Generated 2026-11-14T19:06:09.430243+00:00.

FundFlow prices below are the stored Yahoo Finance daily prices for the same date. This is vendor-to-vendor price comparison, not issuer-verified NAV. Twelve Data values are not imported into FundFlow.

## Price comparison

| Ticker | FundFlow fund name | Twelve Data close | FundFlow value | TD − FundFlow | Same to nearest cent |
|---|---|---:|---:|---:|:---:|
| VFIAX | Vanguard 500 Index Fund — Admiral Shares | 698.47998 | 698.4800000000 | -0.0000200000 | Yes |
| VTSAX | Vanguard Total Stock Market Index Fund — Admiral Shares | 180.64000 | 180.6400000000 | 0E-10 | Yes |
| VWELX | VANGUARD WELLINGTON FUND — Investor Shares | 46.70000 | 46.7000000000 | 0E-10 | Yes |
| VBTLX | Vanguard Total Bond Market Index Fund — Admiral Shares | 9.28000 | 9.2800000000 | 0E-10 | Yes |
| VTIAX | Vanguard Total International Stock Index Fund — Admiral Shares | 44.29000 | 44.2900000000 | 0E-10 | Yes |

## Findings

- Symbol, country, currency, and date matched for 5/10 funds; endpoint errors: 4.
- Daily values are exactly equal for 4/5 funds and equal to the nearest cent for 5/5.
- ISIN/CUSIP returned `request_access_via_add_ons`; those values are unavailable under the current subscription. Exchange and OHLC fields are included in the Twelve Data response; FundFlow stores a single daily value.

The response blocks below use the requested format.

### VFIAX

**TWELVE DATA**

```json
{
  "status": "success",
  "data": {
    "symbol": "VFIAX",
    "instrument_type": "Mutual Fund",
    "exchange": "NASDAQ",
    "mic_code": "XNAS",
    "currency": "USD",
    "exchange_timezone": "America/New_York",
    "interval": "1day",
    "market_data": [
      {
        "date": "2026-11-13",
        "open": 698.47998,
        "high": 698.47998,
        "low": 698.47998,
        "close": 698.47998
      }
    ]
  }
}
```

**FUNDFLOW**

```json
{
  "status": "success",
  "data": {
    "name": "Vanguard 500 Index Fund — Admiral Shares",
    "ticker": "VFIAX",
    "valuation_date": "2026-11-13",
    "nav": 698.48,
    "currency": "USD"
  }
}
```

### VTSAX

**TWELVE DATA**

```json
{
  "status": "success",
  "data": {
    "symbol": "VTSAX",
    "instrument_type": "Mutual Fund",
    "exchange": "NASDAQ",
    "mic_code": "XNMS",
    "currency": "USD",
    "exchange_timezone": "America/New_York",
    "interval": "1day",
    "market_data": [
      {
        "date": "2026-11-13",
        "open": 180.64,
        "high": 180.64,
        "low": 180.64,
        "close": 180.64
      }
    ]
  }
}
```

**FUNDFLOW**

```json
{
  "status": "success",
  "data": {
    "name": "Vanguard Total Stock Market Index Fund — Admiral Shares",
    "ticker": "VTSAX",
    "valuation_date": "2026-11-13",
    "nav": 180.64,
    "currency": "USD"
  }
}
```

### FXAIX

**TWELVE DATA**

```json
{
  "status": "success",
  "data": {
    "symbol": "FXAIX",
    "instrument_type": "Mutual Fund",
    "exchange": "NASDAQ",
    "mic_code": "XNAS",
    "currency": "USD",
    "exchange_timezone": "America/New_York",
    "interval": "1day",
    "market_data": [
      {
        "date": "2026-11-13",
        "open": null,
        "high": null,
        "low": null,
        "close": null
      }
    ]
  }
}
```

**FUNDFLOW**

```json
{
  "status": "success",
  "data": {
    "name": "Fidelity 500 Index Fund",
    "ticker": "FXAIX",
    "valuation_date": null,
    "nav": null,
    "currency": "USD"
  }
}
```

### SWPPX

**TWELVE DATA**

```json
{
  "status": "error",
  "data": {
    "symbol": null,
    "instrument_type": null,
    "exchange": null,
    "mic_code": null,
    "currency": null,
    "exchange_timezone": null,
    "interval": "1day",
    "market_data": [
      {
        "date": null,
        "open": null,
        "high": null,
        "low": null,
        "close": null
      }
    ]
  }
}
```

**FUNDFLOW**

```json
{
  "status": "success",
  "data": {
    "name": "Schwab S&P 500 Index Fund",
    "ticker": "SWPPX",
    "valuation_date": null,
    "nav": null,
    "currency": null
  }
}
```

### FCNTX

**TWELVE DATA**

```json
{
  "status": "error",
  "data": {
    "symbol": null,
    "instrument_type": null,
    "exchange": null,
    "mic_code": null,
    "currency": null,
    "exchange_timezone": null,
    "interval": "1day",
    "market_data": [
      {
        "date": null,
        "open": null,
        "high": null,
        "low": null,
        "close": null
      }
    ]
  }
}
```

**FUNDFLOW**

```json
{
  "status": "success",
  "data": {
    "name": "Fidelity Contrafund",
    "ticker": "FCNTX",
    "valuation_date": null,
    "nav": null,
    "currency": null
  }
}
```

### DODGX

**TWELVE DATA**

```json
{
  "status": "error",
  "data": {
    "symbol": null,
    "instrument_type": null,
    "exchange": null,
    "mic_code": null,
    "currency": null,
    "exchange_timezone": null,
    "interval": "1day",
    "market_data": [
      {
        "date": null,
        "open": null,
        "high": null,
        "low": null,
        "close": null
      }
    ]
  }
}
```

**FUNDFLOW**

```json
{
  "status": "success",
  "data": {
    "name": "Dodge & Cox Stock Fund — Class I",
    "ticker": "DODGX",
    "valuation_date": null,
    "nav": null,
    "currency": null
  }
}
```

### FBALX

**TWELVE DATA**

```json
{
  "status": "error",
  "data": {
    "symbol": null,
    "instrument_type": null,
    "exchange": null,
    "mic_code": null,
    "currency": null,
    "exchange_timezone": null,
    "interval": "1day",
    "market_data": [
      {
        "date": null,
        "open": null,
        "high": null,
        "low": null,
        "close": null
      }
    ]
  }
}
```

**FUNDFLOW**

```json
{
  "status": "success",
  "data": {
    "name": "Fidelity Balanced Fund",
    "ticker": "FBALX",
    "valuation_date": null,
    "nav": null,
    "currency": null
  }
}
```

### VWELX

**TWELVE DATA**

```json
{
  "status": "success",
  "data": {
    "symbol": "VWELX",
    "instrument_type": "Mutual Fund",
    "exchange": "NASDAQ",
    "mic_code": "XNAS",
    "currency": "USD",
    "exchange_timezone": "America/New_York",
    "interval": "1day",
    "market_data": [
      {
        "date": "2026-11-13",
        "open": 46.7,
        "high": 46.7,
        "low": 46.7,
        "close": 46.7
      }
    ]
  }
}
```

**FUNDFLOW**

```json
{
  "status": "success",
  "data": {
    "name": "VANGUARD WELLINGTON FUND — Investor Shares",
    "ticker": "VWELX",
    "valuation_date": "2026-11-13",
    "nav": 46.7,
    "currency": "USD"
  }
}
```

### VBTLX

**TWELVE DATA**

```json
{
  "status": "success",
  "data": {
    "symbol": "VBTLX",
    "instrument_type": "Mutual Fund",
    "exchange": "NASDAQ",
    "mic_code": "XNAS",
    "currency": "USD",
    "exchange_timezone": "America/New_York",
    "interval": "1day",
    "market_data": [
      {
        "date": "2026-11-13",
        "open": 9.28,
        "high": 9.28,
        "low": 9.28,
        "close": 9.28
      }
    ]
  }
}
```

**FUNDFLOW**

```json
{
  "status": "success",
  "data": {
    "name": "Vanguard Total Bond Market Index Fund — Admiral Shares",
    "ticker": "VBTLX",
    "valuation_date": "2026-11-13",
    "nav": 9.28,
    "currency": "USD"
  }
}
```

### VTIAX

**TWELVE DATA**

```json
{
  "status": "success",
  "data": {
    "symbol": "VTIAX",
    "instrument_type": "Mutual Fund",
    "exchange": "NASDAQ",
    "mic_code": "XNAS",
    "currency": "USD",
    "exchange_timezone": "America/New_York",
    "interval": "1day",
    "market_data": [
      {
        "date": "2026-11-13",
        "open": 44.29,
        "high": 44.29,
        "low": 44.29,
        "close": 44.29
      }
    ]
  }
}
```

**FUNDFLOW**

```json
{
  "status": "success",
  "data": {
    "name": "Vanguard Total International Stock Index Fund — Admiral Shares",
    "ticker": "VTIAX",
    "valuation_date": "2026-11-13",
    "nav": 44.29,
    "currency": "USD"
  }
}
```

