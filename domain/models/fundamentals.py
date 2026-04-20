# domain/models/fundamentals.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass
class NcavRecord:
    ticker: str
    y_symbol: str
    statement_date: Optional[str]          # selected date (within 2y) or None
    currency: str                          # FS currency
    assets_current: Optional[float]
    liab_total: Optional[float]
    ncav: Optional[float]
    shares_out: Optional[float]
    ncav_ps: Optional[float]
    source: str
    cached_at: str
    statement_sig: str
    data_age_days: Optional[int] = None    # staleness
    fs_source: Optional[str] = None        # "annual" or "quarterly"
    fs_selected_col: Optional[str] = None  # column date used
    note: Optional[str] = None             # reason when selection fails
