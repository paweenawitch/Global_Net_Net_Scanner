# infrastructure/sources/yahoo_fx_provider.py

from __future__ import annotations
from typing import Dict, List, Optional
import pandas as pd
import yfinance as yf

from application.ports import FxProvider


class YahooFxProvider(FxProvider):
    """
    Returns USD per 1 unit of CCY (usd_per_ccy).

    We fetch USD as base:
      USDJPY=X  -> JPY per 1 USD
      usd_per_ccy["JPY"] = 1 / (JPY per USD)

    This makes conversion consistent:
      value_in_usd = value_in_ccy * usd_per_ccy[ccy]
    """
    FX_BASE = "USD"

    @staticmethod
    def _pairs(codes: List[str]) -> List[str]:
        codes_u = sorted({(c or "USD").upper() for c in codes})
        out: List[str] = []
        for c in codes_u:
            if c == "USD":
                continue
            out.append(f"USD{c}=X")
        return out

    def usd_per_ccy(self, currencies: List[str]) -> Dict[str, float]:
        out: Dict[str, float] = {"USD": 1.0}
        pairs = self._pairs(currencies)
        if not pairs:
            return out

        try:
            df = yf.download(
                pairs,
                period="7d",
                interval="1d",
                progress=False,
                group_by="ticker",
                threads=True,
            )
        except Exception:
            df = None

        def last_close(d: pd.DataFrame) -> Optional[float]:
            if d is None or d.empty or "Close" not in d.columns:
                return None
            d = d.sort_index()
            try:
                v = float(d.iloc[-1]["Close"])
                return v if pd.notna(v) else None
            except Exception:
                return None

        if isinstance(df, pd.DataFrame) and isinstance(df.columns, pd.MultiIndex):
            for p in pairs:
                ccy = p.replace("=X", "")[3:]  # USDJPY=X -> JPY
                try:
                    ccy_per_usd = last_close(df[p])
                    if ccy_per_usd and ccy_per_usd > 0:
                        out[ccy] = 1.0 / ccy_per_usd
                except Exception:
                    pass

        elif isinstance(df, pd.DataFrame) and len(pairs) == 1:
            p = pairs[0]
            ccy = p.replace("=X", "")[3:]
            ccy_per_usd = last_close(df)
            if ccy_per_usd and ccy_per_usd > 0:
                out[ccy] = 1.0 / ccy_per_usd

        out.setdefault("USD", 1.0)
        return out
