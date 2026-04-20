from __future__ import annotations

import sqlite3
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Optional
from datetime import datetime, timedelta

from domain.maintenance.data_inspection_rules import build_dedup_key, validate_finding
from domain.models.data_inspection_finding import DataInspectionFinding
from infrastructure.persistence.sqlite_os_state_store import (
    SqliteOsStateStore,
    DataInspectionCoverageRecord,
)

_log = logging.getLogger("walter.inspection")

@dataclass(frozen=True, slots=True)
class DataInspectionSummary:
    findings_created_or_updated: int
    coverage_rows_upserted: int
    by_signature: dict[str, int]

class DataInspectionService:
    def __init__(self, filings_db: str, market_db: str, state_store: SqliteOsStateStore):
        self.filings_db = filings_db
        self.market_db = market_db
        self.state_store = state_store

    def run_all(self, limit: Optional[int] = None) -> DataInspectionSummary:
        findings_total = 0
        coverage_rows = 0
        by_signature: dict[str, int] = {}

        # 1. Update Coverage for all universe tickers
        coverage_rows = self._update_coverage(limit)

        # 2. Run Detectors
        detectors = [
            self._detect_missing_prices,
            self._detect_stale_filings,
            self._detect_missing_fx,
        ]

        for detector in detectors:
            findings = detector(limit)
            for f in findings:
                validate_finding(f)
                self.state_store.upsert_incident(
                    dedup_key=build_dedup_key(f),
                    severity=f.severity,
                    category=f.category,
                    scope=f.scope,
                    signature=f.signature,
                    anchor_date=f.anchor_date,
                    title=f.title,
                    details={**f.details, "candidate_action": f.candidate_action},
                )
                findings_total += 1
                by_signature[f.signature] = by_signature.get(f.signature, 0) + 1

        return DataInspectionSummary(
            findings_created_or_updated=findings_total,
            coverage_rows_upserted=coverage_rows,
            by_signature=by_signature
        )

    def _update_coverage(self, limit: Optional[int]) -> int:
        # Resolve today as anchor
        anchor_date = datetime.now().strftime("%Y-%m-%d")
        count = 0
        
        with sqlite3.connect(self.filings_db) as con:
            con.row_factory = sqlite3.Row
            query = """
                SELECT u.ticker, u.name, n.latest_fs_date, n.currency 
                FROM universe_tickers u
                LEFT JOIN ncav_records n ON n.ticker = u.ticker
            """
            if limit:
                query += f" LIMIT {limit}"
            
            tickers = con.execute(query).fetchall()
            
            for t in tickers:
                ticker = t["ticker"]
                
                # Check for filing
                ncav = con.execute("SELECT ticker FROM ncav_records WHERE ticker = ?", (ticker,)).fetchone()
                # Check for price
                price = False
                with sqlite3.connect(self.market_db) as mcon:
                    prow = mcon.execute("SELECT ticker FROM price_snapshots WHERE ticker = ?", (ticker,)).fetchone()
                    price = prow is not None
                
                # Check for FX (simple check if currency is USD or if we have it?)
                # This is a bit complex for a simple query, we'll mark it based on presence of FX later
                has_fx = (t["currency"] == "USD" or t["currency"] is None) # Placeholder
                
                missing = []
                if not ncav: missing.append("filing")
                if not price: missing.append("price")
                
                status = "COMPLETE" if not missing else "PARTIAL"
                if len(missing) > 1: status = "MISSING_CRITICAL"

                self.state_store.upsert_data_inspection_coverage(
                    ticker=ticker,
                    anchor_date=anchor_date,
                    run_id=None,
                    name=t["name"],
                    has_filing_anchor=ncav is not None,
                    has_reason_card=False, # Roadmap
                    has_price_snapshot=price,
                    has_required_return_snapshot=True, # Roadmap
                    has_fx_snapshot_if_needed=has_fx,
                    missing_fields=missing,
                    summary_status=status,
                    details={"valuation_currency": t["currency"]}
                )
                count += 1
        
        return count

    def _detect_missing_prices(self, limit: Optional[int]) -> List[DataInspectionFinding]:
        findings = []
        anchor_date = datetime.now().strftime("%Y-%m-%d")
        
        with sqlite3.connect(self.filings_db) as con:
            query = """
                SELECT u.ticker 
                FROM universe_tickers u
                LEFT JOIN ncav_records n ON n.ticker = u.ticker
                WHERE n.ticker IS NOT NULL
            """
            tickers = [r[0] for r in con.execute(query).fetchall()]
            
            with sqlite3.connect(self.market_db) as mcon:
                for ticker in tickers:
                    prow = mcon.execute("SELECT ticker FROM price_snapshots WHERE ticker = ?", (ticker,)).fetchone()
                    if not prow:
                        findings.append(DataInspectionFinding(
                            category="DATA_INTEGRITY",
                            severity="HIGH",
                            scope=ticker,
                            signature="missing_price_snapshot",
                            anchor_date=anchor_date,
                            title=f"Missing price for {ticker}",
                            details={"ticker": ticker},
                            candidate_action="refresh_prices"
                        ))
                        if limit and len(findings) >= limit: break
        return findings

    def _detect_stale_filings(self, limit: Optional[int]) -> List[DataInspectionFinding]:
        findings = []
        anchor_date = datetime.now().strftime("%Y-%m-%d")
        threshold = (datetime.now() - timedelta(days=500)).strftime("%Y-%m-%d")

        with sqlite3.connect(self.filings_db) as con:
            con.row_factory = sqlite3.Row
            rows = con.execute(
                "SELECT ticker, latest_fs_date FROM ncav_records WHERE latest_fs_date < ?", 
                (threshold,)
            ).fetchall()
            
            for r in rows:
                findings.append(DataInspectionFinding(
                    category="DATA_INTEGRITY",
                    severity="MEDIUM",
                    scope=r["ticker"],
                    signature="stale_filing",
                    anchor_date=anchor_date,
                    title=f"Filing for {r['ticker']} is very old ({r['latest_fs_date']})",
                    details={"ticker": r["ticker"], "fs_date": r["latest_fs_date"]},
                    candidate_action="refresh_fundamentals"
                ))
                if limit and len(findings) >= limit: break
        return findings

    def _detect_missing_fx(self, limit: Optional[int]) -> List[DataInspectionFinding]:
        # Placeholder for FX inspection
        return []
