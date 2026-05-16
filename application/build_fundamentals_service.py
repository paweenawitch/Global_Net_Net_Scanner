# application/build_fundamentals_service.py
from __future__ import annotations
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from domain.models.fundamentals import NcavRecord
from infrastructure.persistence.sqlite_filing_store import SqliteFilingStore
from infrastructure.sources.yahoo_source import YahooSource
from infrastructure.sources.us_sec_source import USSecSource

LOGGER = logging.getLogger("application.fundamentals")

class BuildFundamentalsService:
    def __init__(self, project_root: Path, db_path: str = "data/db/filings.sqlite") -> None:
        self.root = project_root
        self._store = SqliteFilingStore(str(self.root / db_path))
        self._yahoo = YahooSource()
        self._sec = USSecSource(self.root)

    def update_ncav_cache(self, tickers: List[str], force: bool = False) -> None:
        """Update NcavRecords (Step 2 fundamentals) for a list of tickers."""
        for ticker in tickers:
            try:
                # Check cache
                cached = self._store.get_ncav_record(ticker)
                if cached and not force:
                    # check staleness if needed, but for now we follow the 'force' flag
                    LOGGER.debug(f"Skipping {ticker}, already cached.")
                    continue

                # Fetch fresh from the best available source.
                fresh = self._yahoo.fetch_ncav_record(ticker)
                self._store.upsert_ncav_record(fresh)
                LOGGER.info(f"Updated NCAV record for {ticker}")
            except Exception as e:
                LOGGER.error(f"Error updating NCAV for {ticker}: {e}")

    def update_sec_core_cache(self, tickers: List[str], force: bool = False) -> None:
        """Update SEC core snapshots (Step 3 fundamentals) for US tickers."""
        for ticker in tickers:
            if not ticker.upper().endswith(".US"):
                continue
                
            try:
                # Check cache
                if not force and self._store.get_sec_core(ticker):
                    continue
                
                # Fetch fresh from SEC
                core = self._sec.fetch_core(ticker)
                self._store.upsert_sec_core(ticker, core)
                LOGGER.info(f"Updated SEC core for {ticker}")
            except Exception as e:
                LOGGER.error(f"Error updating SEC core for {ticker}: {e}")

    def update_non_us_core_cache(self, tickers: List[str], force: bool = False) -> None:
        """Update core snapshots for non-US tickers using Yahoo."""
        # For non-US, 'core' is often just the same as NcavRecord or a similar JSON blob.
        pass

    def update_insider_cache(self, tickers: List[str], force: bool = False) -> None:
        """Update insider signals for US tickers using SEC (Form 4)."""
        for ticker in tickers:
            if not ticker.upper().endswith(".US"):
                continue
                
            try:
                if not force and self._store.get_insider(ticker):
                    continue
                
                # Fetch fresh from SEC (Form 4 parsing)
                data = self._sec.fetch_insiders(ticker)
                self._store.upsert_insider(ticker, data)
                LOGGER.info(f"Updated insider data for {ticker}")
            except Exception as e:
                LOGGER.error(f"Error updating insider for {ticker}: {e}")
