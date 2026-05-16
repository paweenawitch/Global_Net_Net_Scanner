from __future__ import annotations

import argparse
import csv
import logging
from pathlib import Path
from typing import Iterable, List, Optional

from infrastructure.sources.hkex_news_source import HKEXNewsSource

LOGGER = logging.getLogger("application.cli.fetch_hkex_filings")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_tickers(csv_path: Path) -> List[str]:
    if not csv_path.exists():
        raise SystemExit(f"Ticker CSV not found: {csv_path}")

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if "ticker" not in (reader.fieldnames or []):
            raise SystemExit("Ticker CSV must have a 'ticker' column.")

        tickers: List[str] = []
        seen: set[str] = set()
        for row in reader:
            ticker = str(row.get("ticker") or "").strip().upper()
            if not ticker or ticker in seen:
                continue
            seen.add(ticker)
            tickers.append(ticker)
        return tickers


def _select_hk_tickers(tickers: Iterable[str]) -> List[str]:
    return [ticker for ticker in tickers if ticker.upper().endswith(".HK")]


def _apply_shard(tickers: List[str], shard: int, of: int) -> List[str]:
    if of <= 1:
        return tickers
    if shard < 1 or shard > of:
        raise SystemExit("--shard must be between 1 and --of inclusive")
    return [ticker for idx, ticker in enumerate(tickers) if (idx % of) == (shard - 1)]


def run_cli(
    *,
    root: Optional[str] = None,
    csv_path: str = "data/tickers/hk_full.csv",
    tickers: Optional[Iterable[str]] = None,
    limit: Optional[int] = None,
    shard: int = 1,
    of: int = 1,
    verbose: bool = False,
) -> dict:
    project_root = Path(root).resolve() if root else _repo_root()
    source = HKEXNewsSource(filings_root=project_root / "data" / "filings" / "hkex")

    if tickers is None:
        selected = _load_tickers(project_root / csv_path)
    else:
        selected = [str(t).strip().upper() for t in tickers if str(t).strip()]

    selected = _select_hk_tickers(selected)
    selected = _apply_shard(selected, shard, of)
    if limit is not None:
        selected = selected[:limit]

    if not selected:
        print("No HK tickers to process after filtering.")
        return {"total": 0, "ok": 0, "error": 0}

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    results = {"total": len(selected), "ok": 0, "error": 0}
    for idx, ticker in enumerate(selected, start=1):
        try:
            record = source.fetch_ncav_record(ticker)
            results["ok"] += 1
            if verbose:
                LOGGER.info(
                    "[%s/%s] OK %s | fs_date=%s | ncav=%s | note=%s",
                    idx,
                    len(selected),
                    ticker,
                    record.statement_date,
                    record.ncav,
                    record.note,
                )
            else:
                LOGGER.info("[%s/%s] OK %s", idx, len(selected), ticker)
        except Exception as exc:
            results["error"] += 1
            LOGGER.error("[%s/%s] FAIL %s | %s: %s", idx, len(selected), ticker, type(exc).__name__, exc)

    LOGGER.info("HKEX fetch complete. %s", results)
    return results


def main(argv: Optional[Iterable[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Fetch latest HKEX financial reports for NCAV caching.")
    parser.add_argument("--root", type=str, default=None, help="Repository root. Defaults to this repo.")
    parser.add_argument("--csv", type=str, default="data/tickers/hk_full.csv", help="Ticker universe CSV path, relative to root.")
    parser.add_argument("--tickers", nargs="*", default=None, help="Optional explicit ticker list, bypassing CSV.")
    parser.add_argument("--limit", type=int, default=None, help="Limit the number of HK tickers to fetch.")
    parser.add_argument("--shard", type=int, default=1, help="Shard index (1-based).")
    parser.add_argument("--of", type=int, default=1, help="Total shard count.")
    parser.add_argument("--verbose", action="store_true", help="Log statement details.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    run_cli(
        root=args.root,
        csv_path=args.csv,
        tickers=args.tickers,
        limit=args.limit,
        shard=args.shard,
        of=args.of,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
