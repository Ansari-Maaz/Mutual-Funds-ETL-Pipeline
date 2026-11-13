# Twelve Data vs FundFlow US mutual fund comparison — 2026-11-05

Generated 2026-11-06T14:22:28.463659+00:00.

FundFlow values below are the stored Yahoo Finance daily prices for the same date. This is vendor-to-vendor price comparison, not issuer-verified NAV. Twelve Data values are not imported into FundFlow.

## Price comparison

| Ticker | FundFlow fund name | Twelve Data close | FundFlow value | TD − FundFlow | Same to nearest cent |
|---|---|---:|---:|---:|:---:|
| VFIAX | Vanguard 500 Index Fund — Admiral Shares | 679.020020 | 679.0200000000 | 0.0000200000 | Yes |
| VTSAX | Vanguard Total Stock Market Index Fund — Admiral Shares | 175.48000 | 175.4800000000 | 0E-10 | Yes |
| FXAIX | Fidelity 500 Index Fund | 255.64999 | 255.6500000000 | -0.0000100000 | Yes |
| SWPPX | Schwab S&P 500 Index Fund | 19.010000 | 19.0100000000 | 0E-10 | Yes |
| FCNTX | Fidelity Contrafund | 25.90000 | 25.9000000000 | 0E-10 | Yes |
| DODGX | Dodge & Cox Stock Fund — Class I | 17.89000 | 17.8900000000 | 0E-10 | Yes |
| FBALX | Fidelity Balanced Fund | 31.65000 | 31.6500000000 | 0E-10 | Yes |
| VWELX | VANGUARD WELLINGTON FUND — Investor Shares | 46.0099983 | 46.0100000000 | -0.0000017000 | Yes |
| VBTLX | Vanguard Total Bond Market Index Fund — Admiral Shares | 9.44000 | 9.4400000000 | 0E-10 | Yes |
| VTIAX | Vanguard Total International Stock Index Fund — Admiral Shares | 43.45000 | 43.4500000000 | 0E-10 | Yes |

## Findings

- Symbol, country, currency, and date matched for 10/10 funds; endpoint errors: 0.
- Daily values are exactly equal for 7/10 funds and equal to the nearest cent for 10/10.
- ISIN/CUSIP returned `request_access_via_add_ons`; those values are unavailable under the current subscription. Exchange and OHLC fields are included in the Twelve Data response; FundFlow stores a single daily value.

## Requested response format

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
        "date": "2026-11-05",
        "open": 679.02002,
        "high": 679.02002,
        "low": 679.02002,
        "close": 679.02002
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
    "valuation_date": "2026-11-05",
    "nav": 679.02,
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
        "date": "2026-11-05",
        "open": 175.48,
        "high": 175.48,
        "low": 175.48,
        "close": 175.48
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
    "valuation_date": "2026-11-05",
    "nav": 175.48,
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
        "date": "2026-11-05",
        "open": 255.64999,
        "high": 255.64999,
        "low": 255.64999,
        "close": 255.64999
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
    "valuation_date": "2026-11-05",
    "nav": 255.65,
    "currency": "USD"
  }
}
```

### SWPPX

**TWELVE DATA**

```json
{
  "status": "success",
  "data": {
    "symbol": "SWPPX",
    "instrument_type": "Mutual Fund",
    "exchange": "NASDAQ",
    "mic_code": "XNAS",
    "currency": "USD",
    "exchange_timezone": "America/New_York",
    "interval": "1day",
    "market_data": [
      {
        "date": "2026-11-05",
        "open": 19.01,
        "high": 19.01,
        "low": 19.01,
        "close": 19.01
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
    "valuation_date": "2026-11-05",
    "nav": 19.01,
    "currency": "USD"
  }
}
```

### FCNTX

**TWELVE DATA**

```json
{
  "status": "success",
  "data": {
    "symbol": "FCNTX",
    "instrument_type": "Mutual Fund",
    "exchange": "NASDAQ",
    "mic_code": "XNAS",
    "currency": "USD",
    "exchange_timezone": "America/New_York",
    "interval": "1day",
    "market_data": [
      {
        "date": "2026-11-05",
        "open": 25.9,
        "high": 25.9,
        "low": 25.9,
        "close": 25.9
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
    "valuation_date": "2026-11-05",
    "nav": 25.9,
    "currency": "USD"
  }
}
```

### DODGX

**TWELVE DATA**

```json
{
  "status": "success",
  "data": {
    "symbol": "DODGX",
    "instrument_type": "Mutual Fund",
    "exchange": "NASDAQ",
    "mic_code": "XNMS",
    "currency": "USD",
    "exchange_timezone": "America/New_York",
    "interval": "1day",
    "market_data": [
      {
        "date": "2026-11-05",
        "open": 17.89,
        "high": 17.89,
        "low": 17.89,
        "close": 17.89
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
    "valuation_date": "2026-11-05",
    "nav": 17.89,
    "currency": "USD"
  }
}
```

### FBALX

**TWELVE DATA**

```json
{
  "status": "success",
  "data": {
    "symbol": "FBALX",
    "instrument_type": "Mutual Fund",
    "exchange": "NASDAQ",
    "mic_code": "XNAS",
    "currency": "USD",
    "exchange_timezone": "America/New_York",
    "interval": "1day",
    "market_data": [
      {
        "date": "2026-11-05",
        "open": 31.65,
        "high": 31.65,
        "low": 31.65,
        "close": 31.65
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
    "valuation_date": "2026-11-05",
    "nav": 31.65,
    "currency": "USD"
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
        "date": "2026-11-05",
        "open": 46.0099983,
        "high": 46.0099983,
        "low": 46.0099983,
        "close": 46.0099983
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
    "valuation_date": "2026-11-05",
    "nav": 46.01,
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
        "date": "2026-11-05",
        "open": 9.44,
        "high": 9.44,
        "low": 9.44,
        "close": 9.44
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
    "valuation_date": "2026-11-05",
    "nav": 9.44,
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
        "date": "2026-11-05",
        "open": 43.45,
        "high": 43.45,
        "low": 43.45,
        "close": 43.45
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
    "valuation_date": "2026-11-05",
    "nav": 43.45,
    "currency": "USD"
  }
}
```

