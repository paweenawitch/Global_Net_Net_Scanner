# Task: Walter OS Storage SQLite Migration

## Goal
Upgrading the core data persistence layer from flat-file JSON storage to a high-concurrency, hybrid SQLite model (relational metadata + JSON blob payloads) to safely handle the I/O load and concurrency of scanning 30,000+ global assets.

## Done means
- [ ] Migrate/Create `infrastructure/persistence/sqlite_filing_store.py` and `sqlite_market_snapshot_store.py`.
- [ ] Configure the SQLite connection wrapper to enforce `PRAGMA journal_mode=WAL` and `synchronous=NORMAL` for thread safety.
- [ ] Implement the table schema storing canonical metadata in indexed columns (ticker, `latest_fs_date`, `currency`) and complex arrays in `financials_json` TEXT columns.
- [ ] Refactor existing data fetching pipelines (e.g., Yahoo Finance logic, SEC logic) to write directly via repository interfaces to the SQLite store rather than `data/tickers/*.json`.
- [ ] Add utility script to migrate any existing `.json` files into the new SQLite database.
- [ ] Tests added/updated as required
- [ ] `scripts/check.*` passes

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
