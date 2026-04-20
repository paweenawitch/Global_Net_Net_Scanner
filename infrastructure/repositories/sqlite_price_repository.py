# infrastructure/repositories/sqlite_price_repository.py
from __future__ import annotations

import os
from typing import Dict, Optional, List

from application.ports import PricePoint, PriceRepository
from infrastructure.persistence.sqlite_market_snapshot_store import SqliteMarketSnapshotStore


class SqlitePriceRepository(PriceRepository):
    def __init__(self, db_path: str = "data/db/market_snapshots.sqlite") -> None:
        self._store = SqliteMarketSnapshotStore(db_path)

    def get_cached(self, symbol: str) -> Optional[PricePoint]:
        return self._store.get_price(symbol)

    def get_many_cached(self, symbols: List[str]) -> Dict[str, PricePoint]:
        return self._store.get_many_prices(symbols)

    def put_many(self, points: List[PricePoint]) -> None:
        self._store.upsert_many_prices(points)
