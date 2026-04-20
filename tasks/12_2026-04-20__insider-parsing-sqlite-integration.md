# Task: Insider Parsing SQLite Integration

## Goal
Transition insider parsing from the legacy file-based cache to the unified SQLite storage and wire it into the Walter OS orchestration to ensure the screener has access to fresh data.

## Done means
- [ ] Refactored `FetchFundamentalsService` or its callers to use `BuildFundamentalsService` for SQLite persistence.
- [ ] `BuildFundamentalsService.update_insider_cache` is correctly wired to the `fetch_full` pipeline.
- [ ] Walter OS `weekly_fetch_insiders` task successfully populates the `insider_snapshots` table in `data/db/filings.sqlite`.
- [ ] Legacy `cache/sec_insider/` JSON writing logic is removed.
- [ ] `scripts/check.*` passes (if applicable).

## Constraints / must not change
- Must maintain the existing SEC Form 4 parsing logic (`_summarize_form4` in `USSecSource`).
- Storage must use the `SqliteFilingStore` schema for `insider_snapshots`.

## Scope
IN:
- `application/cli/main_fetch_full_cache.py`
- `application/services/fetch_fundamentals_service.py`
- `application/os/run_pipeline.py`
- `infrastructure/repositories/sqlite_insider_repository.py` integration.

OUT:
- Yahoo-based insider fetching (remains a stub for now).

## Suggested files (optional)
- `application/cli/main_fetch_full_cache.py`
- `application/services/fetch_fundamentals_service.py`
- `application/build_fundamentals_service.py`
- `application/os/run_pipeline.py`
