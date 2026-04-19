# infrastructure/repositories/sec_core_fs_repository.py
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any, Optional

from infrastructure.persistence.sqlite_filing_store import SqliteFilingStore

class SecCoreFsRepository:
    def __init__(self, db_path: str = "data/db/filings.sqlite") -> None:
        self._store = SqliteFilingStore(db_path)

    def load_core(self, ticker: str) -> Optional[Dict[str, Any]]:
        return self._store.get_sec_core(ticker)
        
    def save_core(self, ticker: str, data: Dict[str, Any]) -> None:
        self._store.upsert_sec_core(ticker, data)
