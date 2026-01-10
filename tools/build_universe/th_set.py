from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import io, json, os, re

import requests
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "tickers"
DATA.mkdir(parents=True, exist_ok=True)

OUT = DATA / "th_full.csv"
OUT_META = DATA / "th_full.meta.json"

# Official SET static roster (legacy .xls)
SET_XLS_EN = "https://www.set.or.th/dat/eod/listedcompany/static/listedCompanies_en_US.xls"
SET_XLS_TH = "https://www.set.or.th/dat/eod/listedcompany/static/listedCompanies_th_TH.xls"

# Optional: let you override with your own URL (csv/xls/xlsx)
ENV_URL = os.environ.get("TH_PRIMARY_URL", "").strip()

DENY_NAME_TOKENS = (
    "ETF","FUND","TRUST","REIT","WARRANT","DW","DERIVATIVE",
    "BOND","NOTE","DEBENTURE","PREF","PREFERRED","RIGHT","WTS"
)

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def _write_meta(source: str, rows: int) -> None:
    OUT_META.write_text(json.dumps({
        "source": source,
        "generated_at": _now_iso(),
        "rows": int(rows),
        "path": str(OUT),
    }, indent=2), encoding="utf-8")

def _write(df: pd.DataFrame, source: str) -> pd.DataFrame:
    if df is None or df.empty:
        out = pd.DataFrame(columns=["ticker_base","ticker","name","country","mic","board"])
        out.to_csv(OUT, index=False)
        _write_meta(source, 0)
        print(f"✅ TH: 0 rows ({source}) → {OUT}")
        return out

    out = df.copy()
    out["ticker_base"] = out["ticker_base"].astype(str).str.strip().str.upper()
    out["name"] = out.get("name", "").astype(str).fillna("")
    out["board"] = out.get("board", "").astype(str).fillna("")

    out = out[out["ticker_base"].str.len() > 0].copy()
    out["ticker"] = out["ticker_base"] + ".TH"
    out["country"] = "TH"
    out["mic"] = "XBKK"

    out = out[["ticker_base","ticker","name","country","mic","board"]].drop_duplicates("ticker_base").reset_index(drop=True)
    out.to_csv(OUT, index=False)
    _write_meta(source, len(out))
    print(f"✅ TH: {len(out)} rows ({source}) → {OUT}")
    return out

def _download(url: str) -> bytes:
    r = requests.get(url, timeout=60, headers={"User-Agent":"NetNet-Global/1.0"})
    r.raise_for_status()
    return r.content

def _looks_like_common_stock(name: str) -> bool:
    n = (name or "").strip().upper()
    if not n:
        return True
    return not any(tok in n for tok in DENY_NAME_TOKENS)

def _parse_set_xls(content: bytes) -> pd.DataFrame:
    """
    SET sometimes serves an HTML table with .xls extension.
    - If it's real BIFF .xls: parse with xlrd
    - If it's HTML: parse with pandas.read_html
    """
    head = content.lstrip()[:20].lower()

    # Case A) HTML disguised as .xls
    if head.startswith(b"<") or b"<table" in head:
        html = content.decode("utf-8", errors="ignore")
        tables = pd.read_html(io.StringIO(html))
        if not tables:
            raise RuntimeError("No HTML tables found in .xls response")
        df = tables[0].copy()

    # Case B) real .xls (BIFF)
    else:
        try:
            df = pd.read_excel(io.BytesIO(content), engine="xlrd")
        except ImportError as e:
            raise RuntimeError(
                "Reading real .xls requires xlrd. Install: pip install xlrd==2.0.1"
            ) from e

    # ---- Normalize columns (robust) ----
    cols = {str(c).strip().lower(): c for c in df.columns}

    def find_col(candidates):
        for k in candidates:
            for ck, orig in cols.items():
                if k in ck:
                    return orig
        return None

    sym_col = find_col(["symbol", "ticker", "security symbol", "ชื่อย่อ", "หลักทรัพย์"])
    name_col = find_col(["company name", "security name", "name", "ชื่อบริษัท", "บริษัท"])
    board_col = find_col(["market", "board", "set/mai", "ประเภทตลาด"])

    if sym_col is None:
        sym_col = df.columns[0]
    if name_col is None:
        name_col = df.columns[1] if len(df.columns) > 1 else sym_col

    out = df[[sym_col, name_col]].copy()
    out.columns = ["ticker_base", "name"]

    out["board"] = df[board_col].astype(str).str.strip().str.upper() if board_col else ""

    out["ticker_base"] = out["ticker_base"].astype(str).str.strip().str.upper()
    out["name"] = out["name"].astype(str).str.strip()

    out = out.dropna(subset=["ticker_base"])
    out = out[out["ticker_base"].str.len() > 0]

    # keep your existing instrument filter
    out = out[out["name"].map(_looks_like_common_stock)]

    return out.reset_index(drop=True)

def _try_any_url(url: str) -> pd.DataFrame | None:
    if not url:
        return None
    try:
        content = _download(url)
        u = url.lower()
        if u.endswith(".xls"):
            return _parse_set_xls(content)
        if u.endswith(".xlsx"):
            df = pd.read_excel(io.BytesIO(content), engine="openpyxl")
            # Expect same semantics; map first two cols if needed
            if df.shape[1] >= 2:
                out = df.iloc[:, :2].copy()
                out.columns = ["ticker_base","name"]
                out["board"] = ""
                return out
        if u.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
            # best effort
            col0, col1 = df.columns[0], df.columns[1] if len(df.columns) > 1 else df.columns[0]
            out = df[[col0, col1]].copy()
            out.columns = ["ticker_base","name"]
            out["board"] = ""
            return out
    except Exception as e:
        print(f"[TH] URL fetch failed: {url} -> {e}")
    return None

def fetch_list() -> pd.DataFrame:
    # 0) env override (if you have one)
    df = _try_any_url(ENV_URL)
    if df is not None and not df.empty:
        return _write(df, "env")

    # 1) official SET static lists (EN then TH)
    for url, tag in ((SET_XLS_EN, "set_xls_en"), (SET_XLS_TH, "set_xls_th")):
        df = _try_any_url(url)
        if df is not None and not df.empty:
            return _write(df, tag)

    # 2) last resort: emit empty (keeps pipeline deterministic)
    return _write(pd.DataFrame(columns=["ticker_base","name","board"]), "empty")

if __name__ == "__main__":
    fetch_list()
