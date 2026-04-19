# Task: Dismantling Legacy Tools (Clean Architecture Refactor)

## Goal
The `tools/` directory currently houses massive "God Objects" (like `non_us_fetch_companyfact.py` at 33KB and `sec_extract_core.py` at 18KB). These scripts mix network fetching, unstructured parsing, and domain logic together, completely violating Uncle Bob's Clean Architecture. This task will systematically dismantle `tools/` and distribute its logic into the correct architectural layers.

## Done means
- [ ] Refactor `tools/sec_extract_core.py` by placing the network logic in `infrastructure/sources` and parsing rules in `application/`.
- [ ] Refactor `tools/non_us_fetch_companyfact.py` into `infrastructure/sources/` using the new global data boundaries.
- [ ] Migrate `tools/screening_engine.py` logic directly into `domain/playbooks/net_net/` and `application/run_screening.py`.
- [ ] Eliminate `tools/ncav_cache.py` by relying entirely on the new SQLite hybrid storage layer.
- [ ] Delete the `tools/` directory completely.
- [ ] Tests added/updated as required
- [ ] `scripts/check.*` passes

## Constraints / must not change
- No domain logic or math can leak into `infrastructure/` during this migration.
- Existing screening math output must remain exactly the same (pure refactor).

## Scope
IN:
- Deleting `tools/` entirely.
- Refactoring scripts into `application/` and `infrastructure/` boundaries.

OUT:
- Adding new scraping targets or data sources (strictly moving existing logic).

## Suggested files (optional)
- `tools/*`
- `infrastructure/sources/*`
- `domain/playbooks/*`
