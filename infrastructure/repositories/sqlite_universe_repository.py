# infrastructure/repositories/sqlite_universe_repository.py
from __future__ import annotations
from typing import List, Dict, Any
import pandas as pd

from application.ports import UniverseRepository, ShortlistUniverseRepository
from infrastructure.persistence.sqlite_filing_store import SqliteFilingStore

class SqliteUniverseRepository(UniverseRepository, ShortlistUniverseRepository):
    def __init__(self, db_path: str = "data/db/filings.sqlite") -> None:
        self._store = SqliteFilingStore(db_path)

    def write_market(self, market: str, df: pd.DataFrame, meta: Dict[str, Any]) -> None:
        """Port: write per-market universe into SQLite."""
        # For simplicity in this first version, we just upsert rows.
        # In a real system, we might want to track market-specific metadata too.
        for _, row in df.iterrows():
            self._store.upsert_universe_ticker(row.to_dict())

    def write_global(self, df: pd.DataFrame, meta: Dict[str, Any]) -> None:
        """Port: write global universe into SQLite."""
        for _, row in df.iterrows():
            self._store.upsert_universe_ticker(row.to_dict())

    def load_tickers(self) -> List[Dict[str, Any]]:
        """Port (ShortlistUniverse): load all tickers from SQLite."""
        return self._store.get_all_universe_tickers()
