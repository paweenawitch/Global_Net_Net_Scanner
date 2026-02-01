# infrastructure/repositories/json_price_cache_repository.py

from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Dict, Optional

from application.ports import PricePoint, PriceRepository


class JsonPriceCacheRepository(PriceRepository):
    """
    Cache format (single file):
    {
      "updated_at": "2026-01-31T12:34:56Z",
      "prices": {
        "AAPL": {
          "symbol": "AAPL",
          "price": 123.45,
          "asof": "2026-01-31",
          "currency": "USD",
          "updated_at": "2026-01-31T12:34:56Z"
        },
        ...
      }
    }

    Backward compatible with older records missing "currency".
    """

    def __init__(self, cache_path: str = "cache/prices/latest.json") -> None:
        self.cache_path = cache_path

    def get_cached(self, symbol: str) -> Optional[PricePoint]:
        data = self._read()
        node = data.get("prices", {}).get(symbol)
        if not node:
            return None
        return self._to_price_point(node)

    def get_many_cached(self, symbols: list[str]) -> Dict[str, PricePoint]:
        data = self._read()
        prices = data.get("prices", {})
        out: Dict[str, PricePoint] = {}
        for s in symbols:
            node = prices.get(s)
            if node:
                out[s] = self._to_price_point(node)
        return out

    def put_many(self, points: list[PricePoint]) -> None:
        data = self._read()
        prices = data.setdefault("prices", {})

        for p in points:
            # asdict will include currency if your PricePoint dataclass has it
            prices[p.symbol] = asdict(p)

        data["updated_at"] = _utc_now_iso()
        self._write_atomic(data)

    # ---------- internals ----------

    def _read(self) -> dict:
        if not os.path.exists(self.cache_path):
            return {"updated_at": None, "prices": {}}
        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                obj = json.load(f)
            # normalize shape
            if not isinstance(obj, dict):
                return {"updated_at": None, "prices": {}}
            if "prices" not in obj or not isinstance(obj.get("prices"), dict):
                obj["prices"] = {}
            if "updated_at" not in obj:
                obj["updated_at"] = None
            return obj
        except Exception:
            # Corrupt file? Fail safe: start fresh rather than crashing your pipeline.
            return {"updated_at": None, "prices": {}}

    def _write_atomic(self, data: dict) -> None:
        dirpath = os.path.dirname(self.cache_path)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        tmp = self.cache_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.cache_path)

    @staticmethod
    def _to_price_point(node: dict) -> PricePoint:
        """
        Be tolerant to:
          - missing keys
          - older caches without 'currency'
          - wrong types
        """
        symbol = str(node.get("symbol") or "")
        price = node.get("price")
        asof = node.get("asof")
        currency = node.get("currency")  # may be missing in old cache
        updated_at = str(node.get("updated_at") or "")

        # Normalize currency string
        if currency is not None:
            try:
                currency = str(currency).upper()
            except Exception:
                currency = None

        return PricePoint(
            symbol=symbol,
            price=price,
            asof=asof,
            currency=currency,
            updated_at=updated_at,
        )


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
