# infrastructure/persistence/sqlite_filing_store.py
from __future__ import annotations

import json
import sqlite3
from typing import Optional, Dict, Any
from dataclasses import asdict
import os

from domain.models.fundamentals import NcavRecord

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

            con.execute(
                """
                CREATE TABLE IF NOT EXISTS universe_tickers (
                    ticker TEXT PRIMARY KEY,
                    name TEXT,
                    country TEXT,
                    mic TEXT,
                    exchange TEXT,
                    sector TEXT,
                    industry TEXT,
                    updated_at TEXT NOT NULL
                );
                """
            )

            con.execute(
                """
                CREATE TABLE IF NOT EXISTS shortlist_items (
                    ticker TEXT PRIMARY KEY,
                    price REAL NOT NULL,
                    currency TEXT,
                    updated_at TEXT NOT NULL
                );
                """
            )

            con.execute(
                """
                CREATE TABLE IF NOT EXISTS insider_snapshots (
                    ticker TEXT PRIMARY KEY,
                    updated_at TEXT NOT NULL,
                    insider_json TEXT NOT NULL
                );
                """
            )

            con.execute(
                """
                CREATE TABLE IF NOT EXISTS screening_snapshots (
                    ticker TEXT,
                    run_date TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    valuation_json TEXT NOT NULL,
                    PRIMARY KEY (ticker, run_date)
                );
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_screening_ticker ON screening_snapshots(ticker);"
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_screening_date ON screening_snapshots(run_date);"
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

    # --- Universe ---
    def get_all_universe_tickers(self) -> List[Dict[str, Any]]:
        with self._connect() as con:
            con.row_factory = sqlite3.Row
            rows = con.execute("SELECT * FROM universe_tickers").fetchall()
            return [dict(r) for r in rows]

    def upsert_universe_ticker(self, data: Dict[str, Any]) -> None:
        from datetime import datetime, timezone
        updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._connect() as con:
            con.execute(
                """
                INSERT OR REPLACE INTO universe_tickers (
                    ticker, name, country, mic, exchange, sector, industry, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data["ticker"],
                    data.get("name"),
                    data.get("country"),
                    data.get("mic"),
                    data.get("exchange"),
                    data.get("sector"),
                    data.get("industry"),
                    updated_at
                )
            )

    # --- Shortlist ---
    def get_shortlist(self) -> List[Dict[str, Any]]:
        with self._connect() as con:
            con.row_factory = sqlite3.Row
            rows = con.execute("SELECT * FROM shortlist_items").fetchall()
            return [dict(r) for r in rows]

    def upsert_shortlist_item(self, ticker: str, price: float, currency: Optional[str] = None) -> None:
        from datetime import datetime, timezone
        updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._connect() as con:
            con.execute(
                "INSERT OR REPLACE INTO shortlist_items (ticker, price, currency, updated_at) VALUES (?, ?, ?, ?)",
                (ticker, price, currency, updated_at)
            )

    def clear_shortlist(self) -> None:
        with self._connect() as con:
            con.execute("DELETE FROM shortlist_items")

    # --- Insiders ---
    def get_insider(self, ticker: str) -> Optional[Dict[str, Any]]:
        with self._connect() as con:
            row = con.execute("SELECT insider_json FROM insider_snapshots WHERE ticker = ?", (ticker,)).fetchone()
            if not row:
                return None
            try:
                return _loads(row[0])
            except Exception:
                return None

    def upsert_insider(self, ticker: str, data: Dict[str, Any]) -> None:
        from datetime import datetime, timezone
        updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._connect() as con:
            con.execute(
                "INSERT OR REPLACE INTO insider_snapshots (ticker, updated_at, insider_json) VALUES (?, ?, ?)",
                (ticker, updated_at, _dumps(data))
            )

    # --- Screening ---
    def upsert_screening_snapshot(self, ticker: str, run_date: str, data: Dict[str, Any]) -> None:
        from datetime import datetime, timezone
        updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._connect() as con:
            con.execute(
                """
                INSERT OR REPLACE INTO screening_snapshots (
                    ticker, run_date, updated_at, valuation_json
                ) VALUES (?, ?, ?, ?)
                """,
                (ticker, run_date, updated_at, _dumps(data))
            )

    def get_latest_screening_snapshots(self) -> List[Dict[str, Any]]:
        """Returns the most recent screening result for each ticker."""
        query = """
            SELECT s.*
            FROM screening_snapshots s
            INNER JOIN (
                SELECT ticker, MAX(run_date) as max_date
                FROM screening_snapshots
                GROUP BY ticker
            ) latest ON s.ticker = latest.ticker AND s.run_date = latest.max_date
        """
        with self._connect() as con:
            con.row_factory = sqlite3.Row
            rows = con.execute(query).fetchall()
            results = []
            for r in rows:
                item = _loads(r["valuation_json"])
                # Add run_date to the result for context
                item["run_date"] = r["run_date"]
                results.append(item)
            return results
