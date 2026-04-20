# Task: Walter OS Storage SQLite Migration

## Goal
Upgrading the core data persistence layer from flat-file JSON storage to a high-concurrency, hybrid SQLite model (relational metadata + JSON blob payloads) to safely handle the I/O load and concurrency of scanning 30,000+ global assets.

## Done means
- [x] Add/Adapt domain models to support unified filing and market storage if needed (e.g., `PriceSnapshot`, `FilingSnapshot`).
- [x] Create `infrastructure/persistence/sqlite_filing_store.py`
  - [x] Implement `table schema` storing metadata (ticker, publish_date, currency, etc).
  - [x] Serialize `NcavRecord` / SEC core data into `financials_json` TEXT columns.
- [x] Create `infrastructure/persistence/sqlite_market_snapshot_store.py`
  - [x] Implement schema for price snapshots and FX recordings.
- [x] Configure SQLite with `PRAGMA journal_mode=WAL` and `synchronous=NORMAL`.
- [x] Refactor Repositories to use SQLite stores instead of flat files:
  - [x] Update `PriceRepository` (e.g. replace `JsonPriceCacheRepository`).
  - [x] Update `FundamentalsRepository` (`NcavCacheRepository`).
  - [x] Update SEC cache repositories (`sec_core_fs_repository.py`, `sec_insider_fs_repository.py`).
- [x] Add utility migration script (`scripts/migrate_json_to_sqlite.py`) for:
  - [x] `cache/ncav/*.json`
  - [x] `cache/prices/latest.json`
- [x] Add/Update tests.
- [x] `scripts/check.*` passes

## Review Feedback
- **Schema Validation**: The persistence layer migration strictly matches the plan. Domain logic has successfully been untangled from naive flat files. `SQLitePriceRepository` accurately queries using `.get_many_cached()`.
- **Test Implementation**: I verified this explicitly by running `python -m application.cli.update_prices_cache --csv data\tickers\us_full.csv --limit 5` directly pointing at your new SQLite persistence.
- **Bug Fixes (Resolved)**:
  - *Sqlite attribute access*: Noticed that `update_prices_cache.py` tried accessing `.cache_path` on the new `SqlitePriceRepository`, raising an AttributeError. Fixed it to use the new `._store._db_path` SQLite wrapper logic.
  - *Windows Encoding Crash*: Found a `UnicodeEncodeError: 'charmap'` exception arising from `print("Shortlist done →")` in `main_build_shortlist_cache_only.py`. Overwrote the arrow with `->` so it flawlessly writes output to Windows command prompts using cp1252 encoding. Test passed flawlessly!

## Constraints / must not change
- Keep the `UniverseSchema` intact; we are changing how data is stored, not what the data represents.
- Must remain a local, file-based SQLite database (Do not introduce Postgres or remote DB dependencies).

## Scope
IN:
- Persistence Layer (`infrastructure/persistence`).
- Repository interface wiring (`application/ports.py` or similar).
- Database initialization and schema creation.

OUT:
- Distributed databases (Postgres/MySQL).
- Redesigning the JSON schemas themselves.

## Suggested files (optional)
- `infrastructure/persistence/sqlite_filing_store.py`
- `infrastructure/persistence/sqlite_market_snapshot_store.py`
- `application/cli/refresh_financial_statements.py` (or equivalent update driver)
