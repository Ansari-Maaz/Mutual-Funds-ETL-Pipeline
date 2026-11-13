# Twelve Data vs FundFlow US mutual fund comparison — 2026-11-06

Generated 2026-11-09T08:46:59.248110+00:00.

FundFlow prices below are the stored Yahoo Finance daily prices for the same date. This is vendor-to-vendor price comparison, not issuer-verified NAV. Twelve Data values are not imported into FundFlow.

## Price comparison

| Ticker | FundFlow fund name | Twelve Data close | FundFlow value | TD − FundFlow | Same to nearest cent |
|---|---|---:|---:|---:|:---:|
| VFIAX | Vanguard 500 Index Fund — Admiral Shares | 681.20001 | 681.2000000000 | 0.0000100000 | Yes |
| VTSAX | Vanguard Total Stock Market Index Fund — Admiral Shares | 176.16000 | 176.1600000000 | 0E-10 | Yes |
| FXAIX | Fidelity 500 Index Fund | 256.48001 | 256.4800000000 | 0.0000100000 | Yes |
| SWPPX | Schwab S&P 500 Index Fund | 19.070000 | 19.0700000000 | 0E-10 | Yes |
| FCNTX | Fidelity Contrafund | 26.15000 | 26.1500000000 | 0E-10 | Yes |
| DODGX | Dodge & Cox Stock Fund — Class I | 17.82000 | 17.8200000000 | 0E-10 | Yes |
| FBALX | Fidelity Balanced Fund | 31.72000 | 31.7200000000 | 0E-10 | Yes |
| VWELX | VANGUARD WELLINGTON FUND — Investor Shares | 46.090000 | 46.0900000000 | 0E-10 | Yes |
| VBTLX | Vanguard Total Bond Market Index Fund — Admiral Shares | 9.43000 | 9.4300000000 | 0E-10 | Yes |
| VTIAX | Vanguard Total International Stock Index Fund — Admiral Shares | 43.45000 | 43.4500000000 | 0E-10 | Yes |

## Findings

- Symbol, country, currency, and date matched for 10/10 funds; endpoint errors: 0.
- Daily values are exactly equal for 8/10 funds and equal to the nearest cent for 10/10.
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
        "date": "2026-11-06",
        "open": 681.20001,
        "high": 681.20001,
        "low": 681.20001,
        "close": 681.20001
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
    "valuation_date": "2026-11-06",
    "nav": 681.2,
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
        "date": "2026-11-06",
        "open": 176.16,
        "high": 176.16,
        "low": 176.16,
        "close": 176.16
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
    "valuation_date": "2026-11-06",
    "nav": 176.16,
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
        "date": "2026-11-06",
        "open": 256.48001,
        "high": 256.48001,
        "low": 256.48001,
        "close": 256.48001
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
    "valuation_date": "2026-11-06",
    "nav": 256.48,
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
        "date": "2026-11-06",
        "open": 19.07,
        "high": 19.07,
        "low": 19.07,
        "close": 19.07
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
    "valuation_date": "2026-11-06",
    "nav": 19.07,
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
        "date": "2026-11-06",
        "open": 26.15,
        "high": 26.15,
        "low": 26.15,
        "close": 26.15
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
    "valuation_date": "2026-11-06",
    "nav": 26.15,
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
        "date": "2026-11-06",
        "open": 17.82,
        "high": 17.82,
        "low": 17.82,
        "close": 17.82
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
    "valuation_date": "2026-11-06",
    "nav": 17.82,
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
        "date": "2026-11-06",
        "open": 31.72,
        "high": 31.72,
        "low": 31.72,
        "close": 31.72
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
    "valuation_date": "2026-11-06",
    "nav": 31.72,
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
        "date": "2026-11-06",
        "open": 46.09,
        "high": 46.09,
        "low": 46.09,
        "close": 46.09
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
    "valuation_date": "2026-11-06",
    "nav": 46.09,
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
        "date": "2026-11-06",
        "open": 9.43,
        "high": 9.43,
        "low": 9.43,
        "close": 9.43
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
    "valuation_date": "2026-11-06",
    "nav": 9.43,
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
        "date": "2026-11-06",
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
    "valuation_date": "2026-11-06",
    "nav": 43.45,
    "currency": "USD"
  }
}
```

