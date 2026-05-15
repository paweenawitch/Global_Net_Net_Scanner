from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from domain.models.fundamentals import NcavRecord
from domain.services.balance_sheet_metrics import ncav_total_native

BASE_URL = "https://www1.hkexnews.hk"
PREFIX_URL = f"{BASE_URL}/search/prefix.do"
TITLE_SEARCH_URL = f"{BASE_URL}/search/titleSearchServlet.do"


@dataclass(frozen=True)
class HKEXIssuer:
    stock_id: int
    code: str
    name: str


class HKEXNewsSource:
    """
    HKEX announcements helper.

    Stable endpoints:
    - /search/prefix.do to resolve a stock code or company name to an issuer id
    - /search/titleSearchServlet.do to fetch issuer documents as JSON
    """

    def __init__(
        self,
        session: Optional[requests.Session] = None,
        base_url: str = BASE_URL,
        filings_root: Optional[Path] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._session = session or requests.Session()
        self.filings_root = Path(filings_root) if filings_root else None
        headers = getattr(self._session, "headers", None)
        if headers is not None:
            headers.update({"User-Agent": "Mozilla/5.0"})

    def resolve_issuer(
        self,
        stock_code_or_name: str,
        *,
        market: str = "SEHK",
        lang: str = "EN",
        issuer_type: str = "A",
        timeout: int = 30,
    ) -> Optional[HKEXIssuer]:
        params = {
            "callback": "callback",
            "lang": lang,
            "type": issuer_type,
            "name": stock_code_or_name,
            "market": market,
        }
        resp = self._session.get(PREFIX_URL, params=params, timeout=timeout)
        resp.raise_for_status()

        payload = self._parse_jsonp(resp.text)
        stock_info = payload.get("stockInfo") or []
        if not stock_info:
            return None

        info = stock_info[0]
        try:
            stock_id = int(info["stockId"])
        except Exception:
            return None

        return HKEXIssuer(
            stock_id=stock_id,
            code=str(info.get("code") or "").strip(),
            name=str(info.get("name") or "").strip(),
        )

    def fetch_company_documents(
        self,
        stock_code_or_name: str,
        *,
        market: str = "SEHK",
        lang: str = "EN",
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        row_range: int = 4000,
        timeout: int = 30,
    ) -> Tuple[Optional[HKEXIssuer], List[Dict[str, Any]]]:
        issuer = self.resolve_issuer(
            stock_code_or_name,
            market=market,
            lang=lang,
            timeout=timeout,
        )
        if issuer is None:
            return None, []

        return issuer, self.fetch_documents(
            issuer.stock_id,
            market=market,
            lang="E" if lang.upper().startswith("EN") else lang,
            from_date=from_date,
            to_date=to_date,
            row_range=row_range,
            timeout=timeout,
        )

    def fetch_latest_document(
        self,
        stock_code_or_name: str,
        **kwargs: Any,
    ) -> Tuple[Optional[HKEXIssuer], Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        issuer, docs = self.fetch_company_documents(stock_code_or_name, **kwargs)
        return issuer, self.select_latest_document(docs), docs

    def fetch_latest_financial_report(
        self,
        stock_code_or_name: str,
        **kwargs: Any,
    ) -> Tuple[Optional[HKEXIssuer], Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        issuer, docs = self.fetch_company_documents(stock_code_or_name, **kwargs)
        return issuer, self.select_latest_financial_report(docs), docs

    def fetch_documents(
        self,
        stock_id: int,
        *,
        market: str = "SEHK",
        lang: str = "E",
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        row_range: int = 4000,
        category: int = 0,
        document_type: int = -1,
        search_type: int = 0,
        title: str = "",
        sort_by: str = "DateTime",
        sort_dir: int = 0,
        t1code: int = -2,
        t2gcode: int = -2,
        t2code: int = -2,
        timeout: int = 30,
    ) -> List[Dict[str, Any]]:
        if from_date is None:
            from_date = date(1999, 4, 1).strftime("%Y%m%d")
        if to_date is None:
            to_date = date.today().strftime("%Y%m%d")

        params = {
            "sortDir": sort_dir,
            "sortByOptions": sort_by,
            "category": category,
            "market": market,
            "stockId": stock_id,
            "documentType": document_type,
            "fromDate": from_date,
            "toDate": to_date,
            "title": title,
            "searchType": search_type,
            "t1code": t1code,
            "t2Gcode": t2gcode,
            "t2code": t2code,
            "rowRange": row_range,
            "lang": lang,
        }
        resp = self._session.get(TITLE_SEARCH_URL, params=params, timeout=timeout)
        resp.raise_for_status()

        outer = resp.json()
        raw_items = json.loads(outer.get("result") or "[]")
        return [self._normalize_document(item) for item in raw_items]

    def select_latest_document(self, docs: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not docs:
            return None
        return max(
            docs,
            key=lambda d: (
                d.get("published_at") or "",
                str(d.get("news_id") or ""),
            ),
        )

    def select_latest_financial_report(self, docs: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        reports = [d for d in docs if self.is_financial_report(d)]
        return self.select_latest_document(reports)

    def is_financial_report(self, document: Dict[str, Any]) -> bool:
        title = self._normalize_text(document.get("title") or "")
        document_type = self._normalize_text(document.get("document_type") or "")
        haystack = f"{title} {document_type}".strip()
        if not haystack:
            return False

        explicit_terms = (
            "annual report",
            "interim report",
            "quarterly report",
            "quarter result",
            "quarter results",
            "quarterly result",
            "quarterly results",
            "annual results",
            "interim results",
        )
        if any(term in haystack for term in explicit_terms):
            return True

        return bool(
            re.search(r"\b(?:first|second|third|fourth)\s+quarter\b", haystack)
            or re.search(r"\bquarter(?:ly)?\s+results?\b", haystack)
            or re.search(r"\bquarter(?:ly)?\s+report\b", haystack)
        )

    def download_document(self, document: Dict[str, Any], timeout: int = 30) -> bytes:
        url = str(document.get("url") or "").strip()
        if not url:
            raise ValueError("HKEX document is missing a URL")
        resp = self._session.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.content

    def document_extension(self, document: Dict[str, Any]) -> str:
        file_type = str(document.get("file_type") or "").strip().lower()
        if file_type == "pdf":
            return ".pdf"
        if file_type in {"htm", "html"}:
            return ".htm"

        url = str(document.get("url") or "").strip()
        suffix = Path(urlparse(url).path).suffix.lower()
        return suffix if suffix else ".bin"

    def extract_balance_sheet_snapshot(self, document: Dict[str, Any]) -> Dict[str, Any]:
        file_type = str(document.get("file_type") or "").strip().lower()
        if file_type not in {"htm", "html"}:
            return {
                "currency": "HKD",
                "report_kind": document.get("report_kind") or "hkex_report",
                "note": f"unsupported_file_type_{file_type or 'unknown'}",
            }

        html = self.download_document(document).decode("utf-8", errors="ignore")
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text(" ", strip=True)
        currency = self._detect_currency(text) or "HKD"

        tables = []
        for table in soup.find_all("table"):
            matrix = self._table_to_matrix(table)
            if matrix:
                tables.append(matrix)

        best = self._pick_balance_sheet_table(tables)
        if best is None:
            return {
                "currency": currency,
                "report_kind": document.get("report_kind") or "hkex_report",
                "note": "balance_sheet_table_not_found",
            }

        snapshot = self._extract_balance_sheet_from_matrix(best)
        snapshot["currency"] = currency
        snapshot["report_kind"] = document.get("report_kind") or "hkex_report"
        return snapshot

    def fetch_ncav_record(self, house_ticker: str) -> NcavRecord:
        issuer, latest_doc, docs = self.fetch_latest_financial_report(house_ticker)
        if latest_doc is None:
            return NcavRecord(
                ticker=house_ticker,
                y_symbol=house_ticker,
                statement_date=None,
                currency="HKD",
                assets_current=None,
                liab_total=None,
                ncav=None,
                shares_out=None,
                ncav_ps=None,
                source="hkex",
                cached_at=datetime.now().isoformat(timespec="seconds"),
                statement_sig="",
                note="no_financial_report_found",
            )

        self._persist_latest_report(house_ticker, issuer, latest_doc, docs)

        payload = self.extract_balance_sheet_snapshot(latest_doc)
        statement_date = (latest_doc.get("published_at") or "").split("T")[0] or None
        ccy = str(payload.get("currency") or "HKD").upper()
        assets_current = payload.get("assets_current")
        liab_total = payload.get("liab_total")
        assets_total = payload.get("assets_total")
        liab_current = payload.get("liab_current")
        liab_noncurrent = payload.get("liab_noncurrent")

        period = {
            "statement_date": statement_date,
            "currency": ccy,
            "balance": {
                k: v
                for k, v in {
                    "assets_current": {"val": assets_current} if assets_current is not None else None,
                    "assets_total": {"val": assets_total} if assets_total is not None else None,
                    "liab_total": {"val": liab_total} if liab_total is not None else None,
                    "liab_current": {"val": liab_current} if liab_current is not None else None,
                    "liab_noncurrent": {"val": liab_noncurrent} if liab_noncurrent is not None else None,
                }.items()
                if v is not None
            },
        }
        ncav = ncav_total_native(period)

        sig_input = f"{house_ticker}|{statement_date}|{latest_doc.get('news_id')}|{assets_current}|{liab_total}|{ccy}"
        sig = hashlib.sha256(sig_input.encode("utf-8")).hexdigest()[:16]

        data_age_days = None
        if statement_date:
            try:
                data_age_days = (datetime.now().date() - date.fromisoformat(statement_date)).days
            except Exception:
                data_age_days = None

        return NcavRecord(
            ticker=house_ticker,
            y_symbol=house_ticker,
            statement_date=statement_date,
            currency=ccy,
            assets_current=assets_current,
            liab_total=liab_total,
            ncav=ncav,
            shares_out=None,
            ncav_ps=None,
            source="hkex",
            cached_at=datetime.now().isoformat(timespec="seconds"),
            statement_sig=sig,
            data_age_days=data_age_days,
            fs_source=payload.get("report_kind") or "hkex_report",
            fs_selected_col=statement_date,
            note=payload.get("note"),
        )

    def _persist_latest_report(
        self,
        ticker: str,
        issuer: Optional[HKEXIssuer],
        latest_doc: Dict[str, Any],
        docs: List[Dict[str, Any]],
    ) -> None:
        if self.filings_root is None:
            return

        ticker_dir = self.filings_root / ticker
        ticker_dir.mkdir(parents=True, exist_ok=True)
        project_root = self.filings_root.parent.parent.parent

        raw_bytes = self.download_document(latest_doc)
        raw_ext = self.document_extension(latest_doc)
        raw_path = ticker_dir / f"latest{raw_ext}"
        raw_path.write_bytes(raw_bytes)

        payload = {
            "ticker": ticker,
            "issuer": None if issuer is None else {
                "stock_id": issuer.stock_id,
                "code": issuer.code,
                "name": issuer.name,
            },
            "latest_document": latest_doc,
            "documents_count": len(docs),
            "raw_document_path": str(raw_path.relative_to(project_root)),
            "fetched_at": datetime.now().isoformat(timespec="seconds"),
            "source": "hkexnews",
        }
        (ticker_dir / "latest.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

        index_path = self.filings_root / "index.json"
        index = {"updated_at": payload["fetched_at"], "tickers": {}}
        if index_path.exists():
            try:
                index = json.loads(index_path.read_text(encoding="utf-8"))
            except Exception:
                index = {"updated_at": payload["fetched_at"], "tickers": {}}

        index.setdefault("tickers", {})
        index["tickers"][ticker] = {
            "news_id": latest_doc.get("news_id"),
            "published_at": latest_doc.get("published_at"),
            "title": latest_doc.get("title"),
            "file_type": latest_doc.get("file_type"),
            "url": latest_doc.get("url"),
            "latest_json": str((ticker_dir / "latest.json").relative_to(project_root)),
            "raw_document_path": str(raw_path.relative_to(project_root)),
            "fetched_at": payload["fetched_at"],
            "issuer": payload["issuer"],
        }
        index["updated_at"] = payload["fetched_at"]
        index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")

    def _table_to_matrix(self, table) -> List[List[str]]:
        rows: List[List[str]] = []
        for tr in table.find_all("tr"):
            cells = tr.find_all(["th", "td"])
            if not cells:
                continue
            values = [self._strip_html(cell.get_text(" ", strip=True)) for cell in cells]
            if any(v for v in values):
                rows.append(values)
        return rows

    def _pick_balance_sheet_table(self, tables: List[List[List[str]]]) -> Optional[List[List[str]]]:
        if not tables:
            return None

        priority = ("balance sheet", "statement of financial position", "financial position")

        def score(table: List[List[str]]) -> int:
            text = " ".join(" ".join(row) for row in table).lower()
            return sum(5 for term in priority if term in text)

        return max(tables, key=score)

    def _extract_balance_sheet_from_matrix(self, matrix: List[List[str]]) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "assets_current": None,
            "assets_total": None,
            "liab_current": None,
            "liab_noncurrent": None,
            "liab_total": None,
            "cash": None,
            "receivables": None,
            "inventory": None,
            "equity": None,
        }

        for row in matrix:
            if len(row) < 2:
                continue
            label = self._normalize_text(row[0])
            values = [self._parse_number(cell) for cell in row[1:]]
            value = next((v for v in values if v is not None), None)
            if value is None:
                continue

            if self._label_matches(label, "current assets"):
                out["assets_current"] = value
            elif self._label_matches(label, "total assets"):
                out["assets_total"] = value
            elif self._label_matches(label, "current liabilities"):
                out["liab_current"] = value
            elif self._label_matches(label, "non current liabilities") or self._label_matches(label, "non-current liabilities"):
                out["liab_noncurrent"] = value
            elif self._label_matches(label, "total liabilities"):
                out["liab_total"] = value
            elif self._label_matches(label, "cash and cash equivalents"):
                out["cash"] = value
            elif self._label_matches(label, "receivables") or self._label_matches(label, "trade receivables"):
                out["receivables"] = value
            elif self._label_matches(label, "inventories") or self._label_matches(label, "inventory"):
                out["inventory"] = value
            elif self._label_matches(label, "equity") or self._label_matches(label, "owners equity") or self._label_matches(label, "shareholders equity"):
                out["equity"] = value

        if out["liab_total"] is None and out["liab_current"] is not None and out["liab_noncurrent"] is not None:
            out["liab_total"] = out["liab_current"] + out["liab_noncurrent"]
        return out

    def _parse_number(self, raw: str) -> Optional[float]:
        s = self._strip_html(raw)
        if not s:
            return None
        s = s.replace(",", "").replace("HK$", "").replace("HKD", "")
        s = s.replace("(", "-").replace(")", "")
        m = re.search(r"-?\d+(?:\.\d+)?", s)
        if not m:
            return None
        try:
            return float(m.group(0))
        except Exception:
            return None

    def _label_matches(self, label: str, needle: str) -> bool:
        return self._normalize_text(needle) in label

    def _detect_currency(self, text: str) -> Optional[str]:
        txt = text.upper()
        for ccy in ["HKD", "HK$", "CNY", "RMB", "USD", "JPY"]:
            if ccy in txt:
                return "HKD" if ccy == "HK$" else ccy
        return None

    def _normalize_document(self, item: Dict[str, Any]) -> Dict[str, Any]:
        file_link = str(item.get("FILE_LINK") or "").strip()
        title = str(item.get("TITLE") or "").strip()
        document_type = self._strip_html(item.get("SHORT_TEXT"))
        normalized = {
            "news_id": item.get("NEWS_ID"),
            "published_at": self._parse_hkex_datetime(item.get("DATE_TIME")),
            "stock_code": self._strip_html(item.get("STOCK_CODE")),
            "stock_name": self._strip_html(item.get("STOCK_NAME")),
            "title": title,
            "category": self._strip_html(item.get("LONG_TEXT") or item.get("SHORT_TEXT")),
            "document_type": document_type,
            "file_type": str(item.get("FILE_TYPE") or "").strip(),
            "file_info": str(item.get("FILE_INFO") or "").strip(),
            "total_count": self._safe_int(item.get("TOTAL_COUNT")),
            "relative_url": file_link,
            "url": urljoin(self.base_url + "/", file_link.lstrip("/")) if file_link else None,
            "raw": item,
        }
        normalized["report_kind"] = self._infer_report_kind(title, document_type)
        return normalized

    def _infer_report_kind(self, title: str, document_type: str = "") -> Optional[str]:
        text = self._normalize_text(f"{title} {document_type}")
        if not text:
            return None

        if "annual report" in text or re.search(r"\bannual\s+results?\b", text):
            return "annual_report"
        if "interim report" in text or re.search(r"\binterim\s+results?\b", text):
            return "interim_report"
        if "quarterly report" in text or "quarterly results" in text or "quarter results" in text:
            return "quarterly_report"
        if re.search(r"\b(?:first|second|third|fourth)\s+quarter\b", text):
            return "quarterly_report"
        if re.search(r"\bquarter(?:ly)?\s+results?\b", text):
            return "quarterly_report"
        return None

    def _parse_jsonp(self, text: str) -> Dict[str, Any]:
        match = re.match(r"^\s*[^(]+\((.*)\);\s*$", text, re.DOTALL)
        if not match:
            raise ValueError("Unexpected HKEX JSONP payload")
        return json.loads(match.group(1))

    def _parse_hkex_datetime(self, value: Any) -> Optional[str]:
        if not value:
            return None
        try:
            dt = datetime.strptime(str(value).strip(), "%d/%m/%Y %H:%M")
            return dt.isoformat(timespec="minutes")
        except Exception:
            return None

    def _strip_html(self, value: Any) -> str:
        text = re.sub(r"<[^>]+>", " ", str(value or ""))
        return re.sub(r"\s+", " ", text).strip()

    def _normalize_text(self, value: Any) -> str:
        return self._strip_html(value).lower()

    def _safe_int(self, value: Any) -> Optional[int]:
        try:
            return int(value)
        except Exception:
            return None
