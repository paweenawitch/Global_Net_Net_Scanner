from __future__ import annotations

from dataclasses import dataclass
from infrastructure.persistence.sqlite_os_state_store import SqliteOsStateStore


@dataclass
class TaskLockManager:
    store: SqliteOsStateStore
    lock_owner: str

    def acquire(self, *, task_name: str) -> bool:
        return self.store.acquire_task_lock(task_name=task_name, lock_owner=self.lock_owner)

    def release(self, *, task_name: str) -> None:
        self.store.release_task_lock(task_name=task_name, lock_owner=self.lock_owner)

    def refresh(self, *, task_name: str) -> None:
        # Note: SqliteOsStateStore needs this method if we want to support heartbeats
        try:
            self.store.refresh_task_lock(task_name=task_name, lock_owner=self.lock_owner)
        except AttributeError:
            pass # Or implement it
