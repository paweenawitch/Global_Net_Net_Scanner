# Task: Port Robust Universe Construction from Mary Project

## Goal
Transition the US universe building logic to the resilient, localized architecture developed in the "Mary" module. Instead of cluttering `application/build_universe_service.py` with US-specific rules, we will use a strict contract (`application/universe_schema.py`) and push all SEC-specific parsing, dual-class score-based deduplication (using CIK), and ETF/Unit exclusion logic down to the isolated `tools/build_universe/us_sec.py` extraction script.

## Done means
- [x] Port the `UniverseSchema` definition, normalization (`normalize_universe_df`), and QC functions (`universe_qc`) from Mary to `application/universe_schema.py`.
- [x] Port `tools/build_universe/us_sec.py` from Mary to the main project, ensuring it cleanly constructs US tickers by filtering mutual fund endpoints and applying strict name/code regexes safely.
- [x] Incorporate the CIK-based `sym_score` deduplication method into `us_sec.py` to definitively extract a single, primary voting share for every SEC-registered entity.
- [x] Update `infrastructure/sources/us_sec_source.py` to seamlessly wrap this `us_sec.py` module.
- [x] Refactor `application/build_universe_service.py` to remove ad-hoc deduplication and instead utilize `UniverseSchema` to enforce the contract across all markets seamlessly.
- [x] Ensure `scripts/check.*` passes.

## Constraints / must not change
- Global deduplication must remain conservative (`_dedupe_global`) and purely based on structural schemas (`instrument_id`, `(country, ticker)`, `(country, ticker_base)`), without complex regex logic in the app layer.
- `UniverseSchema` canonical data contract must be strictly respected.

## Scope
IN:
- Migrating domain schemas (`application/universe_schema.py`).
- Migrating the CLI-tool parser for the SEC (`tools/build_universe/us_sec.py`).
- Updating the application runner `application/build_universe_service.py` and the `infrastructure/sources/us_sec_source.py` adapter.

OUT:
- Complex fundamental merging (e.g. market caps). Net-net math handles its own consolidations later; universe's only role is to ensure exactly one primary ticker per company via `CIK` grouping.
- International market changes (they just adhere to the schema).

## Suggested files
- `application/universe_schema.py`
- `application/build_universe_service.py`
- `infrastructure/sources/us_sec_source.py`
- `tools/build_universe/us_sec.py`

## Review Feedback
- **Schema & Deduplication Alignment**: The `UniverseSchema` acts perfectly as the data structural contract, isolating normalization (`normalize_universe_df`). `_dedupe_global` correctly utilizes absolute structural identities (`instrument_id`, `(country, ticker)`) without touching fundamental data attributes like names, precisely meeting the constraint requirements. 
- **Tool Adapter Execution**: `infrastructure/sources/us_sec_source.py` correctly uses `importlib` for dynamic loading of your isolated scripting tool. The `us_sec.py` appropriately contains all the messy CIK mapping, mutual fund logic, regex rules, and dual-class `sym_score` ranking locally, successfully decluttering the outer application layer! 
- **Assessment**: No bugs found. Code strictly follows Uncle Bob's Clean Architecture standards by keeping the complex infrastructure fetch/regex mapping isolated far from the application/domain schema bounds. All boxes successfully checked!
