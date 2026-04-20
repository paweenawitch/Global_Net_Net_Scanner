# infrastructure/sources/yahoo_source.py
from __future__ import annotations
import logging
import random
import time
import threading
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple, Callable

import pandas as pd
import requests
import yfinance as yf

from domain.models.fundamentals import NcavRecord

LOGGER = logging.getLogger("infrastructure.sources.yahoo")

# ---------- Rate limit & retry ----------
class TokenBucket:
    def __init__(self, rps: float):
        self.dt = 1.0 / max(0.1, rps)
        self.last_t = 0.0
        self.lock = threading.Lock()

    def wait(self):
        with self.lock:
            now = time.perf_counter()
            wait = self.last_t + self.dt - now
            if wait > 0:
                time.sleep(wait * (1.0 + random.uniform(-0.1, 0.1)))
            self.last_t = time.perf_counter()

# Centralized pacing for Yahoo JSON/HTML and yfinance
_JSON_BUCKET = TokenBucket(0.4)
_INFO_BUCKET = TokenBucket(0.4)

def yahoo_retry(fn: Callable[[], Any], attempts=4, base=1.2) -> Any:
    last = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:
            last = e
            s = str(e).lower()
            if not any(t in s for t in ["401","403","429","500","502","503","504","timed out"]):
                break
            time.sleep(min(12.0, base * (2 ** i) * (1 + random.uniform(-0.2, 0.2))))
    raise last if last else RuntimeError("Yahoo fetch error")

# ---------- Helpers ----------
def to_yahoo_symbol(sym: str) -> str:
    s = (sym or "").strip().upper()
    if not s: return s
    if s.endswith(".US"): return s[:-3]               # AAPL.US -> AAPL
    if s.endswith(".JP"): return s[:-3] + ".T"        # 7203.JP -> 7203.T
    if s.endswith(".HK"): return s                    # 0005.HK -> 0005.HK
    if s.endswith(".UK"): return s[:-3] + ".L"        # PSH.UK -> PSH.L
    if s.endswith(".PL"): return s[:-3] + ".WA"       # KGH.PL -> KGH.WA
    if s.endswith(".FR"): return s[:-3] + ".PA"       # AI.FR  -> AI.PA
    if s.endswith(".TH"): return s[:-3] + ".BK"       # PTTEP.TH -> PTTEP.BK
    return s

def _f(x) -> Optional[float]:
    try:
        if x is None or pd.isna(x): return None
        return float(x)
    except Exception:
        return None

def _norm_date(x) -> Optional[str]:
    try:
        return pd.to_datetime(x).date().isoformat()
    except Exception:
        return None

# ---------- Extraction Logic ----------
def _pick_row(df: pd.DataFrame, names: List[str]) -> Optional[pd.Series]:
    if df is None or df.empty: return None
    def norm(s: str) -> str:
        return re.sub(r"[^a-z0-9]", "", s.strip().lower())
    
    idxmap = {norm(str(i)): i for i in df.index}
    synonyms = {
        "totalcurrentassets": ["totalcurrentassets", "currentassets", "currentassetstotal", "totalcurrentasset"],
        "totalliabilities": ["totalliabilities", "totalliab", "liabilitiestotal", "totalliabliabilities", "totalliabs"],
        "totalcurrentliabilities": ["totalcurrentliabilities", "currentliabilities", "totalcurrentliab", "currentliab"],
        "totalnoncurrentliabilities": ["totalnoncurrentliabilities", "noncurrentliabilities", "totalnoncurrliab"],
        "totalassets": ["totalassets", "totalasset"],
        "workingcapital": ["workingcapital"],
        "sharesoutstanding": ["sharesoutstanding", "totalcommonsharesoutstanding", "basicsharesoutstanding"],
    }
    
    expanded = []
    for n in names:
        n0 = norm(n)
        expanded.append(n0)
        for key, arr in synonyms.items():
            if n0 == key or n0 in arr: expanded += arr
            
    for n0 in expanded:
        if n0 in idxmap: return df.loc[idxmap[n0]]
    for n0 in expanded:
        for k, orig in idxmap.items():
            if n0 in k: return df.loc[orig]
    return None

def _extract_values(df: pd.DataFrame, col: Any) -> Dict[str, Optional[float]]:
    ca_s  = _pick_row(df, ["Total Current Assets","Current Assets"])
    ta_s  = _pick_row(df, ["Total Assets"])
    nca_s = _pick_row(df, ["Non Current Assets","Total Non Current Assets"])
    tl_s  = _pick_row(df, ["Total Liab","Total Liabilities"])
    cl_s  = _pick_row(df, ["Total Current Liabilities","Current Liabilities"])
    ncl_s = _pick_row(df, ["Total Non-Current Liabilities","Non Current Liabilities"])
    wc_s  = _pick_row(df, ["Working Capital"])

    ta  = _f(ta_s.get(col))  if ta_s  is not None else None
    nca = _f(nca_s.get(col)) if nca_s is not None else None
    tl  = _f(tl_s.get(col))  if tl_s  is not None else None
    cl  = _f(cl_s.get(col))  if cl_s  is not None else None
    ncl = _f(ncl_s.get(col)) if ncl_s is not None else None
    wc  = _f(wc_s.get(col))  if wc_s  is not None else None
    ca  = _f(ca_s.get(col))  if ca_s  is not None else None

    # Derivations
    if cl is None and tl is not None and ncl is not None: cl = tl - ncl
    if ca is None and wc is not None and cl is not None: ca = wc + cl
    if ca is None and ta is not None and nca is not None: ca = ta - nca
    if tl is None and cl is not None and ncl is not None: tl = cl + ncl

    return {"assets_current": ca, "liab_total": tl}

def _frame_to_periods(df_bal: pd.DataFrame, ccy: str, limit: int) -> List[Dict[str, Any]]:
    periods: List[Dict[str, Any]] = []
    if df_bal is None or df_bal.empty: return []
    
    cols = list(df_bal.columns)[:limit]
    for col in cols:
        dt = _norm_date(col)
        vals = _extract_values(df_bal, col)
        periods.append({
            "date": dt,
            "currency": ccy,
            "balance": {k: {"val": v, "unit": ccy} for k, v in vals.items() if v is not None}
        })
    return sorted(periods, key=lambda p: (p.get("date") or ""), reverse=True)

class YahooSource:
    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "Mozilla/5.0", "Accept": "application/json"})

    def fetch_full_filings(self, house_ticker: str) -> Dict[str, Any]:
        """Fetch all periods and build a core filings object (similar to USSecSource)."""
        y_sym = to_yahoo_symbol(house_ticker)
        LOGGER.info(f"Fetching full Yahoo filings for {house_ticker} ({y_sym})")
        T = yf.Ticker(y_sym)

        # 1. Statements
        _INFO_BUCKET.wait()
        try: bs_a = yahoo_retry(lambda: T.balance_sheet)
        except Exception: bs_a = pd.DataFrame()
        _INFO_BUCKET.wait()
        try: bs_q = yahoo_retry(lambda: T.quarterly_balance_sheet)
        except Exception: bs_q = pd.DataFrame()

        # 2. Info / Meta
        _INFO_BUCKET.wait()
        try:
            info = yahoo_retry(lambda: T.info or {})
            ccy = str(info.get("financialCurrency") or info.get("currency") or "USD").upper()
        except Exception:
            info = {}
            ccy = "USD"

        a_periods = _frame_to_periods(bs_a, ccy, limit=6)
        q_periods = _frame_to_periods(bs_q, ccy, limit=4)
        both = sorted(a_periods + q_periods, key=lambda p: (p.get("date") or ""), reverse=True)

        # 3. Shares mapping
        shares_out = self._fetch_shares(T)
        shares_series = self._fetch_shares_series(y_sym, T)
        both, latest_shares, _ = self._map_shares_to_periods(both, shares_series, shares_out)

        # 4. Derived latest
        latest = {}
        if both:
            p = both[0]
            b = p.get("balance") or {}
            ca = (b.get("assets_current") or {}).get("val")
            tl = (b.get("liab_total") or {}).get("val")
            sh = (b.get("shares_out") or {}).get("val")
            ncav = (ca - tl) if (ca is not None and tl is not None) else None
            latest = {
                "date": p["date"],
                "ncav": ncav,
                "ncav_ps": (ncav / sh) if (ncav and sh) else None,
            }

        return {
            "meta": {
                "schema_version": "core.v1",
                "ticker": house_ticker,
                "name": info.get("longName"),
                "country_iso": (info.get("country") or "").upper(),
                "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
                "source": "yfinance",
                "y_symbol": y_sym
            },
            "financials": {
                "annual": {"periods": a_periods},
                "quarterly": {"periods": q_periods},
            },
            "derived": {"latest": latest}
        }

    def fetch_ncav_record(self, house_ticker: str) -> NcavRecord:
        y_sym = to_yahoo_symbol(house_ticker)
        LOGGER.info(f"Fetching Yahoo fundamentals for {house_ticker} ({y_sym})")
        
        T = yf.Ticker(y_sym)
        
        # 1. Shares Outstanding
        shares_out = self._fetch_shares(T)
        
        # 2. Balance Sheets
        _INFO_BUCKET.wait()
        try: bs_a = yahoo_retry(lambda: T.balance_sheet)
        except Exception: bs_a = pd.DataFrame()
        
        _INFO_BUCKET.wait()
        try: bs_q = yahoo_retry(lambda: T.quarterly_balance_sheet)
        except Exception: bs_q = pd.DataFrame()
        
        # 3. Currency
        _INFO_BUCKET.wait()
        try:
            info = yahoo_retry(lambda: T.info or {})
            ccy = str(info.get("financialCurrency") or info.get("currency") or "USD").upper()
        except Exception:
            ccy = "USD"
            
        # 4. Selection Logic
        a_periods = _frame_to_periods(bs_a, ccy, limit=6)
        q_periods = _frame_to_periods(bs_q, ccy, limit=4)
        both = sorted(a_periods + q_periods, key=lambda p: (p.get("date") or ""), reverse=True)
        
        info_shares = shares_out
        shares_series = self._fetch_shares_series(y_sym, T)
        both, latest_shares, _ = self._map_shares_to_periods(both, shares_series, info_shares)
        
        sel_date, comp, src = self._select_latest_viable_from_periods(both, max_age_days=730)
        
        ca = comp.get("assets_current")
        tl = comp.get("liab_total")
        ncav = (ca - tl) if (ca is not None and tl is not None) else None
        
        period_shares = comp.get("shares_out")
        ncav_ps = (ncav / period_shares) if (ncav is not None and period_shares and period_shares > 0) else None
        
        data_age_days = None
        if sel_date:
            try:
                data_age_days = (datetime.now(timezone.utc).date() - pd.to_datetime(sel_date).date()).days
            except Exception: pass
            
        import hashlib
        sig_input = f"{sel_date}|{ccy}|{ca}|{tl}|{period_shares}"
        sig = hashlib.sha256(sig_input.encode()).hexdigest()[:16]
        
        return NcavRecord(
            ticker=house_ticker,
            y_symbol=y_sym,
            statement_date=sel_date,
            currency=ccy,
            assets_current=ca,
            liab_total=tl,
            ncav=ncav,
            shares_out=period_shares,
            ncav_ps=ncav_ps,
            source="yahoo",
            cached_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            statement_sig=sig,
            data_age_days=data_age_days,
            fs_source=src,
            fs_selected_col=sel_date,
            note=None if sel_date else "no viable FS column found"
        )

    def _fetch_shares(self, T: yf.Ticker) -> Optional[float]:
        try:
            _INFO_BUCKET.wait()
            info = yahoo_retry(lambda: T.info or {})
            so = info.get("sharesOutstanding")
            if so and float(so) > 0: return float(so)
        except Exception: pass
        return None

    def _fetch_shares_series(self, y_symbol: str, T: yf.Ticker) -> Optional[pd.Series]:
        try:
            _JSON_BUCKET.wait()
            url = f"https://query2.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/{y_symbol}"
            params = {
                "type": "trailingSharesOutstanding,sharesOutstanding,impliedSharesOutstanding,annualBasicAverageShares,annualDilutedAverageShares",
                "period1": "0", "period2": str(int(time.time())), "padTimeSeries": "true",
            }
            resp = yahoo_retry(lambda: self._session.get(url, params=params, timeout=20))
            if resp.status_code == 200:
                js = resp.json()
                res = (js.get("timeseries") or {}).get("result") or []
                pts = []
                for bucket in res:
                    for key, arr in bucket.items():
                        if "share" not in key.lower() or not isinstance(arr, list): continue
                        for it in arr:
                            dt = _norm_date(it.get("asOfDate") or it.get("timestamp"))
                            v = it.get("reportedValue") or it.get("value")
                            if isinstance(v, dict): v = v.get("raw")
                            if dt and v: pts.append((pd.to_datetime(dt), float(v)))
                if pts:
                    pts.sort(key=lambda x: x[0])
                    s = pd.Series([v for _, v in pts], index=pd.DatetimeIndex([d for d, _ in pts]))
                    return s[~s.index.duplicated(keep="last")]
        except Exception: pass

        try:
            _INFO_BUCKET.wait()
            s = yahoo_retry(lambda: T.get_shares_full())
            if s is not None and not s.empty: return s
        except Exception: pass
        return None

    def _map_shares_to_periods(self, periods: List[Dict[str, Any]], series: Optional[pd.Series], info_shares: Optional[float]):
        latest_shares = info_shares
        if series is not None and not series.empty:
            latest_shares = float(series.iloc[-1])
            
        for p in periods:
            dt = pd.to_datetime(p["date"])
            val = None
            if series is not None and not series.empty:
                before = series.loc[:dt]
                after = series.loc[dt:]
                cand = []
                if not before.empty: cand.append((abs((dt - before.index[-1]).days), before.index[-1]))
                if not after.empty: cand.append((abs((after.index[0] - dt).days), after.index[0]))
                cand.sort(key=lambda x: x[0])
                if cand and cand[0][0] <= 90: val = float(series.loc[cand[0][1]])
                elif not before.empty: val = float(before.iloc[-1])
                else: val = float(series.iloc[0])
            
            if val is None: val = info_shares
            if val:
                p["balance"]["shares_out"] = {"val": val, "unit": "shares"}
        
        return periods, latest_shares, {}

    def _select_latest_viable_from_periods(self, periods: List[Dict[str, Any]], max_age_days: int = 730):
        cutoff = datetime.now(timezone.utc).date() - timedelta(days=max_age_days)
        for p in periods:
            dt = pd.to_datetime(p["date"]).date()
            if dt < cutoff: continue
            
            b = p.get("balance") or {}
            ca = (b.get("assets_current") or {}).get("val")
            tl = (b.get("liab_total") or {}).get("val")
            so = (b.get("shares_out") or {}).get("val")
            
            if ca is not None and tl is not None and so and so > 0:
                return p["date"], {"assets_current": ca, "liab_total": tl, "shares_out": so}, "mixed"
        
        return None, {}, None

    def fetch_insiders(self, house_ticker: str) -> Dict[str, Any]:
        """Schema-only stub for now."""
        return {
            "as_of": datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z",
            "buys_count": 0,
            "sells_count": 0,
            "buys_shares": 0.0,
            "sells_shares": 0.0,
            "net_shares": 0.0,
            "signal": "Neutral",
            "status": "disabled",
            "status_reason": "insider_fetch_disabled",
            "source": "disabled",
            "insiders_percent_held": None,
            "insiders_percent_held_source": None,
        }
