# infrastructure/sources/yahoo_fx_provider.py

from __future__ import annotations
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import yfinance as yf

from application.ports import FxProvider

logger = logging.getLogger(__name__)


class YahooFxProvider(FxProvider):
    """
    Returns USD per 1 unit of CCY (usd_per_ccy).
    Uses yfinance as the primary data source with JSON caching.

    Logic for CNY/CNH:
    - Always attempts to fetch both USDCNY=X and USDCNH=X.
    - If one is missing, it falls back to the other.
    """

    def __init__(self, cache_file: Path, ttl: timedelta | None = None) -> None:
        self._cache_file = cache_file
        self._ttl = ttl or timedelta(hours=24)

    def _load_cache(self) -> Optional[Dict[str, float]]:
        if not self._cache_file.exists():
            return None
        try:
            mtime = datetime.fromtimestamp(self._cache_file.stat().st_mtime, tz=timezone.utc)
            if datetime.now(timezone.utc) - mtime > self._ttl:
                return None
            data = json.loads(self._cache_file.read_text(encoding="utf-8"))
            return data.get("rates")
        except Exception as e:
            logger.warning(f"Failed to load FX cache: {e}")
            return None

    def _save_cache(self, rates: Dict[str, float]) -> None:
        try:
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "rates": rates,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "source": "yfinance",
            }
            self._cache_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to save FX cache: {e}")

    def usd_per_ccy(self, currencies: List[str] | None = None) -> Dict[str, float]:
        # 1. Try cache
        cached = self._load_cache()
        if cached:
            # If we requested specific ones, verify they are in cache.
            # Otherwise, just return what we have.
            if currencies:
                missing = [c for c in currencies if c.upper() not in cached]
                if not missing:
                    return cached
            else:
                return cached

        # 2. Fetch fresh
        rates = self._fetch_latest(currencies or ["JPY", "HKD", "CNY", "CNH", "THB", "GBP", "EUR"])
        if rates and len(rates) > 1: # >1 because USD is always there
            self._save_cache(rates)
            return rates
            
        return rates or {"USD": 1.0}

    def _fetch_latest(self, currencies: List[str]) -> Dict[str, float]:
        # Normalize and ensure CNY/CNH are included as requested by user
        requested_codes = {(c or "USD").upper() for c in currencies}
        if "CNY" in requested_codes or "CNH" in requested_codes:
            requested_codes.add("CNY")
            requested_codes.add("CNH")

        out: Dict[str, float] = {"USD": 1.0}
        pairs = sorted([f"USD{c}=X" for c in requested_codes if c != "USD"])
        if not pairs:
            return out

        try:
            # Fetch 7 days of daily data to get at least one valid Close
            df = yf.download(
                pairs,
                period="7d",
                interval="1d",
                progress=False,
                threads=True,
                group_by="ticker",
            )
        except Exception as e:
            logger.error(f"Yahoo FX download failed: {e}")
            return out

        def get_last_val(data: pd.DataFrame) -> Optional[float]:
            if data is None or data.empty or "Close" not in data.columns:
                return None
            valid = data["Close"].dropna()
            if valid.empty:
                return None
            val = float(valid.iloc[-1])
            return val if val > 0 else None

        # Process results
        for p in pairs:
            ccy = p[3:-2] # USDJPY=X -> JPY
            try:
                # yf.download returns MultiIndex if multiple pairs, SingleIndex if 1
                ticker_df = df[p] if len(pairs) > 1 else df
                val_per_usd = get_last_val(ticker_df)
                if val_per_usd:
                    out[ccy] = 1.0 / val_per_usd
            except Exception:
                continue

        # 3. Handle CNY/CNH Aliasing/Fallback as requested
        # "Use CNY first, fallback to CNH if we can't find CNY."
        if "CNY" not in out and "CNH" in out:
            out["CNY"] = out["CNH"]
            logger.info("CNY missing, aliasing to CNH rate")
        elif "CNH" not in out and "CNY" in out:
            out["CNH"] = out["CNY"]
            logger.info("CNH missing, aliasing to CNY rate")

        return out
