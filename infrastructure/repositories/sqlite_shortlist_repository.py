# infrastructure/repositories/sqlite_shortlist_repository.py
from __future__ import annotations
from typing import List, Dict, Any, Optional
from pathlib import Path
import pandas as pd

from application.ports import ShortlistRepository as BuildShortlistRepo
from application.screening_service import ShortlistRepository as ScreenShortlistRepo, ShortlistItem
from infrastructure.persistence.sqlite_filing_store import SqliteFilingStore

class SqliteShortlistRepository(BuildShortlistRepo, ScreenShortlistRepo):
    def __init__(self, db_path: str = "data/db/filings.sqlite") -> None:
        self._store = SqliteFilingStore(db_path)

    # --- BuildShortlistRepo Implementation ---
    def save_all(self, df: pd.DataFrame) -> None:
        """
        Store all candidates. For now, we only store the final shortlist in SQLite.
        A more sophisticated version could have an 'all_candidates' table.
        """
        pass

    def save_shortlist(self, df: pd.DataFrame) -> None:
        """Port: persist the filtered shortlist into SQLite."""
        # Clear existing shortlist first? (Optional, based on requirement)
        self._store.clear_shortlist()
        for _, row in df.iterrows():
            ticker = row.get("ticker")
            price = row.get("price")
            currency = row.get("currency")
            if ticker and price is not None:
                self._store.upsert_shortlist_item(str(ticker), float(price), currency)

    def save_meta(self, payload: Dict[str, Any]) -> None:
        """Port: save run metadata."""
        # Could be stored in a 'runs' or 'metadata' table.
        pass

    # --- ScreenShortlistRepo Implementation ---
    def load_shortlist(self, path: Optional[Path] = None) -> List[ShortlistItem]:
        """Port: load shortlist items for screening."""
        rows = self._store.get_shortlist()
        return [
            ShortlistItem(ticker=r["ticker"], last_price=r["price"])
            for r in rows
        ]
