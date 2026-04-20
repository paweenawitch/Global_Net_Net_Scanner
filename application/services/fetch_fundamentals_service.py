# application/services/fetch_fundamentals_service.py

import json
import logging
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed

from infrastructure.sources.us_sec_source import USSecSource
from infrastructure.sources.yahoo_source import YahooSource

LOGGER = logging.getLogger("application.services.fetch_fundamentals")

class FetchFundamentalsService:
    """
    Use Case: Orchestrate the fetching and local caching of financial fundamentals.
    Replaces the legacy subprocess-based tools/ scripts.
    """

    def __init__(self, project_root: Path):
        self.root = Path(project_root)
        self.core_dir = self.root / "cache" / "sec_core"
        self.ins_dir = self.root / "cache" / "sec_insider"
        self.core_dir.mkdir(parents=True, exist_ok=True)
        self.ins_dir.mkdir(parents=True, exist_ok=True)

        self.us_source = USSecSource(self.root)
        self.yahoo_source = YahooSource()

    def run_all(
        self,
        tickers: List[str],
        skip_days: int = 7,
        force: bool = False,
        max_workers: int = 4,
        shard: int = 1,
        of: int = 1,
        verbose: bool = False
    ) -> Dict[str, Any]:
        """
        Fetch and cache fundamentals for a list of tickers.
        Supports sharding and parallel execution.
        """
        # 1. Sharding
        if of > 1:
            tickers = [t for i, t in enumerate(tickers) if (i % of) == (shard - 1)]
            LOGGER.info(f"Sharding enabled: Shard {shard}/{of}. Processing {len(tickers)} tickers.")

        # 2. Parallel Fetch
        results = {"ok": 0, "error": 0, "skipped": 0}
        fresh_cutoff = datetime.now(timezone.utc) - timedelta(days=skip_days)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            fut_map = {
                executor.submit(self._fetch_single, ticker, fresh_cutoff, force, verbose): ticker
                for ticker in tickers
            }

            for fut in as_completed(fut_map):
                ticker = fut_map[fut]
                try:
                    status = fut.result()
                    results[status] = results.get(status, 0) + 1
                except Exception as e:
                    LOGGER.error(f"Failed {ticker}: {e}")
                    results["error"] += 1

        LOGGER.info(f"Run complete. {results}")
        return results

    def _fetch_single(
        self, 
        ticker: str, 
        fresh_cutoff: datetime, 
        force: bool, 
        verbose: bool
    ) -> str:
        """Process a single ticker: check cache, fetch, and save."""
        core_path = self.core_dir / f"{ticker}_core.json"
        
        # 1. Freshness check
        if not force and core_path.exists():
            mtime = datetime.fromtimestamp(core_path.stat().st_mtime, timezone.utc)
            if mtime >= fresh_cutoff:
                if verbose: LOGGER.info(f"[SKIP] {ticker} is fresh (mtime={mtime.isoformat()})")
                return "skipped"

        # 2. Source Selection
        is_us = ticker.upper().endswith(".US")
        
        try:
            if is_us:
                # US Source (SEC)
                core_obj = self.us_source.fetch_core(ticker)
                ins_obj = self.us_source.fetch_insiders(ticker)
            else:
                # Non-US Source (Yahoo)
                core_obj = self.yahoo_source.fetch_full_filings(ticker)
                ins_obj = self.yahoo_source.fetch_insiders(ticker) # Currently a stub

            # 3. Save
            self._save_json(core_path, core_obj)
            
            ins_path = self.ins_dir / f"{ticker}.json"
            self._save_json(ins_path, ins_obj)

            if verbose: LOGGER.info(f"[OK] {ticker} fetched and cached.")
            return "ok"

        except Exception as e:
            LOGGER.error(f"Error fetching {ticker}: {e}")
            return "error"

    def _save_json(self, path: Path, obj: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
