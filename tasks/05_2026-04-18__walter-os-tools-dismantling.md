# Task: Dismantling Legacy Tools (Clean Architecture Refactor)

## Goal
The `tools/` directory currently houses massive "God Objects" (like `non_us_fetch_companyfact.py` at 33KB and `sec_extract_core.py` at 18KB). These scripts mix network fetching, unstructured parsing, and domain logic together, completely violating Uncle Bob's Clean Architecture. This task will systematically dismantle `tools/` and distribute its logic into the correct architectural layers, while migrating all data persistence from CSV/JSON to a unified SQLite database.

## Done means
- [x] Refactor `tools/sec_extract_core.py` by placing the network logic in `infrastructure/sources` and parsing rules in `infrastructure/sources/parsers`.
- [x] Refactor `tools/non_us_fetch_companyfact.py` into `infrastructure/sources/` using the new global data boundaries.
- [x] Migrate `tools/screening_engine.py` logic directly into `application/screening_service.py` and `application/cli/run_screening.py`.
- [x] Eliminate `tools/ncav_cache.py` by relying entirely on the new SQLite hybrid storage layer.
- [x] Implement `SqliteUniverseRepository`, `SqliteShortlistRepository`, and `SqliteInsiderRepository`.
- [x] Create a migration script `scripts/migrate_files_to_sqlite.py` to port existing data.
- [x] Delete the `tools/`, `cache/sec_core/`, and `cache/sec_insider/` directories completely.
- [x] Tests added/updated as required.
- [x] `scripts/check.*` passes.

## Review Feedback
- **Dismantling Integrity**: The `tools/` directory has been successfully eliminated. Large legacy scripts like `sec_extract_core.py` and `non_us_fetch_companyfact.py` have been refactored into high-quality source adapters in `infrastructure/sources/`.
- **Infrastructure Progress**: `SqliteUniverseRepository`, `SqliteShortlistRepository`, and `SqliteInsiderRepository` are fully implemented and integrated. 
- **Migration**: The `scripts/migrate_files_to_sqlite.py` script covers the transition of universe, shortlist, SEC core, and insider data. 
- **User Verification**: Recent CLI updates (e.g., in `update_prices_cache.py`) correctly switch from CSV-based loaders to `SqliteUniverseRepository`, proving the new architecture is being actively adopted.
- **Next Steps**: With the "Tools" layer gone, the project is now a textbook example of Clean Architecture, ready for the taxonomy mapping and orchestration phases.

## Implementation Plan

### Phase 1: DB & Repository Layer
1. **Expand `SqliteFilingStore`**: Add tables for `universe`, `shortlist`, and `insider_snapshots`.
2. **Implement Repositories**:
   - `SqliteUniverseRepository` (Ports: `UniverseRepository`)
   - `SqliteShortlistRepository` (Ports: `ShortlistRepository`)
   - `SqliteInsiderRepository` (Ports: `InsiderRepository`)
3. **Refactor `FundamentalsRepository`**: Ensure it uses SQLite snapshots instead of individual JSON files.

### Phase 2: Logic Migration
1. **SEC Source**: Extract logic from `sec_extract_core.py` to `infrastructure/sources/us_sec_source.py`.
2. **Yahoo Source**: Extract logic from `non_us_fetch_companyfact.py` and `ncav_cache.py` to `infrastructure/sources/yahoo_source.py`.
3. **Fundamentals Service**: Create `application/build_fundamentals_service.py` to orchestrate fetching and saving to DB.
4. **Screening CLI**: Create `application/cli/run_screening.py` using the new repositories and services.

### Phase 3: Migration & Cleanup
1. **Migration Script**: Create and run `scripts/migrate_files_to_sqlite.py`.
2. **Verification**: Confirm `run_screening.py` produces identical results to the legacy engine.
3. **Deletion**: Scrub the `tools/` and `cache/` directories.

## Constraints / must not change
- No domain logic or math can leak into `infrastructure/` during this migration.
- Existing screening math output must remain exactly the same (pure refactor).

## Scope
IN:
- Deleting `tools/` entirely.
- Refactoring scripts into `application/` and `infrastructure/` boundaries.
- Migrating CSV/JSON persistence to SQLite.

OUT:
- Adding new scraping targets or data sources (strictly moving existing logic).

## Suggested files
- `infrastructure/persistence/sqlite_filing_store.py`
- `infrastructure/repositories/sqlite_*.py`
- `infrastructure/sources/*.py`
- `application/cli/run_screening.py`
