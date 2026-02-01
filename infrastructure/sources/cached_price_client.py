# infrastructure/sources/cached_price_client.py

from __future__ import annotations
from typing import Dict, List, Optional, Tuple

from application.ports import PriceClient
from infrastructure.repositories.json_price_cache_repository import JsonPriceCacheRepository


class CachedPriceClient(PriceClient):
    """
    Adapter: present cached prices as a PriceClient.
    Returns the same mapping as YahooPriceClient.latest_closes:
      symbol -> (price, asof)
    """

    def __init__(self, repo: JsonPriceCacheRepository) -> None:
        self.repo = repo

    def latest_closes(
        self,
        y_symbols: List[str],
        batch_size: int,
    ) -> Dict[str, Tuple[Optional[float], Optional[str]]]:
        out: Dict[str, Tuple[Optional[float], Optional[str]]] = {}
        if not y_symbols:
            return out

        # repo supports bulk get; preserve request order
        got = self.repo.get_many_cached(list(dict.fromkeys(y_symbols)))
        for s in y_symbols:
            p = got.get(s)
            if p is None:
                out[s] = (None, None)
            else:
                out[s] = (p.price, p.asof)
        return out
