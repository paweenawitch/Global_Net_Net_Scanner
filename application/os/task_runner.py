from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import time
from typing import Optional, Any

from application.os.task_registry import TaskRegistry
from application.os.task_specs import TaskSpec
from infrastructure.persistence.sqlite_os_state_store import SqliteOsStateStore
from infrastructure.scheduler.lock_manager import TaskLockManager

PARALLEL_MARKET_TASKS = {
    "refresh_fundamentals",
    "refresh_prices",
    "refresh_fx_rates",
}
TASK_HEARTBEAT_PARAM_KEY = "__task_heartbeat"
TASK_HEARTBEAT_MIN_INTERVAL_SECONDS = 10.0


def _is_transient_error(exc: Exception) -> bool:
    return isinstance(exc, RuntimeError) and str(exc).startswith("TRANSIENT:")


@dataclass
class TaskRunner:
    registry: TaskRegistry
    store: SqliteOsStateStore
    lock_manager: TaskLockManager
    stale_task_timeout: timedelta = timedelta(minutes=30)

    def run_task(
        self,
        *,
        spec: TaskSpec,
        trigger_type: str = "MANUAL",
        scheduled_at: Optional[datetime] = None,
    ) -> int:
        current = scheduled_at or datetime.now(timezone.utc)
        self._recover_stale_running_tasks(now=current)

        if spec.task_name not in PARALLEL_MARKET_TASKS:
            running_task_names = self.store.get_running_task_names()
            if running_task_names:
                return self.store.create_task_run(
                    task_name=spec.task_name,
                    status="SKIPPED",
                    params=spec.params,
                    trigger_type=trigger_type,
                    started_at=scheduled_at,
                    error_message=f"SKIPPED_CONCURRENT_TASK:{','.join(sorted(running_task_names))}",
                )

        acquired_lock = True
        if not spec.allow_overlap:
            acquired_lock = self.lock_manager.acquire(task_name=spec.task_name)
            if not acquired_lock:
                self._recover_stale_task_if_needed(task_name=spec.task_name, now=current)
                acquired_lock = self.lock_manager.acquire(task_name=spec.task_name)
            if not acquired_lock:
                return self.store.create_task_run(
                    task_name=spec.task_name,
                    status="SKIPPED",
                    params=spec.params,
                    trigger_type=trigger_type,
                    started_at=scheduled_at,
                    error_message="SKIPPED_OVERLAP",
                )

        task_run_id = self.store.create_task_run(
            task_name=spec.task_name,
            status="RUNNING",
            params=spec.params,
            trigger_type=trigger_type,
            started_at=scheduled_at,
        )

        try:
            fn = self.registry.get(spec.pipeline)
            params_for_run = dict(spec.params)
            if not spec.allow_overlap:
                last_heartbeat_at = 0.0

                def task_heartbeat() -> None:
                    nonlocal last_heartbeat_at
                    now_monotonic = time.monotonic()
                    if now_monotonic - last_heartbeat_at < TASK_HEARTBEAT_MIN_INTERVAL_SECONDS:
                        return
                    self.lock_manager.refresh(task_name=spec.task_name)
                    last_heartbeat_at = now_monotonic

                params_for_run[TASK_HEARTBEAT_PARAM_KEY] = task_heartbeat

            attempts = 0
            while True:
                attempts += 1
                try:
                    result = fn(params_for_run)
                    related_run_id = (
                        None if result is None else result.get("related_run_id")
                    )
                    self.store.finish_task_run(
                        task_run_id=task_run_id,
                        status="SUCCESS",
                        related_run_id=related_run_id,
                    )
                    return task_run_id
                except Exception as exc:
                    if attempts <= spec.max_retries and _is_transient_error(exc):
                        continue
                    self.store.finish_task_run(
                        task_run_id=task_run_id,
                        status="FAILED",
                        error_message=str(exc),
                    )
                    return task_run_id
        finally:
            if not spec.allow_overlap and acquired_lock:
                self.lock_manager.release(task_name=spec.task_name)

    def _recover_stale_running_tasks(self, *, now: datetime) -> None:
        for task_name in sorted(self.store.get_running_task_names()):
            self._recover_stale_task_if_needed(task_name=task_name, now=now)

    def _recover_stale_task_if_needed(self, *, task_name: str, now: datetime) -> None:
        lock = self.store.get_task_lock(task_name=task_name)
        latest = self.store.get_latest_task_run(task_name=task_name)
        if latest is None:
            return
        task_run_id, status, started_at = latest
        if status != "RUNNING":
            if lock is not None:
                self.store.force_release_task_lock(task_name=task_name)
            return
        stale_before = now - self.stale_task_timeout
        lock_is_fresh = lock is not None and lock.locked_at > stale_before
        if lock_is_fresh or started_at > stale_before:
            return
        self.store.mark_task_run_failed(
            task_run_id=task_run_id,
            error_message="FAILED_STALE_RUN",
            finished_at=now,
        )
        self.store.force_release_task_lock(task_name=task_name)
