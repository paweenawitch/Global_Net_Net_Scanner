from __future__ import annotations
from dataclasses import asdict
from typing import List, Dict, Any

from domain.models.valuation_result import ValuationResult
from application.ports import ScreeningResultRepository
from infrastructure.persistence.sqlite_filing_store import SqliteFilingStore

class SqliteScreeningRepository(ScreeningResultRepository):
    def __init__(self, db_path: str = "data/db/filings.sqlite") -> None:
        self._store = SqliteFilingStore(db_path)

    def save_results(self, results: List[ValuationResult], run_date: str) -> None:
        """Persist valuation results into the SQLite store."""
        for res in results:
            # We convert the ValuationResult to a dict (which handles red_flags/green_flags lists)
            data = asdict(res)
            self._store.upsert_screening_snapshot(
                ticker=res.ticker,
                run_date=run_date,
                data=data
            )

    def get_latest_results(self) -> List[ValuationResult]:
        """Load the most recent ValuationResults from the store."""
        rows = self._store.get_latest_screening_snapshots()
        results = []
        for row in rows:
            # Reconstruct ValuationResult objects
            # Note: We need to handle the 'run_date' which we added in get_latest_screening_snapshots
            # But ValuationResult doesn't have a run_date field. 
            # We can either strip it or pass it as metadata if we had a wrapper.
            # For now, we'll strip it to match the dataclass.
            clean_row = {k: v for k, v in row.items() if k != "run_date"}
            results.append(ValuationResult(**clean_row))
        return results
