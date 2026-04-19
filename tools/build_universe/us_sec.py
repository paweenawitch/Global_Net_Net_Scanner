from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "tickers"
DATA.mkdir(parents=True, exist_ok=True)

OUT_CSV = DATA / "us_full.csv"
OUT_META = DATA / "us_full.meta.json"
CACHE_JSON = ROOT / "cache" / "sec_company_tickers.json"
CACHE_JSON.parent.mkdir(parents=True, exist_ok=True)

# SEC requires a descriptive User-Agent. Set SEC_USER_AGENT env var for your email.
SEC_UA = os.environ.get("SEC_USER_AGENT", "mary/1.0 (yourname@email.com)")

# SEC ticker endpoints.
EXCHANGE_TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
MUTUAL_FUND_TICKERS_URL = "https://www.sec.gov/files/company_tickers_mf.json"

# Universe policy: common-equity-ish filter. Keep it conservative and explainable.
# False negatives are preferred to false positives for this screening pipeline.
BAD_NAME_PAT = re.compile(
    r"("
    r"\betf\b|exchange\s*traded\s*fund|"
    r"\betn\b|exchange\s*traded\s*note|"
    r"\bfund\b|\bportfolio\b|"
    r"closed[-\s]*end|"
    r"warrant|wts|rights?|unit|"
    r"spac|acquisition|blank\s*check|trust"
    r")",
    re.IGNORECASE,
)
BAD_CODE_PAT = re.compile(r"(-WT|-WTS|-WS|-U|-UN|-RT|-R|\s+WTS?|\s+UNIT|\s+RT)$", re.IGNORECASE)

# SEC ticker files do not reliably provide the exchange/MIC. Keep explicit UNKNOWN.
DEFAULT_PRIMARY_LISTING_MIC = "UNKNOWN"


def get_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": SEC_UA, "Accept-Encoding": "gzip, deflate"})
    return s


def _build_rows_from_exchange_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    fields = payload.get("fields") or []
    data = payload.get("data") or []
    if not isinstance(fields, list) or not isinstance(data, list):
        return []

    index_by_name = {str(name): idx for idx, name in enumerate(fields)}
    required = {"cik", "name", "ticker"}
    if not required.issubset(index_by_name):
        return []

    rows: list[dict[str, Any]] = []
    for entry in data:
        if not isinstance(entry, list):
            continue

        ticker_idx = index_by_name["ticker"]
        ticker = str(entry[ticker_idx] if ticker_idx < len(entry) else "").strip().upper()
        if not ticker:
            continue

        name_idx = index_by_name["name"]
        cik_idx = index_by_name["cik"]

        name_raw = entry[name_idx] if name_idx < len(entry) else ""
        cik_raw = entry[cik_idx] if cik_idx < len(entry) else 0
        try:
            cik_int = int(cik_raw or 0)
        except Exception:
            cik_int = 0

        rows.append(
            {
                "instrument_id": f"{ticker}.US",
                "ticker_base": ticker,
                "ticker": f"{ticker}.US",
                "cik": (str(cik_int).zfill(10) if cik_int > 0 else None),
                "name": str(name_raw or "").strip(),
                "country": "US",
                "primary_listing_mic": DEFAULT_PRIMARY_LISTING_MIC,
            }
        )

    return rows


def _build_mutual_fund_symbol_set(payload: dict[str, Any]) -> set[str]:
    fields = payload.get("fields") or []
    data = payload.get("data") or []
    if not isinstance(fields, list) or not isinstance(data, list):
        return set()

    try:
        symbol_idx = fields.index("symbol")
    except ValueError:
        return set()

    out: set[str] = set()
    for entry in data:
        if not isinstance(entry, list) or symbol_idx >= len(entry):
            continue
        symbol = str(entry[symbol_idx] or "").strip().upper()
        if symbol:
            out.add(symbol)
    return out


def fetch_exchange_tickers(sec: requests.Session) -> list[dict[str, Any]]:
    r = sec.get(EXCHANGE_TICKERS_URL, timeout=30)
    r.raise_for_status()
    data = r.json()
    CACHE_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return _build_rows_from_exchange_payload(data)


def fetch_mutual_fund_symbols(sec: requests.Session) -> set[str]:
    r = sec.get(MUTUAL_FUND_TICKERS_URL, timeout=30)
    r.raise_for_status()
    data = r.json()
    return _build_mutual_fund_symbol_set(data)


def classify_exclusion_reason(row: dict[str, Any], mf_symbols: set[str]) -> str | None:
    name = str(row.get("name", "") or "")
    code = str(row.get("ticker_base", "") or "").upper()

    if code in mf_symbols:
        return "mutual_fund_symbol"
    if BAD_NAME_PAT.search(name):
        return "name_pattern_non_common"
    if BAD_CODE_PAT.search(code):
        return "ticker_pattern_non_common"
    return None


def apply_sec_verifier_filters(
    rows: list[dict[str, Any]],
    *,
    mf_symbols: set[str],
) -> tuple[pd.DataFrame, dict[str, int]]:
    kept: list[dict[str, Any]] = []
    counts: dict[str, int] = {"kept": 0}

    for row in rows:
        reason = classify_exclusion_reason(row, mf_symbols)
        if reason is None:
            kept.append(row)
            counts["kept"] += 1
            continue
        counts[reason] = counts.get(reason, 0) + 1

    return pd.DataFrame(kept), counts


def sym_score(sym: str) -> int:
    """
    Deterministic tie-breaker for multiple tickers per CIK:
    - penalize digits/suffixes a bit
    - prefer shorter, cleaner tickers
    """
    s = sym or ""
    score = 0
    if any(ch.isdigit() for ch in s):
        score += 10
    if s.endswith("F"):
        score += 5
    if s.endswith("Y"):
        score += 5
    score += len(s)
    return score


def fetch_list() -> pd.DataFrame:
    s = get_session()
    rows = fetch_exchange_tickers(s)
    before = len(rows)
    mf_symbols = fetch_mutual_fund_symbols(s)

    df, exclusion_counts = apply_sec_verifier_filters(rows, mf_symbols=mf_symbols)

    # Clean + filter
    df = df.dropna(subset=["ticker_base", "ticker"]).drop_duplicates("ticker_base")

    # Require CIK for US universe usefulness (filing-first)
    df = df.dropna(subset=["cik"]).copy()

    # Within a CIK, keep the best ticker deterministically.
    df["__score"] = df["ticker_base"].astype(str).map(sym_score)
    df = (
        df.sort_values(["cik", "__score", "ticker_base"]).groupby("cik", as_index=False).first()
    )

    df = (
        df[
            [
                "instrument_id",
                "ticker",
                "ticker_base",
                "name",
                "country",
                "cik",
                "primary_listing_mic",
            ]
        ]
        .sort_values("ticker")
        .reset_index(drop=True)
    )

    df.to_csv(OUT_CSV, index=False)

    meta = {
        "source": "sec_company_tickers_exchange.json",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rows": int(len(df)),
        "raw_rows": int(before),
        "path": str(OUT_CSV),
        "schema": {
            "instrument_id_field": "instrument_id",
            "entity_hint_field": "cik",
            "primary_listing_mic_field": "primary_listing_mic",
        },
        "verifier_sources": {
            "exchange_tickers": EXCHANGE_TICKERS_URL,
            "mutual_fund_tickers": MUTUAL_FUND_TICKERS_URL,
        },
        "exclusion_counts": {k: int(v) for k, v in exclusion_counts.items() if k != "kept"},
        "universe_policy": {
            "instrument_type": "common_equity_only_best_effort_with_sec_verifier",
            "excludes_by_sec_sets": ["mutual_fund_symbols"],
            "excludes_by_name_or_code": ["spac", "units", "warrants", "rights", "trust", "etf", "fund", "etn"],
            "listing_scope": ["primary_listings_unknown_from_sec"],
            "currency_policy": "native_currency_at_source",
        },
        "notes": [
            "Universe baseline uses SEC exchange tickers and excludes SEC mutual-fund symbols.",
            "SEC exchange data does not provide MIC; primary_listing_mic is best-effort = UNKNOWN.",
            "CIK is stored as zero-padded string for reliable joining later.",
        ],
    }
    OUT_META.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"US: {len(df)} rows -> {OUT_CSV}")
    return df


if __name__ == "__main__":
    fetch_list()
