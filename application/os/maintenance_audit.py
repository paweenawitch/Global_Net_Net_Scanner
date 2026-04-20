from __future__ import annotations

import os
import sqlite3
import logging
from dataclasses import dataclass
from typing import Any, Dict, List
from datetime import datetime, timezone

from infrastructure.persistence.sqlite_os_state_store import SqliteOsStateStore

_log = logging.getLogger("walter.audit")

@dataclass(frozen=True, slots=True)
class MaintenanceAuditSummary:
    db_stats: Dict[str, Any]
    zombie_locks_cleared: int
    stale_tasks_flagged: int

class MaintenanceAuditService:
    def __init__(self, state_store: SqliteOsStateStore, db_paths: List[str]):
        self.state_store = state_store
        self.db_paths = db_paths

    def run_audit(self) -> MaintenanceAuditSummary:
        _log.info("Starting maintenance audit")
        
        # 1. DB Stats
        db_stats = self._gather_db_stats()
        
        # 2. Clear Zombie Locks
        cleared_locks = self._clear_zombie_locks()
        
        # 3. Flag Stale Tasks
        stale_tasks = self._flag_stale_tasks()
        
        return MaintenanceAuditSummary(
            db_stats=db_stats,
            zombie_locks_cleared=cleared_locks,
            stale_tasks_flagged=stale_tasks
        )

    def _gather_db_stats(self) -> Dict[str, Any]:
        stats = {}
        for path in self.db_paths:
            if os.path.exists(path):
                size_mb = os.path.getsize(path) / (1024 * 1024)
                stats[os.path.basename(path)] = f"{size_mb:.2f} MB"
        return stats

    def _clear_zombie_locks(self) -> int:
        # If a lock is older than 2 hours, it's likely a zombie
        threshold = datetime.now(timezone.utc) - timedelta(hours=2)
        # We need a method in state_store to fetch locks or we check them individually
        # For now, let's just log and skip unless we find specific locked tasks
        return 0

    def _flag_stale_tasks(self) -> int:
        # Logic to find tasks marked as RUNNING but with no heartbeat
        return 0
