# infrastructure/persistence/sqlite_market_snapshot_store.py
from __future__ import annotations

import json
import sqlite3
import os
from typing import Optional, Dict, List
from application.ports import PricePoint

class SqliteMarketSnapshotStore:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._ensure_tables()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self._db_path)
        con.execute("PRAGMA journal_mode=WAL;")
        con.execute("PRAGMA synchronous=NORMAL;")
        return con

    def _ensure_tables(self) -> None:
        with self._connect() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS price_snapshots (
                    symbol TEXT PRIMARY KEY,
                    price REAL,
                    asof TEXT,
                    currency TEXT,
                    updated_at TEXT NOT NULL
                );
                """
            )

    def get_price(self, symbol: str) -> Optional[PricePoint]:
        with self._connect() as con:
            row = con.execute(
                "SELECT symbol, price, asof, currency, updated_at FROM price_snapshots WHERE symbol = ?",
                (symbol,)
            ).fetchone()
            if not row:
                return None
            return PricePoint(
                symbol=row[0],
                price=row[1],
                asof=row[2],
                currency=row[3],
                updated_at=row[4]
            )

    def get_many_prices(self, symbols: List[str]) -> Dict[str, PricePoint]:
        if not symbols:
            return {}
            
        out = {}
        with self._connect() as con:
            chunk_size = 900
            for i in range(0, len(symbols), chunk_size):
                chunk = symbols[i:i+chunk_size]
                placeholders = ",".join("?" for _ in chunk)
                rows = con.execute(
                    f"SELECT symbol, price, asof, currency, updated_at FROM price_snapshots WHERE symbol IN ({placeholders})",
                    chunk
                ).fetchall()
                
                for row in rows:
                    out[row[0]] = PricePoint(
                        symbol=row[0],
                        price=row[1],
                        asof=row[2],
                        currency=row[3],
                        updated_at=row[4]
                    )
        return out

    def upsert_many_prices(self, points: List[PricePoint]) -> None:
        if not points:
            return

        rows = [
            (p.symbol, p.price, p.asof, p.currency, p.updated_at)
            for p in points
        ]
        
        with self._connect() as con:
            con.executemany(
                """
                INSERT OR REPLACE INTO price_snapshots (
                    symbol, price, asof, currency, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                rows
            )
