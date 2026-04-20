# Task: Walter OS Core Orchestration

## Goal
Establish the full Walter OS by porting the event-driven, autonomous orchestration layer from the Mary project. This will handle the I/O-heavy scheduling, heartbeat monitoring, and safe execution of global data fetches.

## Done means
- [x] Migrate `application/os` (Task Runner, Registry, Specs) into the Global Net-Net Scanner repository.
- [x] Migrate `infrastructure/persistence/sqlite_os_state_store.py` to enable persistent tracking and locking.
- [x] Refactor `application/os/run_pipeline.py` to use `run_cli` entry points for all core background scripts.
- [x] Add **Regional Parallelism** support to `main.py` to match manual sharding workflows.
- [x] Refactor `refresh_fx_rates` to route through the Determinstic Service.
- [x] Port `DataInspectionService` and `MaintenanceAuditService` to auto-flag stale filings and missing market data.
- [x] Integrate orchestration with the **FastAPI Control Center** for remote execution.
- [x] `scripts/check.*` passes

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
