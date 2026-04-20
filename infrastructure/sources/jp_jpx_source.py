import io, re, requests, json
from pathlib import Path
from urllib.parse import urljoin
import pandas as pd

from application.ports import TickerSource

CANDIDATE_PAGES = [
    "https://www.jpx.co.jp/markets/equities/ss-reg/",
    "https://www.jpx.co.jp/english/markets/equities/ss-reg/",
    "https://www.jpx.co.jp/english/markets/statistics-equities/misc/01.html",
]
XLS_PAT = re.compile(r"Primary_Listing_Markets\.xls$", re.IGNORECASE)
CODE_PAT = re.compile(r"^\d{4}$")
DUMB_JPX_CSV = "https://dumbstockapi.com/stock?format=csv&exchanges=JPX"

class JPJpxSource(TickerSource):
    market_code = "JP"
    source_label = "JPX primary list"

    def __init__(self, project_root: Path) -> None:
        self.root = Path(project_root)
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "Mozilla/5.0"})

    def fetch(self) -> pd.DataFrame:
        """Ported from tools/build_universe/jp_jpx.py"""
        # A) Crawl for XLS
        try:
            xls_url = self._find_primary_xls()
            if xls_url:
                r = self._session.get(xls_url, timeout=30)
                if r.ok: return self._parse_primary_xls(r.content)
        except Exception as e: print(f"[JP] XLS crawl failed: {e}")

        # B) Fallback to DumbStockAPI
        try:
            r = self._session.get(DUMB_JPX_CSV, timeout=30)
            if r.ok: return self._parse_dumb_csv(r.content)
        except Exception as e: print(f"[JP] Dumb fallback failed: {e}")

        return pd.DataFrame(columns=["ticker_base","ticker","name","country","mic"])

    def _find_primary_xls(self) -> str | None:
        for page in CANDIDATE_PAGES:
            try:
                r = self._session.get(page, timeout=30)
                if not r.ok: continue
                for h in re.findall(r'href="([^"]+)"', r.text):
                    if XLS_PAT.search(h): return urljoin(page, h)
            except Exception: pass
        return None

    def _parse_primary_xls(self, content: bytes) -> pd.DataFrame:
        df = pd.read_excel(io.BytesIO(content))
        code_col = name_col = None
        for c in df.columns:
            k = str(c).strip().lower()
            if ("code" in k and "stock" in k) or k in ("code", "securities code", "証券コード"): code_col = c
            if ("name" in k and "stock" in k) or ("name" in k) or ("銘柄" in k): name_col = c
        if code_col is None or name_col is None: code_col, name_col = list(df.columns)[:2]
        
        out = df[[code_col, name_col]].copy(); out.columns = ["ticker_base","name"]
        out["ticker_base"] = out["ticker_base"].astype(str).str.extract(r"(\d{4})")[0]
        out = out.dropna(subset=["ticker_base","name"]); out = out[out["ticker_base"].str.match(CODE_PAT)]
        out["ticker"] = out["ticker_base"] + ".JP"; out["country"] = "JP"; out["mic"] = "XJPX"
        return out.drop_duplicates("ticker_base").reset_index(drop=True)

    def _parse_dumb_csv(self, content: bytes) -> pd.DataFrame:
        df = pd.read_csv(io.BytesIO(content))
        if not {"ticker","name","exchange"}.issubset(df.columns): return pd.DataFrame()
        df = df[df["exchange"].astype(str).str.upper() == "JPX"].copy()
        df["ticker_base"] = df["ticker"].astype(str).str.extract(r"(\d{4})")[0]
        df = df.dropna(subset=["ticker_base"])
        df["ticker"] = df["ticker_base"] + ".JP"; df["country"] = "JP"; df["mic"] = "XJPX"
        return df[["ticker_base","ticker","name","country","mic"]].drop_duplicates("ticker_base").reset_index(drop=True)
