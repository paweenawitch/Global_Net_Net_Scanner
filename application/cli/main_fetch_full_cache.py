# application/cli/main_fetch_full_cache.py

import argparse
import logging
from pathlib import Path
from application.services.fetch_fundamentals_service import FetchFundamentalsService
from infrastructure.repositories.sqlite_shortlist_repository import SqliteShortlistRepository

def run_cli(
    *,
    shortlist: str = "data/db/filings.sqlite",
    skip_days: int = 7,
    force: bool = False,
    us_only: bool = False,
    nonus_only: bool = False,
    only: list[str] = [],
    shard: int = 1,
    of: int = 1,
    parallel: int = 4,
    verbose: bool = False,
) -> None:
    # 1. Paths
    root = Path(__file__).resolve().parents[2]
    db_path = root / shortlist
    
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")

    # 2. Load Tickers
    repo = SqliteShortlistRepository(db_path=str(db_path))
    items = repo.load_shortlist()
    
    tickers = [str(item.ticker).strip().upper() for item in items if item.ticker]
    
    # 3. Apply Filters
    if us_only:
        tickers = [t for t in tickers if t.endswith(".US")]
    elif nonus_only:
        tickers = [t for t in tickers if not t.endswith(".US")]
    
    if only:
        want = {t.strip().upper() for t in only}
        tickers = [t for t in tickers if t in want]

    if not tickers:
        print("No tickers to process after filtering.")
        return

    # 4. Run Service
    logging.basicConfig(
        level=logging.INFO if not verbose else logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    
    svc = FetchFundamentalsService(root)
    svc.run_all(
        tickers=tickers,
        skip_days=skip_days,
        force=force,
        max_workers=parallel,
        shard=shard,
        of=of,
        verbose=verbose
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shortlist", default="data/db/filings.sqlite")
    ap.add_argument("--skip-days", type=int, default=7)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--us-only", action="store_true")
    ap.add_argument("--nonus-only", action="store_true")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--shard", type=int, default=1, help="Shard index (1-based)")
    ap.add_argument("--of", type=int, default=1, help="Total shards")
    ap.add_argument("--parallel", type=int, default=4)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    run_cli(
        shortlist=args.shortlist,
        skip_days=args.skip_days,
        force=args.force,
        us_only=args.us_only,
        nonus_only=args.nonus_only,
        only=args.only or [],
        shard=args.shard,
        of=args.of,
        parallel=args.parallel,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
