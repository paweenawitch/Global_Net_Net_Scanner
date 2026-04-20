from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _dumps(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def _loads(value: Optional[str]) -> Any:
    if value is None:
        return None
    return json.loads(value)


def _to_dt(value: Optional[str]) -> Optional[datetime]:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


@dataclass(frozen=True, slots=True)
class EventRecord:
    id: int
    event_type: str
    status: str
    payload: dict[str, Any]
    handler_name: Optional[str]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class RuntimeStateRecord:
    runtime_name: str
    state: dict[str, Any]
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class TaskLockRecord:
    task_name: str
    lock_owner: str
    locked_at: datetime


@dataclass(frozen=True, slots=True)
class TaskRunRecord:
    id: int
    task_name: str
    started_at: datetime
    finished_at: Optional[datetime]
    status: str
    error_message: Optional[str]
    params: dict[str, Any]
    trigger_type: str
    related_run_id: Optional[str]


@dataclass(frozen=True, slots=True)
class IncidentRecord:
    id: int
    dedup_key: str
    status: str
    severity: str
    category: str
    scope: str
    signature: str
    anchor_date: str
    title: str
    details: dict[str, Any]
    occurrence_count: int
    first_seen_at: datetime
    last_seen_at: datetime
    updated_at: datetime
    related_event_id: Optional[int]
    related_task_run_id: Optional[int]


@dataclass(frozen=True, slots=True)
class MaintenanceBundleRecord:
    id: int
    created_at: datetime
    window_start: datetime
    window_end: datetime
    status: str
    summary: dict[str, Any]
    requires_human_approval: bool
    approved_by: Optional[str]
    approved_at: Optional[datetime]


@dataclass(frozen=True, slots=True)
class FailedTaskSummary:
    task_name: str
    failure_count: int
    latest_error_message: str
    latest_started_at: datetime


@dataclass(frozen=True, slots=True)
class FailedEventSummary:
    event_id: int
    event_type: str
    error_message: str
    created_at: datetime
    dedup_key: Optional[str]


@dataclass(frozen=True, slots=True)
class MetricRecord:
    measured_at: datetime
    metric_type: str
    metric_name: str
    metric_value: float
    unit: str


@dataclass(frozen=True, slots=True)
class DataInspectionCoverageRecord:
    id: int
    ticker: str
    anchor_date: str
    run_id: Optional[str]
    name: Optional[str]
    has_filing_anchor: bool
    has_reason_card: bool
    has_price_snapshot: bool
    has_required_return_snapshot: bool
    has_fx_snapshot_if_needed: bool
    missing_fields: list[str]
    summary_status: str
    details: dict[str, Any]
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class DebugCaseRecord:
    id: int
    debug_case_id: str
    protocol_version: str
    created_at: datetime
    updated_at: datetime
    origin: str
    workflow: str
    entity_type: str
    entity_id: str
    trigger_type: str
    severity: str
    truth_risk_level: str
    status: str
    allowed_retry_action_set: list[str]
    incident_id: Optional[int]
    task_run_id: Optional[int]
    run_id: Optional[str]
    filing_id: Optional[str]


@dataclass(frozen=True, slots=True)
class DebugCaseArtifactRecord:
    id: int
    debug_case_id: str
    artifact_kind: str
    payload: dict[str, Any]
    created_at: datetime


class SqliteOsStateStore:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._ensure_tables()

    @property
    def db_path(self) -> str:
        return self._db_path

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self._db_path)
        con.execute("PRAGMA journal_mode=WAL;")
        con.execute("PRAGMA synchronous=NORMAL;")
        return con

    def _ensure_tables(self) -> None:
        with self._connect() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS task_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_name TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    params_json TEXT,
                    trigger_type TEXT NOT NULL,
                    related_run_id TEXT
                );
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_task_runs_name_started "
                "ON task_runs(task_name, started_at DESC);"
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS task_locks (
                    task_name TEXT PRIMARY KEY,
                    lock_owner TEXT NOT NULL,
                    locked_at TEXT NOT NULL
                );
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS system_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    measured_at TEXT NOT NULL,
                    metric_type TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    unit TEXT NOT NULL
                );
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_system_metrics_type_name_time "
                "ON system_metrics(metric_type, metric_name, measured_at DESC);"
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    handler_name TEXT,
                    started_at TEXT,
                    finished_at TEXT,
                    error_message TEXT,
                    related_run_id TEXT,
                    related_ticker TEXT,
                    dedup_key TEXT
                );
                """
            )
            con.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_events_dedup_key "
                "ON events(dedup_key) WHERE dedup_key IS NOT NULL;"
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_status_created "
                "ON events(status, created_at);"
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS runtime_state (
                    runtime_name TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS incidents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dedup_key TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    category TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    signature TEXT NOT NULL,
                    anchor_date TEXT NOT NULL,
                    title TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    occurrence_count INTEGER NOT NULL,
                    related_event_id INTEGER,
                    related_task_run_id INTEGER
                );
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_incidents_status_updated "
                "ON incidents(status, updated_at DESC);"
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS incident_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    runbook_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    dry_run INTEGER NOT NULL,
                    notes TEXT,
                    details_json TEXT NOT NULL,
                    related_event_id INTEGER,
                    related_task_run_id INTEGER
                );
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_incident_actions_incident_created "
                "ON incident_actions(incident_id, created_at DESC);"
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS maintenance_bundles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    window_start TEXT NOT NULL,
                    window_end TEXT NOT NULL,
                    status TEXT NOT NULL,
                    summary_json TEXT NOT NULL,
                    requires_human_approval INTEGER NOT NULL,
                    approved_by TEXT,
                    approved_at TEXT
                );
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_maintenance_bundles_created "
                "ON maintenance_bundles(created_at DESC);"
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS data_inspection_coverage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    anchor_date TEXT NOT NULL,
                    run_id TEXT,
                    name TEXT,
                    has_filing_anchor INTEGER NOT NULL,
                    has_reason_card INTEGER NOT NULL,
                    has_price_snapshot INTEGER NOT NULL,
                    has_required_return_snapshot INTEGER NOT NULL,
                    has_fx_snapshot_if_needed INTEGER NOT NULL,
                    missing_fields_json TEXT NOT NULL,
                    summary_status TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE (ticker, anchor_date)
                );
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_data_inspection_coverage_anchor "
                "ON data_inspection_coverage(anchor_date DESC, ticker ASC);"
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS debug_cases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    debug_case_id TEXT NOT NULL UNIQUE,
                    protocol_version TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    origin TEXT NOT NULL,
                    workflow TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    trigger_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    truth_risk_level TEXT NOT NULL,
                    status TEXT NOT NULL,
                    allowed_retry_action_set_json TEXT NOT NULL,
                    incident_id INTEGER,
                    task_run_id INTEGER,
                    run_id TEXT,
                    filing_id TEXT
                );
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_debug_cases_status_updated "
                "ON debug_cases(status, updated_at DESC);"
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_debug_cases_incident_id "
                "ON debug_cases(incident_id);"
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS debug_case_artifacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    debug_case_id TEXT NOT NULL,
                    artifact_kind TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_debug_case_artifacts_case_kind_created "
                "ON debug_case_artifacts(debug_case_id, artifact_kind, created_at DESC);"
            )

    def create_task_run(
        self,
        *,
        task_name: str,
        status: str,
        params: dict[str, Any],
        trigger_type: str,
        started_at: Optional[datetime] = None,
        error_message: Optional[str] = None,
        related_run_id: Optional[str] = None,
    ) -> int:
        start_value = (started_at or _utc_now()).isoformat()
        with self._connect() as con:
            cur = con.execute(
                """
                INSERT INTO task_runs (
                    task_name, started_at, status, error_message, params_json, trigger_type, related_run_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    task_name,
                    start_value,
                    status,
                    error_message,
                    _dumps(params),
                    trigger_type,
                    related_run_id,
                ),
            )
            return int(cur.lastrowid)

    def finish_task_run(
        self,
        *,
        task_run_id: int,
        status: str,
        error_message: Optional[str] = None,
        related_run_id: Optional[str] = None,
    ) -> None:
        with self._connect() as con:
            con.execute(
                """
                UPDATE task_runs
                SET finished_at = ?, status = ?, error_message = ?, related_run_id = COALESCE(?, related_run_id)
                WHERE id = ?;
                """,
                (_utc_now().isoformat(), status, error_message, related_run_id, task_run_id),
            )

    def acquire_task_lock(self, *, task_name: str, lock_owner: str) -> bool:
        with self._connect() as con:
            try:
                con.execute(
                    "INSERT INTO task_locks (task_name, lock_owner, locked_at) VALUES (?, ?, ?);",
                    (task_name, lock_owner, _utc_now().isoformat()),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def release_task_lock(self, *, task_name: str, lock_owner: str) -> None:
        with self._connect() as con:
            con.execute(
                "DELETE FROM task_locks WHERE task_name = ? AND lock_owner = ?;",
                (task_name, lock_owner),
            )

    def refresh_task_lock(self, *, task_name: str, lock_owner: str) -> None:
        with self._connect() as con:
            con.execute(
                """
                UPDATE task_locks
                SET locked_at = ?
                WHERE task_name = ? AND lock_owner = ?;
                """,
                (_utc_now().isoformat(), task_name, lock_owner),
            )

    def force_release_task_lock(self, *, task_name: str) -> None:
        with self._connect() as con:
            con.execute("DELETE FROM task_locks WHERE task_name = ?;", (task_name,))

    def get_task_lock(self, *, task_name: str) -> Optional[TaskLockRecord]:
        with self._connect() as con:
            row = con.execute(
                """
                SELECT task_name, lock_owner, locked_at
                FROM task_locks
                WHERE task_name = ?
                LIMIT 1;
                """,
                (task_name,),
            ).fetchone()
        if row is None:
            return None
        return TaskLockRecord(
            task_name=str(row[0]),
            lock_owner=str(row[1]),
            locked_at=_to_dt(row[2]) or _utc_now(),
        )

    def get_latest_task_run(self, *, task_name: str) -> Optional[tuple[int, str, datetime]]:
        with self._connect() as con:
            row = con.execute(
                """
                SELECT id, status, started_at
                FROM task_runs
                WHERE task_name = ?
                ORDER BY id DESC
                LIMIT 1;
                """,
                (task_name,),
            ).fetchone()
        if row is None:
            return None
        return (int(row[0]), str(row[1]), _to_dt(row[2]) or _utc_now())

    def get_latest_task_run_record(self, *, task_name: str) -> Optional[TaskRunRecord]:
        with self._connect() as con:
            row = con.execute(
                """
                SELECT
                    id, task_name, started_at, finished_at, status, error_message, params_json,
                    trigger_type, related_run_id
                FROM task_runs
                WHERE task_name = ?
                ORDER BY id DESC
                LIMIT 1;
                """,
                (task_name,),
            ).fetchone()
        if row is None:
            return None
        return TaskRunRecord(
            id=int(row[0]),
            task_name=str(row[1]),
            started_at=_to_dt(row[2]) or _utc_now(),
            finished_at=_to_dt(row[3]),
            status=str(row[4]),
            error_message=None if row[5] is None else str(row[5]),
            params=_loads(row[6]) or {},
            trigger_type=str(row[7]),
            related_run_id=None if row[8] is None else str(row[8]),
        )

    def get_running_task_names(self) -> set[str]:
        with self._connect() as con:
            rows = con.execute(
                """
                SELECT t.task_name
                FROM task_runs t
                JOIN (
                    SELECT task_name, MAX(id) AS latest_id
                    FROM task_runs
                    GROUP BY task_name
                ) latest
                  ON latest.task_name = t.task_name
                 AND latest.latest_id = t.id
                WHERE t.status = 'RUNNING';
                """
            ).fetchall()
        return {str(row[0]) for row in rows if row and row[0]}

    def mark_task_run_failed(
        self,
        *,
        task_run_id: int,
        error_message: str,
        finished_at: Optional[datetime] = None,
    ) -> None:
        with self._connect() as con:
            con.execute(
                """
                UPDATE task_runs
                SET status = 'FAILED',
                    error_message = ?,
                    finished_at = ?
                WHERE id = ?;
                """,
                (error_message, (finished_at or _utc_now()).isoformat(), int(task_run_id)),
            )

    def create_event(
        self,
        *,
        event_type: str,
        payload: dict[str, Any],
        handler_name: Optional[str] = None,
        related_run_id: Optional[str] = None,
        related_ticker: Optional[str] = None,
        dedup_key: Optional[str] = None,
    ) -> Optional[int]:
        with self._connect() as con:
            try:
                cur = con.execute(
                    """
                    INSERT INTO events (
                        event_type, created_at, status, payload_json, handler_name,
                        related_run_id, related_ticker, dedup_key
                    ) VALUES (?, ?, 'PENDING', ?, ?, ?, ?, ?);
                    """,
                    (
                        event_type,
                        _utc_now().isoformat(),
                        _dumps(payload),
                        handler_name,
                        related_run_id,
                        related_ticker,
                        dedup_key,
                    ),
                )
                return int(cur.lastrowid)
            except sqlite3.IntegrityError:
                return None

    def fetch_pending_events(self, *, limit: int = 100) -> list[EventRecord]:
        with self._connect() as con:
            rows = con.execute(
                """
                SELECT id, event_type, status, payload_json, handler_name, created_at
                FROM events
                WHERE status = 'PENDING'
                ORDER BY id ASC
                LIMIT ?;
                """,
                (int(limit),),
            ).fetchall()
        out: list[EventRecord] = []
        for event_id, event_type, status, payload_json, handler_name, created_at in rows:
            out.append(
                EventRecord(
                    id=int(event_id),
                    event_type=str(event_type),
                    status=str(status),
                    payload=_loads(payload_json) or {},
                    handler_name=handler_name,
                    created_at=_to_dt(created_at) or _utc_now(),
                )
            )
        return out

    def mark_event_done(self, *, event_id: int) -> None:
        with self._connect() as con:
            con.execute(
                """
                UPDATE events
                SET status = 'DONE', finished_at = ?, error_message = NULL
                WHERE id = ?;
                """,
                (_utc_now().isoformat(), event_id),
            )

    def mark_event_failed(self, *, event_id: int, error_message: str) -> None:
        with self._connect() as con:
            con.execute(
                """
                UPDATE events
                SET status = 'FAILED', finished_at = ?, error_message = ?
                WHERE id = ?;
                """,
                (_utc_now().isoformat(), error_message, event_id),
            )

    def record_metric(
        self,
        *,
        metric_type: str,
        metric_name: str,
        metric_value: float,
        unit: str,
    ) -> int:
        with self._connect() as con:
            cur = con.execute(
                """
                INSERT INTO system_metrics (measured_at, metric_type, metric_name, metric_value, unit)
                VALUES (?, ?, ?, ?, ?);
                """,
                (_utc_now().isoformat(), metric_type, metric_name, float(metric_value), unit),
            )
            return int(cur.lastrowid)

    def upsert_runtime_state(self, *, runtime_name: str, state: dict[str, Any]) -> None:
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO runtime_state (runtime_name, state_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(runtime_name) DO UPDATE SET
                    state_json = excluded.state_json,
                    updated_at = excluded.updated_at;
                """,
                (runtime_name, _dumps(state), _utc_now().isoformat()),
            )

    def get_runtime_state(self, *, runtime_name: str) -> Optional[RuntimeStateRecord]:
        with self._connect() as con:
            row = con.execute(
                """
                SELECT runtime_name, state_json, updated_at
                FROM runtime_state
                WHERE runtime_name = ?;
                """,
                (runtime_name,),
            ).fetchone()
        if row is None:
            return None
        return RuntimeStateRecord(
            runtime_name=str(row[0]),
            state=_loads(row[1]) or {},
            updated_at=_to_dt(row[2]) or _utc_now(),
        )

    def upsert_incident(
        self,
        *,
        dedup_key: str,
        severity: str,
        category: str,
        scope: str,
        signature: str,
        anchor_date: str,
        title: str,
        details: dict[str, Any],
        status: str = "OPEN",
        related_event_id: Optional[int] = None,
        related_task_run_id: Optional[int] = None,
    ) -> int:
        now = _utc_now().isoformat()
        with self._connect() as con:
            row = con.execute(
                "SELECT id, occurrence_count, first_seen_at FROM incidents WHERE dedup_key = ?;",
                (dedup_key,),
            ).fetchone()
            if row is None:
                cur = con.execute(
                    """
                    INSERT INTO incidents (
                        dedup_key, status, severity, category, scope, signature, anchor_date, title,
                        details_json, first_seen_at, last_seen_at, updated_at, occurrence_count,
                        related_event_id, related_task_run_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        dedup_key,
                        status,
                        severity,
                        category,
                        scope,
                        signature,
                        anchor_date,
                        title,
                        _dumps(details),
                        now,
                        now,
                        now,
                        1,
                        related_event_id,
                        related_task_run_id,
                    ),
                )
                return int(cur.lastrowid)
            incident_id = int(row[0])
            occurrence_count = int(row[1]) + 1
            first_seen_at = str(row[2])
            con.execute(
                """
                UPDATE incidents
                SET status = ?,
                    severity = ?,
                    category = ?,
                    scope = ?,
                    signature = ?,
                    anchor_date = ?,
                    title = ?,
                    details_json = ?,
                    first_seen_at = ?,
                    last_seen_at = ?,
                    updated_at = ?,
                    occurrence_count = ?,
                    related_event_id = COALESCE(?, related_event_id),
                    related_task_run_id = COALESCE(?, related_task_run_id)
                WHERE id = ?;
                """,
                (
                    status,
                    severity,
                    category,
                    scope,
                    signature,
                    anchor_date,
                    title,
                    _dumps(details),
                    first_seen_at,
                    now,
                    now,
                    occurrence_count,
                    related_event_id,
                    related_task_run_id,
                    incident_id,
                ),
            )
            return incident_id

    def fetch_incidents(
        self,
        *,
        status: Optional[str] = None,
        min_occurrence_count: int = 1,
        limit: Optional[int] = None,
    ) -> list[IncidentRecord]:
        query = """
            SELECT
                id, dedup_key, status, severity, category, scope, signature, anchor_date, title,
                details_json, occurrence_count, first_seen_at, last_seen_at, updated_at,
                related_event_id, related_task_run_id
            FROM incidents
            WHERE occurrence_count >= ?
        """
        params: list[Any] = [int(min_occurrence_count)]
        if status is not None:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY updated_at DESC, id DESC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(int(limit))
        query += ";"
        with self._connect() as con:
            rows = con.execute(query, tuple(params)).fetchall()
        out: list[IncidentRecord] = []
        for row in rows:
            out.append(
                IncidentRecord(
                    id=int(row[0]),
                    dedup_key=str(row[1]),
                    status=str(row[2]),
                    severity=str(row[3]),
                    category=str(row[4]),
                    scope=str(row[5]),
                    signature=str(row[6]),
                    anchor_date=str(row[7]),
                    title=str(row[8]),
                    details=_loads(row[9]) or {},
                    occurrence_count=int(row[10]),
                    first_seen_at=_to_dt(row[11]) or _utc_now(),
                    last_seen_at=_to_dt(row[12]) or _utc_now(),
                    updated_at=_to_dt(row[13]) or _utc_now(),
                    related_event_id=None if row[14] is None else int(row[14]),
                    related_task_run_id=None if row[15] is None else int(row[15]),
                )
            )
        return out

    def upsert_data_inspection_coverage(
        self,
        *,
        ticker: str,
        anchor_date: str,
        run_id: Optional[str],
        name: Optional[str],
        has_filing_anchor: bool,
        has_reason_card: bool,
        has_price_snapshot: bool,
        has_required_return_snapshot: bool,
        has_fx_snapshot_if_needed: bool,
        missing_fields: list[str],
        summary_status: str,
        details: dict[str, Any],
    ) -> int:
        now = _utc_now().isoformat()
        with self._connect() as con:
            row = con.execute(
                "SELECT id FROM data_inspection_coverage WHERE ticker = ? AND anchor_date = ?;",
                (ticker, anchor_date),
            ).fetchone()
            if row is None:
                cur = con.execute(
                    """
                    INSERT INTO data_inspection_coverage (
                        ticker, anchor_date, run_id, name,
                        has_filing_anchor, has_reason_card, has_price_snapshot,
                        has_required_return_snapshot, has_fx_snapshot_if_needed,
                        missing_fields_json, summary_status, details_json, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        ticker,
                        anchor_date,
                        run_id,
                        name,
                        1 if has_filing_anchor else 0,
                        1 if has_reason_card else 0,
                        1 if has_price_snapshot else 0,
                        1 if has_required_return_snapshot else 0,
                        1 if has_fx_snapshot_if_needed else 0,
                        _dumps(missing_fields),
                        summary_status,
                        _dumps(details),
                        now,
                    ),
                )
                return int(cur.lastrowid)
            coverage_id = int(row[0])
            con.execute(
                """
                UPDATE data_inspection_coverage
                SET run_id = ?,
                    name = ?,
                    has_filing_anchor = ?,
                    has_reason_card = ?,
                    has_price_snapshot = ?,
                    has_required_return_snapshot = ?,
                    has_fx_snapshot_if_needed = ?,
                    missing_fields_json = ?,
                    summary_status = ?,
                    details_json = ?,
                    updated_at = ?
                WHERE id = ?;
                """,
                (
                    run_id,
                    name,
                    1 if has_filing_anchor else 0,
                    1 if has_reason_card else 0,
                    1 if has_price_snapshot else 0,
                    1 if has_required_return_snapshot else 0,
                    1 if has_fx_snapshot_if_needed else 0,
                    _dumps(missing_fields),
                    summary_status,
                    _dumps(details),
                    now,
                    coverage_id,
                ),
            )
            return coverage_id

    def delete_data_inspection_coverages_except(self, *, anchor_date: str) -> None:
        with self._connect() as con:
            con.execute(
                "DELETE FROM data_inspection_coverage WHERE anchor_date <> ?;",
                (anchor_date,),
            )

    def fetch_data_inspection_coverages(
        self,
        *,
        anchor_date: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[DataInspectionCoverageRecord]:
        query = """
            SELECT
                id, ticker, anchor_date, run_id, name,
                has_filing_anchor, has_reason_card, has_price_snapshot,
                has_required_return_snapshot, has_fx_snapshot_if_needed,
                missing_fields_json, summary_status, details_json, updated_at
            FROM data_inspection_coverage
        """
        params: list[Any] = []
        if anchor_date is not None:
            query += " WHERE anchor_date = ?"
            params.append(anchor_date)
        query += " ORDER BY anchor_date DESC, ticker ASC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(int(limit))
        query += ";"
        with self._connect() as con:
            rows = con.execute(query, tuple(params)).fetchall()
        out: list[DataInspectionCoverageRecord] = []
        for row in rows:
            out.append(
                DataInspectionCoverageRecord(
                    id=int(row[0]),
                    ticker=str(row[1]),
                    anchor_date=str(row[2]),
                    run_id=None if row[3] is None else str(row[3]),
                    name=None if row[4] is None else str(row[4]),
                    has_filing_anchor=bool(row[5]),
                    has_reason_card=bool(row[6]),
                    has_price_snapshot=bool(row[7]),
                    has_required_return_snapshot=bool(row[8]),
                    has_fx_snapshot_if_needed=bool(row[9]),
                    missing_fields=list(_loads(row[10]) or []),
                    summary_status=str(row[11]),
                    details=_loads(row[12]) or {},
                    updated_at=_to_dt(row[13]) or _utc_now(),
                )
            )
        return out

    def create_maintenance_bundle(
        self,
        *,
        window_start: datetime,
        window_end: datetime,
        status: str,
        summary: dict[str, Any],
        requires_human_approval: bool,
    ) -> int:
        with self._connect() as con:
            cur = con.execute(
                """
                INSERT INTO maintenance_bundles (
                    created_at, window_start, window_end, status, summary_json, requires_human_approval
                ) VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    _utc_now().isoformat(),
                    window_start.isoformat(),
                    window_end.isoformat(),
                    status,
                    _dumps(summary),
                    1 if requires_human_approval else 0,
                ),
            )
            return int(cur.lastrowid)

    def mark_maintenance_bundle_approved(self, *, bundle_id: int, approved_by: str) -> None:
        with self._connect() as con:
            con.execute(
                """
                UPDATE maintenance_bundles
                SET status = 'APPROVED',
                    approved_by = ?,
                    approved_at = ?
                WHERE id = ?;
                """,
                (approved_by, _utc_now().isoformat(), int(bundle_id)),
            )

    def fetch_latest_maintenance_bundle(self) -> Optional[MaintenanceBundleRecord]:
        with self._connect() as con:
            row = con.execute(
                """
                SELECT
                    id, created_at, window_start, window_end, status, summary_json,
                    requires_human_approval, approved_by, approved_at
                FROM maintenance_bundles
                ORDER BY id DESC
                LIMIT 1;
                """
            ).fetchone()
        if row is None:
            return None
        return MaintenanceBundleRecord(
            id=int(row[0]),
            created_at=_to_dt(row[1]) or _utc_now(),
            window_start=_to_dt(row[2]) or _utc_now(),
            window_end=_to_dt(row[3]) or _utc_now(),
            status=str(row[4]),
            summary=_loads(row[5]) or {},
            requires_human_approval=bool(int(row[6])),
            approved_by=None if row[7] is None else str(row[7]),
            approved_at=_to_dt(row[8]),
        )
