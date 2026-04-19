# infrastructure/sources/us_sec_source.py
from __future__ import annotations
import logging
import os
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import requests

LOGGER = logging.getLogger("infrastructure.sources.us_sec")

SEC_UA = os.environ.get("SEC_USER_AGENT", "net_net_screener_global/1.0 (yourname@email.com)")
SLEEP = float(os.environ.get("SEC_SLEEP", "0.35"))

FACTS_URL       = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
COMPANY_TICKERS_JSON = "https://www.sec.gov/files/company_tickers.json"

# --- Parsing Concepts ---
BALANCE_CONCEPTS = {
    "assets_total":    "Assets",
    "assets_current":  "AssetsCurrent",
    "cash":            "CashAndCashEquivalentsAtCarryingValue",
    "short_invest":    "MarketableSecuritiesCurrent",
    "receivables":     "AccountsReceivableNetCurrent",
    "inventory":       "InventoryNet",
    "liab_total":      "Liabilities",
    "liab_current":    "LiabilitiesCurrent",
    "liab_noncurrent": "LiabilitiesNoncurrent",
    "equity":          "StockholdersEquity",
}
INCOME_CONCEPTS = {
    "revenue":       "SalesRevenueNet",
    "gross_profit":  "GrossProfit",
    "oper_income":   "OperatingIncomeLoss",
    "net_income":    "NetIncomeLoss",
}
CF_CONCEPTS = {
    "cfo":            "NetCashProvidedByUsedInOperatingActivities",
    "capex":          "PaymentsToAcquirePropertyPlantAndEquipment",
    "dividends_paid": "PaymentsOfDividends",
}

SHARE_CONCEPTS_PRIORITY = [
    ("CommonStockSharesOutstanding",                    "shares"),
    ("EntityCommonStockSharesOutstanding",              "shares"),
    ("CommonStockSharesOutstandingRestated",            "shares"),
    ("WeightedAverageNumberOfDilutedSharesOutstanding", "shares"),
    ("WeightedAverageNumberOfSharesOutstandingBasic",   "shares"),
    ("WeightedAverageNumberOfSharesOutstanding",        "shares"),
]

class UsSecSource:
    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": SEC_UA, "Accept-Encoding": "gzip, deflate"})

    def fetch_core(self, ticker: str, cik: Optional[int] = None) -> Dict[str, Any]:
        if not cik:
            cik = self.get_cik_for_ticker(ticker)
        if not cik:
            raise ValueError(f"Could not find CIK for ticker {ticker}")
            
        LOGGER.info(f"Fetching SEC facts for {ticker} (CIK {cik:010d})")
        facts = self._fetch_json(FACTS_URL.format(cik=cik))
        
        LOGGER.info(f"Fetching SEC submissions for {ticker}")
        subs = self._fetch_json(SUBMISSIONS_URL.format(cik=cik))
        
        return self._build_core_object(ticker, cik, facts, subs)

    def get_cik_for_ticker(self, ticker: str) -> Optional[int]:
        """Fetch mapping if needed and return CIK for a given US ticker."""
        # Strip .US if present
        sym = ticker.upper().replace(".US", "").strip()
        
        # Lazy load map
        if not hasattr(self, "_ticker_map"):
            try:
                LOGGER.info("Loading SEC ticker-to-CIK map...")
                data = self._fetch_json(COMPANY_TICKERS_JSON)
                self._ticker_map = {}
                for v in (data or {}).values():
                    t = str(v.get("ticker", "")).upper()
                    c = v.get("cik_str")
                    if t and c is not None:
                        self._ticker_map[t] = int(c)
            except Exception as e:
                LOGGER.error(f"Failed to load SEC ticker map: {e}")
                return None
                
        return self._ticker_map.get(sym)

    def _fetch_json(self, url: str) -> Dict[str, Any]:
        time.sleep(SLEEP)
        r = self._session.get(url, timeout=60)
        if not r.ok:
            if r.status_code == 404: return {}
            r.raise_for_status()
        return r.json()

    # --- Internal Parsing Logic (Ported from tools/sec_extract_core.py) ---
    
    def _iter_points(self, facts: dict, concept: str) -> List[dict]:
        try:
            node = facts["facts"]["us-gaap"][concept]
        except Exception: return []
        out = []
        for unit, arr in (node.get("units") or {}).items():
            for pt in arr or []:
                v = pt.get("val")
                if isinstance(v, (int, float)):
                    out.append({
                        "end": pt.get("end") or "",
                        "fp": (pt.get("fp") or "").upper(),
                        "fy": pt.get("fy"),
                        "form": (pt.get("form") or "").upper(),
                        "accn": pt.get("accn"),
                        "val": float(v),
                        "unit": unit,
                    })
        out.sort(key=lambda x: x["end"], reverse=True)
        return out

    def _pick_at_date(self, facts: dict, concept: str, end_date: str) -> Optional[dict]:
        for pt in self._iter_points(facts, concept):
            if pt["end"] == end_date:
                return {
                    "val": pt["val"],
                    "src": f"us-gaap:{concept}",
                    "form": pt.get("form"),
                    "unit": pt.get("unit"),
                }
        return None

    def _pick_shares_at_date(self, facts: dict, end_date: str) -> Optional[dict]:
        for concept, hint in SHARE_CONCEPTS_PRIORITY:
            try:
                node = facts["facts"]["us-gaap"][concept]
                units = node.get("units") or {}
                # Try hint first, then any with 'shares'
                ordered = [hint] if hint in units else []
                ordered += [u for u in units if u != hint and "shares" in u.lower()]
                for uk in ordered:
                    for pt in units[uk] or []:
                        if pt.get("end") == end_date and isinstance(pt.get("val"), (int,float)):
                            return {"val": float(pt["val"]), "src": f"us-gaap:{concept}", "unit": uk}
            except Exception: continue
        return None

    def _detect_currency(self, facts: dict) -> Optional[str]:
        for concept in ["Assets","AssetsCurrent","Liabilities"]:
            for pt in self._iter_points(facts, concept):
                unit = pt.get("unit")
                if unit:
                    head = unit.split("/")[0].upper()
                    if len(head) == 3: return head
        return "USD"

    def _build_period(self, facts: dict, end_date: str) -> dict:
        ccy = self._detect_currency(facts)
        bal = {k: self._pick_at_date(facts, c, end_date) for k, c in BALANCE_CONCEPTS.items()}
        bal = {k: v for k, v in bal.items() if v}
        
        shares = self._pick_shares_at_date(facts, end_date)
        if shares: bal["shares_out"] = shares
        
        inc = {k: self._pick_at_date(facts, c, end_date) for k, c in INCOME_CONCEPTS.items()}
        inc = {k: v for k, v in inc.items() if v}
        
        cf = {k: self._pick_at_date(facts, c, end_date) for k, c in CF_CONCEPTS.items()}
        cf = {k: v for k, v in cf.items() if v}
        
        return {"date": end_date, "currency": ccy, "balance": bal, "income": inc, "cashflow": cf}

    def _build_core_object(self, ticker: str, cik: int, facts: dict, subs: dict) -> dict:
        # Collect dates
        dates = set()
        for concept in ["AssetsCurrent","Liabilities"]:
            for pt in self._iter_points(facts, concept):
                if pt["end"]: dates.add(pt["end"])
        
        sorted_dates = sorted(dates, reverse=True)[:10]
        periods = [self._build_period(facts, d) for d in sorted_dates]
        
        # Derive latest
        latest = {}
        if periods:
            p = periods[0]
            b = p.get("balance") or {}
            ca = (b.get("assets_current") or {}).get("val")
            tl = (b.get("liab_total") or {}).get("val")
            if tl is None:
                lc = (b.get("liab_current") or {}).get("val")
                lnc = (b.get("liab_noncurrent") or {}).get("val")
                if lc is not None and lnc is not None: tl = lc + lnc
            
            sh = (b.get("shares_out") or {}).get("val")
            ncav = (ca - tl) if (ca is not None and tl is not None) else None
            ncav_ps = (ncav / sh) if (ncav and sh) else None
            
            latest = {
                "date": p["date"],
                "ncav": ncav,
                "ncav_ps": ncav_ps,
            }

        return {
            "meta": {
                "schema_version": "core.v1",
                "ticker": ticker,
                "name": subs.get("name"),
                "country_iso": "US",
                "sector": subs.get("sicDescription"),
                "ids": {"cik": f"{cik:010d}"},
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "source": "SEC",
            },
            "financials": {
                "annual": {"periods": [p for p in periods if "-12-" in p["date"] or "-11-" in p["date"]][:5]},
                "quarterly": {"periods": periods[:4]},
            },
            "derived": {"latest": latest}
        }

    # --- Insider (Form 4) Scanning (Ported from tools/sec_insider_scan.py) ---

    def fetch_insiders(self, ticker: str, cik: Optional[int] = None, days_back: int = 180) -> Dict[str, Any]:
        if not cik:
            cik = self.get_cik_for_ticker(ticker)
        if not cik:
            return self._empty_insider(ticker, "no_cik")

        LOGGER.info(f"Scanning SEC Form 4 filings for {ticker} (CIK {cik:010d}, {days_back} days)")
        filings = self._list_recent_form4(cik, days_back)

        buys = sells = 0
        bsh = ssh = 0.0

        for acc_nodash, prim in filings:
            files = self._fetch_filing_dir(cik, acc_nodash)
            if not files: continue
            pick = self._pick_form4_xml(files, prim)
            if not pick:
                xmls = [f for f in files if f.lower().endswith(".xml")]
                pick = xmls[0] if xmls else None
            if not pick: continue
            
            xml_text = self._fetch_filing_file(cik, acc_nodash, pick)
            if not xml_text: continue
            
            summary = self._summarize_form4(xml_text)
            buys += summary["buys_count"]
            sells += summary["sells_count"]
            bsh += summary["buys_shares"]
            ssh += summary["sells_shares"]

        status = "ok" if (buys or sells or bsh or ssh) else "no_data"
        signal = "Neutral"
        if (buys > 0 and sells == 0) or (bsh > ssh): signal = "InsiderBuy"
        elif (sells > 0 and buys == 0) or (ssh > bsh): signal = "InsiderSell"

        return {
            "ticker": ticker,
            "as_of": datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z",
            "buys_count": int(buys),
            "sells_count": int(sells),
            "buys_shares": float(bsh),
            "sells_shares": float(ssh),
            "net_shares": float(bsh - ssh),
            "signal": signal,
            "status": status,
            "source": "edgar_form4_xml",
            "insiders_percent_held": None,
            "insiders_percent_held_source": None,
        }

    def _empty_insider(self, ticker: str, reason: str) -> Dict[str, Any]:
        return {
            "ticker": ticker,
            "as_of": datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z",
            "buys_count": 0, "sells_count": 0, "buys_shares": 0.0, "sells_shares": 0.0, "net_shares": 0.0,
            "signal": "Neutral", "status": reason, "source": "edgar_form4_xml",
            "insiders_percent_held": None, "insiders_percent_held_source": None
        }

    def _list_recent_form4(self, cik: int, days_back: int) -> List[Tuple[str, str]]:
        url = SUBMISSIONS_URL.format(cik=cik)
        sub = self._fetch_json(url)
        if not sub: return []
        
        rec = sub.get("filings", {}).get("recent", {})
        forms = rec.get("form", [])
        accs = rec.get("accessionNumber", [])
        prims = rec.get("primaryDocument", [])
        dates = rec.get("filingDate", [])
        
        out = []
        cutoff = datetime.now(timezone.utc).date() - timedelta(days=days_back)
        for i, f in enumerate(forms):
            if f not in ("4", "4/A"): continue
            try:
                fdate = datetime.strptime(dates[i], "%Y-%m-%d").date()
                if fdate < cutoff: continue
                acc = accs[i].replace("-", "")
                out.append((acc, prims[i] or ""))
            except Exception: continue
        return out

    def _fetch_filing_dir(self, cik: int, acc_nodash: str) -> List[str]:
        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_nodash}/index.json"
        js = self._fetch_json(url)
        if not js: return []
        try:
            items = js.get("directory", {}).get("item") or []
            return [f.get("name") for f in items if isinstance(f.get("name"), str)]
        except Exception: return []

    def _pick_form4_xml(self, files: List[str], primary_hint: str = "") -> Optional[str]:
        cand = []
        for fn in files:
            lower = fn.lower()
            if not lower.endswith(".xml"): continue
            score = 0
            if "form4" in lower or "doc4" in lower or "f4" in lower: score += 5
            if "primary" in lower: score += 2
            if primary_hint and lower.endswith(primary_hint.lower()): score += 3
            cand.append((score, fn))
        if not cand: return None
        cand.sort(reverse=True)
        return cand[0][1]

    def _fetch_filing_file(self, cik: int, acc_nodash: str, filename: str) -> Optional[str]:
        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_nodash}/{filename}"
        time.sleep(SLEEP)
        r = self._session.get(url, timeout=30)
        return r.text if r.ok else None

    def _summarize_form4(self, xml_text: str) -> Dict[str, float]:
        import xml.etree.ElementTree as ET
        buys = sells = 0
        bsh = ssh = 0.0
        try:
            root = ET.fromstring(xml_text)
        except Exception: return {"buys_count":0, "sells_count":0, "buys_shares":0.0, "sells_shares":0.0}

        def _local(t): return t.split("}")[-1] if "}" in t else t
        def _get_val(n, name):
            for el in n.iter():
                if _local(el.tag).lower() == name.lower():
                    t = (el.text or "").strip()
                    if t: return t
                    for v in el.iter():
                        if _local(v.tag).lower() == "value" and (v.text or "").strip():
                            return v.text.strip()
            return None

        for n in root.iter():
            if _local(n.tag).lower().endswith("transaction"):
                code = _get_val(n, "transactionCode")
                if code not in ("P", "S"): continue
                
                sh = _get_val(n, "transactionShares")
                try: 
                    sh_f = abs(float(sh)) if sh else 0.0
                except: sh_f = 0.0
                
                if code == "P": buys += 1; bsh += sh_f
                else: sells += 1; ssh += sh_f
        
        return {"buys_count": buys, "sells_count": sells, "buys_shares": bsh, "sells_shares": ssh}
