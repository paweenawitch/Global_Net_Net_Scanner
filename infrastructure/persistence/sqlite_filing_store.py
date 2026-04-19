# infrastructure/persistence/sqlite_filing_store.py
from __future__ import annotations

import json
import sqlite3
from typing import Optional, Dict, Any
from dataclasses import asdict
import os

from tools.ncav_cache import NcavRecord

def _dumps(obj: Any) -> str:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)

def _loads(s: str) -> Any:
    return json.loads(s)

class SqliteFilingStore:
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
                CREATE TABLE IF NOT EXISTS ncav_records (
                    ticker TEXT PRIMARY KEY,
                    y_symbol TEXT NOT NULL,
                    latest_fs_date TEXT,
                    currency TEXT,
                    cached_at TEXT NOT NULL,
                    financials_json TEXT NOT NULL
                );
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_ncav_fs_date ON ncav_records(latest_fs_date);"
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_ncav_currency ON ncav_records(currency);"
            )
            
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS sec_core_snapshots (
                    ticker TEXT PRIMARY KEY,
                    updated_at TEXT NOT NULL,
                    core_json TEXT NOT NULL
                );
                """
            )

    def get_ncav_record(self, ticker: str) -> Optional[NcavRecord]:
        with self._connect() as con:
            row = con.execute(
                "SELECT financials_json FROM ncav_records WHERE ticker = ?",
                (ticker,)
            ).fetchone()
            
            if not row:
                return None
            
            try:
                data = _loads(row[0])
                return NcavRecord(**data)
            except Exception as e:
                import logging
                logging.error(f"Error decoding NcavRecord for {ticker}: {e}")
                return None

    def upsert_ncav_record(self, record: NcavRecord) -> None:
        with self._connect() as con:
            con.execute(
                """
                INSERT OR REPLACE INTO ncav_records (
                    ticker, y_symbol, latest_fs_date, currency, cached_at, financials_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.ticker,
                    record.y_symbol,
                    record.statement_date,
                    record.currency,
                    record.cached_at,
                    _dumps(asdict(record))
                )
            )

    def get_sec_core(self, ticker: str) -> Optional[Dict[str, Any]]:
        with self._connect() as con:
            row = con.execute("SELECT core_json FROM sec_core_snapshots WHERE ticker = ?", (ticker,)).fetchone()
            if not row:
                return None
            try:
                return _loads(row[0])
            except Exception:
                return None

    def upsert_sec_core(self, ticker: str, data: Dict[str, Any]) -> None:
        from datetime import datetime, timezone
        updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._connect() as con:
            con.execute(
                "INSERT OR REPLACE INTO sec_core_snapshots (ticker, updated_at, core_json) VALUES (?, ?, ?)",
                (ticker, updated_at, _dumps(data))
            )
