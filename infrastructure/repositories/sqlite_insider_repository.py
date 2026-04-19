# infrastructure/repositories/sqlite_insider_repository.py
from __future__ import annotations
from typing import Dict, Any, Optional

from application.screening_service import InsiderRepository
from infrastructure.persistence.sqlite_filing_store import SqliteFilingStore

class SqliteInsiderRepository(InsiderRepository):
    def __init__(self, db_path: str = "data/db/filings.sqlite") -> None:
        self._store = SqliteFilingStore(db_path)

    def load_insiders(self, ticker: str) -> Optional[Dict[str, Any]]:
        return self._store.get_insider(ticker)

    def save_insiders(self, ticker: str, data: Dict[str, Any]) -> None:
        self._store.upsert_insider(ticker, data)
