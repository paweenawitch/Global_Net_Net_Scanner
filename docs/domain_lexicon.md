# Domain Lexicon

This document defines the mathematical and conceptual truths underpinning the net-net valuation formulas. The core goal of the project is determinism.

## Core Financial Metrics

### Current Ratio
**Current Assets** divided by **Current Liabilities**. 
```text
current_ratio = assets_current / liab_current
```
*Note: Evaluates baseline liquidity.*

### Debt-to-Equity (Graham-Style)
**Total Liabilities** divided by **Equity**. If explicit equity is not stated on the balance sheet, it is implicitly derived as `Total Assets - Total Liabilities`.
```text
debt_to_equity = liab_total / equity
```

### NCAV Native (Net Current Asset Value)
Net Current Asset Value expressed in the company's reporting currency. Calculates the liquidation bedrock. 
If `assets_current` is unstated, it dangerously falls back to `assets_total`.
```text
ncav_total_native = assets_current - liab_total
```

### NCAV Per Share
```text
ncav_per_share = ncav_total_native / shares_out
```

### Price to NCAV Per Share
Market snapshot reality test. Passing the Graham boundary generally means the stock trades below 2/3rds (0.67x) of its NCAV per share.
```text
price_to_ncavps = last_price / ncav_per_share
```

### Margin of Safety
A percentage expression of the discount against NCAV per share.
```text
margin_of_safety = 1 - price_to_ncavps
```

## Advanced & Calculated Metrics

### Dilution
Percentage change in `shares_out`. We track it strictly over 3 axes:
- **dilution_qoq**: Quarter-Over-Quarter.
- **dilution_hoh**: Half-Over-Half (6-month comparisons).
- **dilution_yoy**: Year-Over-Year.
```text
dilution = (shares_out_new - shares_out_old) / shares_out_old
```
If any of `dilution_qoq`, `dilution_hoh`, or `dilution_yoy` is greater than 5%, the company receives a red flag:
```text
Dilution QoQ >5%
Dilution HoH >5%
Dilution YoY >5%
```

### DilutionCAGR
Compound Annual Growth Rate of issued shares over a multi-year window (e.g. 3 years). Identifies chronic, structured shareholder dilution traps.
```text
DilutionCAGR = ( (shares_out_latest / shares_out_oldest) ^ (1 / years) ) - 1
```

### ROCE_adj (Adjusted Return on Capital Employed)
A stricter calculation of classical ROCE aimed specifically at stripping out transient accounting noise or cyclical windfalls.
```text
ROCE_adj = (EBIT - One_Off_Gains) / (Total_Assets - Current_Liabilities)
```

### FCF Yield (Free Cash Flow Yield)
Standardizing core operating cash generating power compared to the current market valuation.
```text
FCF_Yield = (Operating_Cash_Flow - Capital_Expenditures) / Market_Cap
```

## Categorical Flags

- **Green Flags**: Positive compliance rules (e.g., `price_to_ncavps <= 0.67`).
- **Red Flags**: Defensive veto lines (e.g., dilution QoQ/HoH/YoY > 5%, severe 12-month or 3-year issuance, poor current ratio compliance, staleness of filings).
