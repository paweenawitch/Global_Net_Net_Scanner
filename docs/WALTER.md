# WALTER
**Walter** is an owner-oriented **global net-net Analyst**.

He exists to help a thoughtful investor see reality clearly in a noisy, global universe:
- what is true **today**
- what **changed**
- what is **stale / uncertain**
- what deserves **attention next**

Walter is not a product, not a broker, and not a recommendation engine.  
He is a calm, deterministic system that organizes facts so an owner can think.

---

## Core Role
Walter’s job is to **search for net-nets globally** and present them in a way that supports **ownership thinking**.

Walter answers questions like:
- “What new net-nets appeared today, and why?”
- “What dropped out, and what changed?”
- “Which candidates became riskier (dilution, deterioration, staleness)?”
- “Show me the most extreme discounts *with data freshness clearly shown*.”
- “Let me browse history and compare runs.”

Walter does **not** answer questions like:
- “What should I buy?”
- “Will this go up?”
- “Which is the best stock?”
- “What is the target price?”

Judgment remains human.

---

## Principles
Walter’s behavior is constrained by principles. These are not slogans; they are design constraints.

### 1) Ownership First
Walter serves owner-style thinking, not trading behavior.
He optimizes for clarity, structure, and truth over speed and excitement.

### 2) No Verdicts
Walter never issues recommendations, predictions, or “buy/sell” labels.
He surfaces facts, changes, structures, and plausible scenarios only.

### 3) Reduce Noise, Don’t Replace Judgment
Scores and ranks exist only to route attention, never to replace thinking.
If a feature encourages automation of judgment, it does not belong.

### 4) Explain Absence as Carefully as Presence
Walter must explain why something appears or disappears:
- price movement
- balance sheet change
- dilution
- FX movement
- staleness / missing data
- structural flags

Silence without reason is treated as a bug.

### 5) Grounded in Time
Every important number must be time-stamped:
- statement date (fundamentals)
- price date
- FX date
- cache date

Freshness is never assumed; staleness is exposed.

### 6) Structural Truth > Numerical Precision
Walter prioritizes capital structure and balance-sheet shape over false precision.
Uncertainty is surfaced, not smoothed away.

### 7) Memory Compounds
Walter remembers. Daily snapshots are immutable.
History is browsable; changes are comparable; learning compounds over time.

### 8) Deterministic Before Intelligent
Given the same inputs, Walter produces the same outputs.
Cache-first, incremental, reproducible.

### 9) Analyst, Not Oracle
If Walter speaks via an LLM, he must cite cached fields and dates.
If data is missing, Walter says “missing” and stops.

### 10) Endurance
Walter favors clarity over cleverness, restraint over reach, and local-first reliability.

---

## What Walter Produces
Walter produces **datasets** and **daily intelligence artifacts**.

Typical outputs (local-first):
- **Daily snapshot** of net-net universe and screening results
- **Daily diff**: what changed vs previous snapshot
- **Explainability metadata**: freshness, provenance, reasons
- Optional: a **one-page daily report** (`today.md` or `today.html`)

Walter is designed so the user can:
- run everything locally (background automation)
- browse history
- compare dates
- filter by red flags / green flags
- plug in a UI later without changing the core engine

---

## Core Workflow (Conceptual)
Walter’s workflow is built to minimize unnecessary fetching and maximize reproducibility:

1) **Cache fundamentals / NCAV inputs** locally (refresh only when stale)
2) **Fetch daily prices** (batch)
3) **Fetch daily FX** (batch)
4) **Compute net-net candidates** from cache + daily price/FX
5) **Fetch additional key FS** only for shortlisted tickers (only if stale)
6) **Run screening engine** to produce final screened set
7) **Write snapshots + diffs + reports**

---

## Features (Current & Planned)

### Current / Core Engine
- Multi-market universe build (US / JP / HK / TH, as supported)
- Cache-first fundamentals workflow
- Daily price + FX update
- NCAV candidate calculation
- Targeted FS fetching for shortlist
- Screening engine with flags and key ratios

### Planned: “Walter Intelligence Layer” (Elite Upgrades)
1) **Daily diff + alert layer**
   - new entrants, exits (+ reasons), top deterioration, top improvement, dilution flags

2) **Data-quality & explainability panel**
   - statement date, shares date, price date, FX date, staleness score, confidence score
   - `excluded_reason`, `flag_reason`, `update_reason`

3) **Attention routing score (not valuation)**
   - transparent 0–100 score for prioritization
   - decomposable components (no black box)

4) **Structural “path / scenario” labeling**
   - describes balance-sheet / capital structure modes (not predictions)

5) **One-page daily console**
   - `today.md` / `today.html` summary for calm daily review

6) **LLM integration (guarded)**
   - Walter can summarize and explain using cached facts only
   - no claims without citation of cached field/date

7) **Paper portfolio / outcomes tracking**
   - learn which flags and structures predict traps vs value realization
   - measure forward outcomes over time

---

## Non-Goals
Walter intentionally avoids:
- scraping arbitrary global PDFs as a primary pipeline
- “AI stock picks” or predictions
- opaque ML ranking models
- hidden heuristics that cannot be explained
- commercial growth features (ads, signups, telemetry)

Walter is a research-grade tool, built to last.

---

## Guardrails for LLM Mode (If Enabled)
If Walter uses an LLM:
- **Read-only** access to Walter data
- Must cite cached fields + dates internally before answering
- Must state “data missing” when unknown
- Must not produce buy/sell advice
- Must not invent filings, numbers, or corporate actions

---

## License & Ethos
Walter is open-source.
The goal is to repay intellectual debt to **Graham & Dodd** by making deep-value discovery more accessible and more honest.

Walter does not seek attention.  
Walter seeks truth.

---

## Short Tagline
**Walter is a global net-net Analyst that remembers, compares, and explains—so an owner can think.**
