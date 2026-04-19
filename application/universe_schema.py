# application/universe_schema.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import pandas as pd


@dataclass(frozen=True, slots=True)
class UniverseSchema:
    """
    Universe Schema Contract (single source of truth)

    Universe = tradable instruments list (NOT companies).
    This table exists to define WHAT we will attempt to screen later.

    Required columns:
      - ticker: instrument key (e.g. "AAPL.US")
      - ticker_base: base symbol (e.g. "AAPL")
      - name: display name
      - country: ISO-ish (e.g. "US")

    Recommended (optional but strongly preferred):
      - instrument_id: stable instrument identifier (default = ticker)
      - cik: US entity hint (zero-padded string), optional
      - primary_listing_mic: MIC code or "UNKNOWN" if not known

    Back-compat:
      - If a source uses "mic", we map it to primary_listing_mic.
    """

    # Canonical columns (extras allowed)
    required = ("ticker", "ticker_base", "name", "country")
    recommended = ("instrument_id", "cik", "primary_listing_mic")

    @classmethod
    def canonical_columns(cls) -> tuple[str, ...]:
        return cls.recommended + cls.required

    @classmethod
    def universe_policy(cls) -> Dict[str, Any]:
        # “Nice-to-have A”: policy stamp for reproducibility + reporting
        return {
            "definition": "tradable_instruments_not_companies",
            "instrument_type": "common_equity_only_best_effort",
            "excludes": ["spac", "units", "warrants", "rights", "trust"],  # best-effort filters by source
            "listing_scope": ["primary_listings_best_effort"],
            "currency_policy": "native_currency_at_source",
            "notes": [
                "MIC may be UNKNOWN depending on source capabilities.",
                "CIK is preserved as entity hint for US instruments when available.",
            ],
        }


def _norm_str(x) -> Optional[str]:
    if x is None:
        return None
    try:
        if pd.isna(x):
            return None
    except Exception:
        pass
    s = str(x).strip()
    if s == "" or s.lower() == "nan":
        return None
    return s


def normalize_universe_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize ANY source DF into canonical universe schema.
    Extras are dropped by default (keep universe tight + stable).
    """
    cols = UniverseSchema.canonical_columns()

    if df is None or df.empty:
        return pd.DataFrame(columns=list(cols))

    out = df.copy()

    # Back-compat mapping
    if "primary_listing_mic" not in out.columns and "mic" in out.columns:
        out["primary_listing_mic"] = out["mic"]

    # Ensure required columns exist
    for c in UniverseSchema.required:
        if c not in out.columns:
            out[c] = None

    # Ensure recommended columns exist
    if "instrument_id" not in out.columns:
        out["instrument_id"] = out.get("ticker")
    if "cik" not in out.columns:
        out["cik"] = None
    if "primary_listing_mic" not in out.columns:
        out["primary_listing_mic"] = "UNKNOWN"

    # Normalize strings
    out["ticker"] = out["ticker"].map(_norm_str)
    out["ticker_base"] = out["ticker_base"].map(_norm_str)
    out["name"] = out["name"].map(_norm_str)
    out["country"] = out["country"].map(_norm_str)

    out["ticker_base"] = out["ticker_base"].astype(str).str.strip().str.upper()

    # instrument_id defaults to ticker if missing
    out["instrument_id"] = out["instrument_id"].map(_norm_str)
    out.loc[out["instrument_id"].isna(), "instrument_id"] = out["ticker"]

    # Normalize CIK to zero-padded string if possible
    def _norm_cik(x) -> Optional[str]:
        s = _norm_str(x)
        if s is None:
            return None
        # tolerate float/int-ish inputs
        try:
            n = int(float(s))
            if n <= 0:
                return None
            return str(n).zfill(10)
        except Exception:
            digits = "".join(ch for ch in s if ch.isdigit())
            return digits.zfill(10) if digits else None

    out["cik"] = out["cik"].map(_norm_cik)

    # MIC placeholder
    out["primary_listing_mic"] = out["primary_listing_mic"].map(_norm_str)
    out["primary_listing_mic"] = out["primary_listing_mic"].fillna("UNKNOWN")

    # Enforce minimal viability
    out = out.dropna(subset=["ticker", "ticker_base"]).drop_duplicates(subset=["ticker"], keep="first")

    # Keep canonical order
    out = out[list(cols)].reset_index(drop=True)
    return out


def universe_qc(df: pd.DataFrame) -> Dict[str, Any]:
    """
    “Nice-to-have B”: cheap QC checks for CLI/service reporting.
    No domain involvement. Deterministic.
    """
    if df is None or df.empty:
        return {
            "rows": 0,
            "unique_tickers": 0,
            "duplicate_tickers": 0,
            "missing_name": 0,
            "missing_country": 0,
            "missing_primary_listing_mic": 0,
            "missing_instrument_id": 0,
            "missing_cik_us": 0,
        }

    rows = int(len(df))
    unique_tickers = int(df["ticker"].nunique())
    duplicate_tickers = int(rows - unique_tickers)

    missing_name = int(df["name"].isna().sum())
    missing_country = int(df["country"].isna().sum())
    missing_mic = int((df["primary_listing_mic"].isna() | (df["primary_listing_mic"] == "UNKNOWN")).sum())
    missing_instrument_id = int(df["instrument_id"].isna().sum())

    # US-only CIK expectation (best-effort; not a hard failure globally)
    is_us = (df["country"] == "US")
    missing_cik_us = int(df.loc[is_us, "cik"].isna().sum()) if "cik" in df.columns else int(is_us.sum())

    return {
        "rows": rows,
        "unique_tickers": unique_tickers,
        "duplicate_tickers": duplicate_tickers,
        "missing_name": missing_name,
        "missing_country": missing_country,
        "missing_primary_listing_mic_or_unknown": missing_mic,
        "missing_instrument_id": missing_instrument_id,
        "missing_cik_us": missing_cik_us,
    }
