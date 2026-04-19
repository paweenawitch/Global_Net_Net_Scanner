# application/cli/update_prices_cache.py

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple, List, Any

import yfinance as yf

from application.ports import PriceClient, PricePoint, ShortlistUniverseRepository
from infrastructure.repositories.sqlite_price_repository import SqlitePriceRepository


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


class DualLogger:
    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        _ensure_dir(log_path.parent)
        self.write(f"--- update_prices_cache start {_utc_now_iso()} ---")

    def write(self, msg: str) -> None:
        line = f"{_utc_now_iso()} | {msg}"
        print(line)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def _build_symbols_from_universe(universe_repo: ShortlistUniverseRepository) -> List[str]:
    # canonical mapping in your project
    from tools.ncav_cache import to_yahoo  # uses your mapping

    rows = universe_repo.load_tickers()
    syms: List[str] = []
    for r in rows:
        ht = r.get("ticker")
        if not ht:
            continue
        y = to_yahoo(str(ht))
        if y:
            syms.append(y)
    return sorted(set(syms))


def _load_quote_currency_cache(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_quote_currency_cache(path: Path, data: Dict[str, str]) -> None:
    _ensure_dir(path.parent)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


def _get_quote_currency(symbol: str, cc_map: Dict[str, str]) -> Optional[str]:
    """
    Slow path: yfinance Ticker().info call. Cache results to avoid repeat calls.
    """
    if symbol in cc_map:
        return cc_map[symbol] or None
    try:
        info = yf.Ticker(symbol).info or {}
        ccy = info.get("currency")
        if ccy:
            cc_map[symbol] = str(ccy).upper()
            return cc_map[symbol]
    except Exception:
        pass
    cc_map[symbol] = ""
    return None


def run(
    *,
    universe_repo: ShortlistUniverseRepository,
    price_client: PriceClient,
    price_repo: SqlitePriceRepository,
    batch_size: int,
    logger: DualLogger,
    limit: Optional[int],
    quote_ccy_cache_path: Path,
    quote_ccy_mode: str,   # "none" | "missing" | "all"
    min_batch_interval_s: float,
) -> None:
    symbols = _build_symbols_from_universe(universe_repo)
    if limit is not None:
        symbols = symbols[:limit]

    total = len(symbols)
    if total == 0:
        logger.write("No symbols found. Nothing to do.")
        return

    logger.write(f"Symbols: {total} | batch_size={batch_size}")
    logger.write(f"Quote currency mode: {quote_ccy_mode} | cache: {quote_ccy_cache_path}")
    logger.write(f"Rate limit guard: min_batch_interval_s={min_batch_interval_s}")

    updated_at = _utc_now_iso()
    points: List[PricePoint] = []

    ok = 0
    none_count = 0
    failed_batches = 0

    cc_map = _load_quote_currency_cache(quote_ccy_cache_path)
    cc_updates = 0

    for bi, i in enumerate(range(0, total, batch_size), start=1):
        chunk = symbols[i : i + batch_size]
        start_t = time.monotonic()

        logger.write(f"[batch {bi}] fetch {len(chunk)} symbols ({i}-{min(i+batch_size, total)} of {total})")

        try:
            res: Dict[str, Tuple[Optional[float], Optional[str]]] = price_client.latest_closes(
                chunk, batch_size=batch_size
            )
        except Exception as e:
            failed_batches += 1
            logger.write(f"[batch {bi}] FAIL | {type(e).__name__}: {e}")
            res = {s: (None, None) for s in chunk}

        for s in chunk:
            price, asof = res.get(s, (None, None))

            qccy: Optional[str] = None
            if quote_ccy_mode != "none":
                if quote_ccy_mode == "all":
                    before = cc_map.get(s)
                    qccy = _get_quote_currency(s, cc_map)
                    if before != cc_map.get(s):
                        cc_updates += 1
                elif quote_ccy_mode == "missing":
                    if s not in cc_map:
                        before = cc_map.get(s)
                        qccy = _get_quote_currency(s, cc_map)
                        if before != cc_map.get(s):
                            cc_updates += 1
                    else:
                        qccy = cc_map.get(s) or None

            if price is None:
                none_count += 1
            else:
                ok += 1

            points.append(
                PricePoint(
                    symbol=s,
                    price=price,
                    asof=asof,
                    currency=qccy,
                    updated_at=updated_at,
                )
            )

        elapsed = time.monotonic() - start_t
        if min_batch_interval_s > 0 and elapsed < min_batch_interval_s:
            sleep_s = min_batch_interval_s - elapsed
            logger.write(f"[batch {bi}] done | ok={ok} none={none_count} failed_batches={failed_batches} | sleeping {sleep_s:.2f}s")
            time.sleep(sleep_s)
        else:
            logger.write(f"[batch {bi}] done | ok={ok} none={none_count} failed_batches={failed_batches} | elapsed {elapsed:.2f}s")

    price_repo.put_many(points)
    logger.write(f"Saved {len(points)} price points to {price_repo._store._db_path}")

    if quote_ccy_mode != "none" and cc_updates > 0:
        _save_quote_currency_cache(quote_ccy_cache_path, cc_map)
        logger.write(f"Updated quote currency cache: {cc_updates} new/changed entries")

    audit: Dict[str, Any] = {
        "started_at": updated_at,
        "finished_at": _utc_now_iso(),
        "total_symbols": total,
        "batch_size": batch_size,
        "ok_prices": ok,
        "none_prices": none_count,
        "failed_batches": failed_batches,
        "quote_ccy_mode": quote_ccy_mode,
        "quote_ccy_cache": str(quote_ccy_cache_path),
        "min_batch_interval_s": min_batch_interval_s,
        "price_cache": price_repo._store._db_path,
    }
    audit_path = Path(str(logger.log_path) + ".json")
    audit_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")

    logger.write("--- SUMMARY ---")
    logger.write(json.dumps(audit, ensure_ascii=False))
    logger.write("--- update_prices_cache end ---")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="Path to universe CSV (absolute or project-relative)")
    ap.add_argument("--batch-size", type=int, default=50, help="Keep small to reduce Yahoo flakiness")
    ap.add_argument("--price-cache", type=str, default="data/db/market_snapshots.sqlite")
    ap.add_argument("--log-dir", type=str, default="logs")
    ap.add_argument("--limit", type=int)
    ap.add_argument(
        "--quote-currency",
        type=str,
        default="none",  # ✅ safer daily default
        choices=["none", "missing", "all"],
        help="Fetch trading currency via yfinance Ticker().info (slow).",
    )
    ap.add_argument(
        "--min-batch-interval",
        type=float,
        default=float(os.environ.get("YF_MIN_BATCH_INTERVAL", "1.2")),
        help="Minimum seconds per batch (adaptive sleep).",
    )
    args = ap.parse_args()

    project_root = Path(__file__).resolve().parents[2]

    csv_path = Path(args.csv)
    if not csv_path.is_absolute():
        csv_path = (project_root / csv_path).resolve()

    price_cache_path = Path(args.price_cache)
    if not price_cache_path.is_absolute():
        price_cache_path = (project_root / price_cache_path).resolve()

    log_dir = Path(args.log_dir)
    if not log_dir.is_absolute():
        log_dir = (project_root / log_dir).resolve()
    _ensure_dir(log_dir)

    quote_ccy_cache_path = project_root / "cache" / "prices" / "quote_currency.json"

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"update_prices_cache_{ts}.log"
    logger = DualLogger(log_path)

    logger.write(f"Project root: {project_root}")
    logger.write(f"Universe CSV: {csv_path}")
    logger.write(f"Price cache:  {price_cache_path}")

    from infrastructure.repositories.csv_universe_loader_repository import CsvUniverseLoaderRepository
    from infrastructure.sources.yahoo_price_client import YahooPriceClient

    universe_repo = CsvUniverseLoaderRepository(csv_path)
    price_client = YahooPriceClient()
    price_repo = SqlitePriceRepository(db_path=str(price_cache_path))

    run(
        universe_repo=universe_repo,
        price_client=price_client,
        price_repo=price_repo,
        batch_size=args.batch_size,
        logger=logger,
        limit=args.limit,
        quote_ccy_cache_path=quote_ccy_cache_path,
        quote_ccy_mode=args.quote_currency,
        min_batch_interval_s=args.min_batch_interval,
    )


if __name__ == "__main__":
    main()
