import io, re, requests, json
from pathlib import Path
import pandas as pd

from application.ports import TickerSource

SEHK_XLS = "https://www.hkex.com.hk/eng/services/trading/securities/securitieslists/ListOfSecurities.xlsx"
NUM4 = re.compile(r"^\d{4}$")

class HKHKEXSource(TickerSource):
    market_code = "HK"
    source_label = "HKEX official list"

    def __init__(self, project_root: Path) -> None:
        self.root = Path(project_root)
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "Mozilla/5.0"})

    def fetch(self) -> pd.DataFrame:
        """Fetch HK ticker universe from HKEX official list."""
        try:
            r = self._session.get(SEHK_XLS, timeout=60, headers={"User-Agent":"NetNet-Global/1.0"})
            r.raise_for_status()
            return self._parse_official_xls(r.content)
        except Exception as e:
            print(f"[HK] Official XLS failed: {e}")
            return pd.DataFrame(columns=["ticker_base","ticker","name","country","mic"])

    def _parse_official_xls(self, content: bytes) -> pd.DataFrame:
        xl = pd.ExcelFile(io.BytesIO(content), engine="openpyxl")
        tables = []
        for sheet in xl.sheet_names:
            t = self._sheet_to_table(xl, sheet)
            if t is not None and not t.empty: tables.append(t)
        
        if not tables: return pd.DataFrame(columns=["ticker_base","ticker","name","country","mic"])
        
        df = pd.concat(tables, ignore_index=True)
        # Normalize code to 4 digits (e.g., 5 -> 0005)
        df["ticker_base"] = (df["Stock Code"].astype(str).str.extract(r"(\d+)")[0]
                             .fillna("0").astype(int).astype(str).str.zfill(4))
        df = df[df["ticker_base"].str.match(NUM4)]
        
        # Identity logic: only keep common equity
        mask = df.apply(lambda r: self._is_equity(r.get("Category",""), r.get("Sub-Category","")), axis=1)
        base = df[mask].drop_duplicates(subset=["ticker_base"]).copy()
        
        base["ticker"] = base["ticker_base"] + ".HK"
        base["country"] = "HK"
        base["mic"] = "XHKG"
        base = base.rename(columns={"Name of Securities": "name"})
        return base[["ticker_base","ticker","name","country","mic"]].reset_index(drop=True)

    def _sheet_to_table(self, xl: pd.ExcelFile, sheet_name: str) -> pd.DataFrame | None:
        try:
            raw = xl.parse(sheet_name, header=None, dtype=object)
            found = self._find_header(raw)
            if not found: return None
            hdr_i, idx_map = found
            data = raw.iloc[hdr_i+1:].reset_index(drop=True).copy()
            data.columns = [idx_map.get(j) for j in range(raw.shape[1])]
            return data[[c for c in data.columns if c is not None]].dropna(how="all")
        except Exception: return None

    def _find_header(self, df: pd.DataFrame):
        for i in range(min(50, len(df))):
            mapping = self._canonize_header(df.iloc[i].tolist())
            if len(set(mapping.values())) >= 2 and "Stock Code" in mapping.values():
                return i, mapping
        return None

    def _canonize_header(self, cells) -> dict[int,str]:
        SYN = {
            "stock code": "Stock Code", "stockcode": "Stock Code", "股份代號": "Stock Code",
            "name of securities": "Name of Securities", "english short name": "Name of Securities", "證券名稱": "Name of Securities",
            "category": "Category", "類別": "Category",
            "sub-category": "Sub-Category", "次類別": "Sub-Category"
        }
        out = {}
        for j, raw in enumerate(cells):
            if raw is None: continue
            s = str(raw).strip().lower()
            key = SYN.get(s) or SYN.get(re.sub(r"[\(\)（）].*$","", s).strip())
            if key: out[j] = key
        return out

    def _is_equity(self, cat: str, subcat: str) -> bool:
        deny = {"cbbc","warrant","bond","debt","note",
                "etf","fund","trust","reit","stapled","structured"}
        c = str(cat).lower()
        s = str(subcat).lower()
        if any(t in c for t in deny) or any(t in s for t in deny): return False
        return True
