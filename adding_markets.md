# How to Add a New Market to Global Net-Net Scanner

*(Practical checklist — battle tested with Thailand)*

This project is designed so **adding a new country is mostly plumbing, not logic**.
If you follow the steps below, the market will automatically flow through:

```
Universe → NCAV cache → Shortlist → NON-US fetch → Screening
```

No special cases downstream.

---

## 0. Decide the house ticker convention (one-time decision)

Pick a **house ticker suffix** and never change it.

Examples:

```
US → AAPL.US
Japan → 7203.JP
Hong Kong → 0005.HK
Thailand → PTTEP.TH
```

Rules:

* One ticker = one economic entity
* Suffix encodes country / exchange
* Yahoo mapping happens later

---

## 1. Find a free, full ticker roster (authoritative or static)

You need **one source** that provides:

* all common stocks
* symbols + company names
* no login / no paid API

Preferred order:

1. Exchange static CSV/XLS (even if HTML-disguised)
2. Exchange downloadable directory
3. Government / regulator mirror
4. Last-resort: reputable aggregator

⚠️ Excel opening ≠ machine-readable Excel
Always inspect raw bytes (`<table>` means HTML).

---

## 2️. Write a market universe builder (tools/build_universe)

Create:

```
tools/build_universe/<market>.py
```

Responsibilities:

* Download the roster
* Parse CSV / XLS / HTML table
* Filter out non-common-stock instruments
* Normalize to **this exact schema**:

```csv
ticker_base,ticker,name,country,mic
```

Example normalization:

```python
ticker_base = "PTTEP"
ticker      = "PTTEP.TH"
country     = "TH"
mic         = "XBKK"
```

**Rule:**
The script must **always write a CSV**, even if empty (fail-safe).

---

## 3️. Add a TickerSource adapter (infrastructure/sources)

Create:

```
infrastructure/sources/<market>_source.py
```

Responsibilities:

* Ensure `<market>_full.csv` exists (run builder if needed)
* Load CSV
* Return a DataFrame with required columns

No filtering. No logic. No prints.

This keeps the architecture clean.

---

## 4. Register the market in build_universe CLI

Edit:

```
application/cli/build_universe.py
```

Add your source:

```python
sources = [
    USSecSource(...),
    JPJpxSource(...),
    HKHKEXSource(...),
    NewMarketSource(...),
]
```

That’s it.

If the market doesn’t show up later, **it’s not excluded here**.

---

## 5. Verify universe inclusion (don’t trust logs)

Logs can lie. Data doesn’t.

Always verify with data:

```bash
python application/cli/build_universe.py
python -c "
import pandas as pd
df=pd.read_csv('data/tickers/global_full.csv')
print(df[df['country']=='XX'].head())
print('Rows:', (df['country']=='XX').sum())
"
```

If rows > 0 → market is included.

---

## 6. Yahoo mapping (usually already exists)

Check:

```
tools/ncav_cache.py → to_yahoo()
```

Add mapping only if needed:

```python
if s.endswith(".TH"):
    return s[:-3] + ".BK"
```

Most markets only need this once.

---

## 7. Fundamentals: nothing special for NON-US

If the market:

* is non-US
* has Yahoo coverage

Then **NON_US fetch already works**.

No new jobs. No registry changes.

---

## 8. Currency handling (important, easy to miss)

NCAVPS must be compared to price **in the same currency**.

Two safe options:

### Option A (current approach)

Add suffix → currency mapping:

```python
if house_ticker.endswith(".TH"):
    return "THB"
```

### Option B (recommended long-term)

Use reporting currency directly:

```python
target_ccy = currency
```

Never default non-US stocks to USD.

---

## 9. Logs are optional — data correctness is not

Some markets print logs (US/JP/HK) because their builders print.

Others won’t.

**Absence of log ≠ absence of data.**

Always trust:

```
data/tickers/<market>_full.csv
data/tickers/global_full.csv
```

---

## 10. Final validation checklist

Before calling the market “done”:

* [ ] `<market>_full.csv` exists
* [ ] Global universe contains the country
* [ ] Yahoo symbol resolves
* [ ] NCAV cache builds
* [ ] Shortlist includes market tickers
* [ ] Screening runs without conditionals

If all pass → market is successfully added. Good luck searching for diamonds in the graveyards.

---

