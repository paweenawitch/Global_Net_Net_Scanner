import io, re, requests, json
from pathlib import Path
import pandas as pd

from application.ports import TickerSource

SET_XLS_EN = "https://www.set.or.th/dat/eod/listedcompany/static/listedCompanies_en_US.xls"
DENY_NAME_TOKENS = (
    "ETF","FUND","TRUST","REIT","WARRANT","DW","DERIVATIVE",
    "BOND","NOTE","DEBENTURE","PREF","PREFERRED","RIGHT","WTS"
)

class THSetSource(TickerSource):
    market_code = "TH"
    source_label = "SET official list"

    def __init__(self, project_root: Path) -> None:
        self.root = Path(project_root)
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "Mozilla/5.0"})

    def fetch(self) -> pd.DataFrame:
        """Fetch TH ticker universe from SET official list."""
        try:
            r = self._session.get(SET_XLS_EN, timeout=60, headers={"User-Agent":"NetNet-Global/1.0"})
            r.raise_for_status()
            return self._parse_set_xls(r.content)
        except Exception as e:
            print(f"[TH] Official XLS failed: {e}")
            return pd.DataFrame(columns=["ticker_base","ticker","name","country","mic"])

    def _parse_set_xls(self, content: bytes) -> pd.DataFrame:
        """Handle SET's HTML-disguised-as-XLS or real XLS."""
        head = content.lstrip()[:20].lower()
        if head.startswith(b"<") or b"<table" in head:
            html = content.decode("utf-8", errors="ignore")
            tables = pd.read_html(io.StringIO(html))
            df = tables[0].copy()
        else:
            df = pd.read_excel(io.BytesIO(content), engine="xlrd")

        # Normalize columns
        cols = {str(c).strip().lower(): c for c in df.columns}
        def find_col(candidates):
            for k in candidates:
                for ck, orig in cols.items():
                    if k in ck: return orig
            return None

        sym_col = find_col(["symbol", "ticker", "ชื่อย่อ"])
        name_col = find_col(["company name", "security name", "ชื่อบริษัท"])
        
        if sym_col is None: sym_col = df.columns[0]
        if name_col is None: name_col = df.columns[1] if len(df.columns) > 1 else sym_col

        out = df[[sym_col, name_col]].copy()
        out.columns = ["ticker_base", "name"]
        out["ticker_base"] = out["ticker_base"].astype(str).str.strip().str.upper()
        out = out.dropna(subset=["ticker_base"])
        out = out[out["ticker_base"].str.len() > 0]
        
        # Filter for common stock
        mask = out["name"].apply(lambda n: not any(tok in str(n).upper() for tok in DENY_NAME_TOKENS))
        out = out[mask].copy()

        out["ticker"] = out["ticker_base"] + ".TH"
        out["country"] = "TH"
        out["mic"] = "XBKK"
        return out[["ticker_base","ticker","name","country","mic"]].reset_index(drop=True)
