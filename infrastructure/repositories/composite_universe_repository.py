# infrastructure/repositories/composite_universe_repository.py
from __future__ import annotations
from typing import List, Dict, Any
from pathlib import Path
import pandas as pd

from application.ports import UniverseRepository
from infrastructure.repositories.csv_universe_writer_repository import CsvUniverseWriterRepository
from infrastructure.repositories.sqlite_universe_repository import SqliteUniverseRepository

class CompositeUniverseRepository(UniverseRepository):
    """
    Orchestrator that writes to both CSV and SQLite to maintain dual-path persistence.
    """
    def __init__(self, project_root: Path) -> None:
        self.csv_repo = CsvUniverseWriterRepository(project_root)
        # SQLite path is relative to root usually
        self.sqlite_repo = SqliteUniverseRepository(str(project_root / "data" / "db" / "filings.sqlite"))

    def write_market(self, market: str, df: pd.DataFrame, meta: Dict[str, Any]) -> None:
        # 1. Write CSV
        self.csv_repo.write_market(market, df, meta)
        # 2. Write SQLite
        self.sqlite_repo.write_market(market, df, meta)

    def write_global(self, df: pd.DataFrame, meta: Dict[str, Any]) -> None:
        # 1. Write CSV
        self.csv_repo.write_global(df, meta)
        # 2. Write SQLite
        self.sqlite_repo.write_global(df, meta)
