## infrastructure/repositories/ncav_cache_repository.py
from __future__ import annotations
import logging
from typing import Optional, Dict, Any
from application.ports import FundamentalsRepository

from domain.models.fundamentals import NcavRecord
from infrastructure.persistence.sqlite_filing_store import SqliteFilingStore
from infrastructure.sources.yahoo_source import YahooSource

_log = logging.getLogger("shortlist.fundamentals")

class NcavCacheRepository(FundamentalsRepository):
    def __init__(self, db_path: str = "data/db/filings.sqlite") -> None:
        self._store = SqliteFilingStore(db_path)
        self._source = YahooSource()

    def get_or_update(self, house_ticker: str, fetch_timeout: int) -> Dict[str, Any]:
        _log.debug("fetching fundamentals (update) for %s", house_ticker)
        
        # 1. Try Loading cached
        cached = self._store.get_ncav_record(house_ticker)
        
        # 2. Fetch fresh
        try:
            # We use YahooSource which handles its own timeouts/retries
            fresh = self._source.fetch_ncav_record(house_ticker)
            
            # 3. Check if statement has changed (sig comparison)
            if cached and cached.statement_sig == fresh.statement_sig:
                # Update cached_at timestamp but keep old record to avoid churn?
                # Actually, SqliteFilingStore handles upsert_ncav_record.
                # If sig is same, we still want to update 'cached_at' in the DB.
                cached.cached_at = fresh.cached_at
                self._store.upsert_ncav_record(cached)
                return self._to_dict(cached)
            
            self._store.upsert_ncav_record(fresh)
            return self._to_dict(fresh)
        except Exception as e:
            _log.error("Failed to fetch fresh fundamentals for %s: %s", house_ticker, e)
            if cached:
                return self._to_dict(cached)
            # Return a "not found" or "error" record
            return self._to_dict(NcavRecord(
                ticker=house_ticker, y_symbol="", statement_date=None, currency="",
                assets_current=None, liab_total=None, ncav=None, shares_out=None, ncav_ps=None,
                source="error", cached_at="", statement_sig="", note=str(e)
            ))

    def get_cached(self, house_ticker: str) -> Optional[Dict[str, Any]]:
        rec = self._store.get_ncav_record(house_ticker)
        if rec is None:
            _log.debug("cache miss: %s", house_ticker)
            return None
        _log.debug("cache hit: %s (date=%s)", house_ticker, rec.statement_date)
        return self._to_dict(rec)

    def _to_dict(self, rec: NcavRecord) -> Dict[str, Any]:
        from dataclasses import asdict
        d = asdict(rec)
        return {
            "ticker": d.get("ticker"),
            "y_symbol": d.get("y_symbol"),
            "fs_date": d.get("statement_date"),
            "currency": d.get("currency"),
            "assets_current": d.get("assets_current"),
            "liab_total": d.get("liab_total"),
            "ncav": d.get("ncav"),
            "shares_out": d.get("shares_out"),
            "ncav_ps": d.get("ncav_ps"),
            "data_age_days": d.get("data_age_days"),
            "fs_source": d.get("fs_source"),
            "fs_selected_col": d.get("fs_selected_col"),
            "note": d.get("note"),
        }
