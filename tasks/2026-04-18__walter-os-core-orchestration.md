# Task: Walter OS Core Orchestration

## Goal
Establish the full Walter OS by porting the event-driven, autonomous orchestration layer from the Mary project. This will handle the I/O-heavy scheduling, heartbeat monitoring, and safe execution of global data fetches.

## Done means
- [ ] Migrate `application/os` (Event Bus, Task Runner, Remediation) into the Global Net-Net Scanner repository.
- [ ] Migrate `infrastructure/persistence/sqlite_os_state_store.py` to enable persistent queueing.
- [ ] Refactor `application/os/run_pipeline.py` specifically `build_universe()` to detach from `USSecSource` and hook into the Global Source/Taxonomy mapping framework.
- [ ] Refactor `refresh_fx_rates` to route through the upcoming Deterministic Global FX Normalization service.
- [ ] Activate `data_inspection.py` and `maintenance_audit.py` to auto-quarantine stale global filings and suspicious FX changes.
- [ ] Tests added/updated as required
- [ ] `scripts/check.*` passes

## Constraints / must not change
- Must retain the strict Policy Verifier (`verify_event_policy`); background jobs cannot violate the determining rules.
- Local SQLite database must be the source of truth for the OS state.

## Scope
IN:
- Event Bus and Task Polling.
- Thread heartbeat managers (`_run_with_task_heartbeat`) to protect against hung API calls on international markets.
- Data Quality and Maintenance Audit tasks.

OUT:
- Front-end UI integration of the OS logs (handled in a separate UX task).

## Suggested files (optional)
- `application/os/*`
- `infrastructure/persistence/sqlite_os_state_store.py`
- `application/os/run_pipeline.py`
