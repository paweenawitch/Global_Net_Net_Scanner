## application/cli/main_build_shortlist_cache_only.py
from __future__ import annotations
from pathlib import Path
import argparse
import logging
import json
from typing import Dict, List

from application.ports import ShortlistConfig
from application.build_shortlist_service import BuildShortlistService
from infrastructure.repositories.csv_universe_loader_repository import CsvUniverseLoaderRepository
from infrastructure.repositories.ncav_cache_repository import NcavCacheRepository
from infrastructure.repositories.local_shortlist_repository import LocalShortlistRepository
from infrastructure.repositories.sqlite_price_repository import SqlitePriceRepository
from infrastructure.sources.cached_price_client import CachedPriceClient

# Default project paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CACHE_ROOT = PROJECT_ROOT


def _load_fx_cache(path: Path) -> Dict[str, float]:
    """
    FX cache format written by update_fx_cache.py:

      {
        "units": "usd_per_ccy",
        "rates": { "USD": 1.0, "JPY": 0.0067, ... },
        ...
      }

    Returns only the 'rates' dict (USD per 1 CCY). Always includes USD=1.0.
    """
    if not path.exists():
        return {"USD": 1.0}

    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        # New structured format
        if isinstance(obj, dict) and isinstance(obj.get("rates"), dict):
            rates_obj = obj["rates"]
        # Backward compatibility: allow plain dict {"USD":1.0,...}
        elif isinstance(obj, dict):
            rates_obj = obj
        else:
            return {"USD": 1.0}

        out: Dict[str, float] = {}
        for k, v in rates_obj.items():
            try:
                out[str(k).upper()] = float(v)
            except Exception:
                continue
        out.setdefault("USD", 1.0)
        return out

    except Exception:
        return {"USD": 1.0}



class CachedFxProvider:
    """
    Implements the FxProvider port without network calls.
    """
    def __init__(self, usd_per: Dict[str, float]) -> None:
        self._usd_per = usd_per

    def usd_per_ccy(self, currencies: List[str]) -> Dict[str, float]:
        out = {"USD": 1.0}
        for c in currencies:
            if not c:
                continue
            c = str(c).upper()
            if c in self._usd_per:
                out[c] = self._usd_per[c]
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers_csv", type=str, default=str(CACHE_ROOT / "data" / "tickers" / "global_full.csv"))
    ap.add_argument("--price_cache", type=str, default=str(CACHE_ROOT / "data" / "db" / "market_snapshots.sqlite"))
    ap.add_argument("--fx_cache", type=str, default=str(CACHE_ROOT / "cache" / "fx" / "usd_per_ccy.json"))

    ap.add_argument("--max-workers", type=int, default=3)
    ap.add_argument("--fetch-timeout", type=int, default=12)
    ap.add_argument("--prices-batch", type=int, default=40)
    ap.add_argument("--limit", type=int)

    # Cache-only by design; we keep this flag but force it on
    ap.add_argument("--max-fs-age-days", type=int, default=730)
    ap.add_argument("--min-fs-age-days", type=int, default=90)
    ap.add_argument("--verbose", "-v", action="count", default=1,
                    help="-v INFO, -vv DEBUG, -vvv TRACE-like (DEBUG+extra)")
    ap.add_argument("--log-every", type=int, default=10, help="log fundamentals progress every N tickers")
    args = ap.parse_args()

    # Logging setup
    level = logging.WARNING
    if args.verbose == 1:
        level = logging.INFO
    elif args.verbose >= 2:
        level = logging.DEBUG
    logging.basicConfig(level=level, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    logger = logging.getLogger("shortlist-cache-only")
    logger.info("Starting shortlist builder (cache-only)")

    from infrastructure.repositories.sqlite_universe_repository import SqliteUniverseRepository
    from infrastructure.repositories.ncav_cache_repository import NcavCacheRepository

    universe = SqliteUniverseRepository(db_path=str(args.price_cache).replace("market_snapshots", "filings"))
    fundamentals = NcavCacheRepository()

    # ✅ Cached prices
    price_repo = SqlitePriceRepository(db_path=str(args.price_cache))
    prices = CachedPriceClient(price_repo)

    # ✅ Cached FX (no network)
    fx_rates = _load_fx_cache(Path(args.fx_cache))
    fx = CachedFxProvider(fx_rates)

    from infrastructure.repositories.sqlite_shortlist_repository import SqliteShortlistRepository
    out = SqliteShortlistRepository(db_path=str(args.price_cache).replace("market_snapshots", "filings"))

    svc = BuildShortlistService(universe, fundamentals, prices, fx, out, logger=logger, log_every=args.log_every)
    cfg = ShortlistConfig(
        max_workers=args.max_workers,
        fetch_timeout=args.fetch_timeout,
        prices_batch=args.prices_batch,
        max_fs_age_days=args.max_fs_age_days,
        min_fs_age_days=args.min_fs_age_days,
        prices_only=True,  # ✅ FORCE cache-only fundamentals
        limit=args.limit,
    )
    meta = svc.run(cfg)
    logger.info("Shortlist done → %s", meta["outputs"]["ncav_shortlist_csv"])
    print("Shortlist done ->", meta["outputs"]["ncav_shortlist_csv"])


if __name__ == "__main__":
    main()
