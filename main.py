from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable

from infrastructure.persistence.sqlite_os_state_store import SqliteOsStateStore
from infrastructure.scheduler.lock_manager import TaskLockManager
from application.os.task_registry import TaskRegistry
from application.os.task_runner import TaskRunner
from application.os.task_specs import TaskSpec
from application.os import run_pipeline

class Walter:
    def __init__(self, db_path: str):
        self.store = SqliteOsStateStore(db_path)
        self.lock_manager = TaskLockManager(self.store, lock_owner="main_process")
        self.registry = TaskRegistry()
        self._register_pipelines()
        self.runner = TaskRunner(self.registry, self.store, self.lock_manager)

    def _register_pipelines(self):
        self.registry.register("refresh_fx", run_pipeline.run_fx_update)
        self.registry.register("refresh_prices", run_pipeline.run_prices_update)
        self.registry.register("build_shortlist", run_pipeline.run_build_shortlist)
        self.registry.register("build_universe", run_pipeline.run_build_universe)
        self.registry.register("update_ncav", run_pipeline.run_ncav_update)
        self.registry.register("fetch_full", run_pipeline.run_fetch_full_cache)
        self.registry.register("inspect_data", run_pipeline.run_data_inspection)
        self.registry.register("run_audit", run_pipeline.run_maintenance_audit)

    def run_daily_cycle(self, universe_csv: str, price_batch_size: int, price_min_batch_interval: float):
        print(">>> Starting Walter Daily Cycle")
        # 1. FX
        self.runner.run_task(spec=TaskSpec(task_name="daily_fx", pipeline="refresh_fx", params={"include_targets": True}))
        # 2. Prices
        self.runner.run_task(spec=TaskSpec(task_name="daily_prices", pipeline="refresh_prices", params={
            "universe_csv": universe_csv,
            "batch_size": price_batch_size,
            "min_batch_interval": price_min_batch_interval
        }))
        # 3. Shortlist
        self.runner.run_task(spec=TaskSpec(task_name="daily_shortlist", pipeline="build_shortlist", params={"universe_csv": universe_csv}))
        
        # 4. Self-Audit (Internal Health)
        self.runner.run_task(spec=TaskSpec(task_name="daily_audit", pipeline="run_audit", params={
            "walter_db": self.store.db_path,
            "db_paths": ["data/db/filings.sqlite", "data/db/market_snapshots.sqlite", self.store.db_path]
        }))
        print("<<< Walter Daily Cycle Finished")

    def run_weekly_cycle(
        self,
        universe_csv: str,
        ncav_shards: int,
        fetch_us_shards: int,
        fetch_nonus_shards: int,
        ncav_max_age_days: int,
        ncav_min_cache_interval_days: int,
        ncav_fetch_timeout: int,
        ncav_regional: bool = False,
    ):
        print(">>> Starting Walter Weekly Cycle")
        repo_root = Path(universe_csv).parent.parent.parent # d:/Projects/.../data/tickers

        # 1. Universe
        self.runner.run_task(spec=TaskSpec(task_name="weekly_universe", pipeline="build_universe"))

        # 2. NCAV Shards or Regional Parallelism
        if ncav_regional:
            regional_files = sorted(Path(repo_root / "data" / "tickers").glob("*_full.csv"))
            # Filter out global_full.csv if present
            regional_files = [f for f in regional_files if f.name != "global_full.csv"]
            
            print(f"> Running {len(regional_files)} regional NCAV updates in parallel: {[f.name for f in regional_files]}")
            with ThreadPoolExecutor(max_workers=len(regional_files)) as ex:
                futs = []
                for csv_path in regional_files:
                    region = csv_path.name.replace("_full.csv", "").upper()
                    spec = TaskSpec(
                        task_name=f"weekly_ncav_{region}",
                        pipeline="update_ncav",
                        params={
                            "universe_csv": str(csv_path),
                            "max_age_days": ncav_max_age_days,
                            "min_cache_interval_days": ncav_min_cache_interval_days,
                            "fetch_timeout": ncav_fetch_timeout,
                        }
                    )
                    futs.append(ex.submit(self.runner.run_task, spec=spec))
                for fut in as_completed(futs):
                    fut.result()
        else:
            print(f"> Running {ncav_shards} NCAV shards in parallel")
            with ThreadPoolExecutor(max_workers=ncav_shards) as ex:
                futs = []
                for i in range(1, ncav_shards + 1):
                    spec = TaskSpec(
                        task_name=f"weekly_ncav_shard_{i}",
                        pipeline="update_ncav",
                        params={
                            "universe_csv": universe_csv,
                            "max_age_days": ncav_max_age_days,
                            "min_cache_interval_days": ncav_min_cache_interval_days,
                            "fetch_timeout": ncav_fetch_timeout,
                            "shard": i,
                            "of": ncav_shards
                        }
                    )
                    futs.append(ex.submit(self.runner.run_task, spec=spec))
                for fut in as_completed(futs):
                    fut.result()

        # 3. Full Fetch US Shards (Parallel)
        print(f"> Running {fetch_us_shards} US fetch shards in parallel")
        with ThreadPoolExecutor(max_workers=fetch_us_shards) as ex:
            futs = []
            for i in range(1, fetch_us_shards + 1):
                spec = TaskSpec(
                    task_name=f"weekly_fetch_us_shard_{i}",
                    pipeline="fetch_full",
                    params={
                        "us_only": True,
                        "shard": i,
                        "of": fetch_us_shards
                    }
                )
                futs.append(ex.submit(self.runner.run_task, spec=spec))
            for fut in as_completed(futs):
                fut.result()

        # 4. Full Fetch Non-US Shards (Parallel)
        print(f"> Running {fetch_nonus_shards} Non-US fetch shards in parallel")
        with ThreadPoolExecutor(max_workers=fetch_nonus_shards) as ex:
            futs = []
            for i in range(1, fetch_nonus_shards + 1):
                spec = TaskSpec(
                    task_name=f"weekly_fetch_nonus_shard_{i}",
                    pipeline="fetch_full",
                    params={
                        "nonus_only": True,
                        "shard": i,
                        "of": fetch_nonus_shards
                    }
                )
                futs.append(ex.submit(self.runner.run_task, spec=spec))
            for fut in as_completed(futs):
                fut.result()

        # 5. US Insiders
        self.runner.run_task(spec=TaskSpec(task_name="weekly_fetch_insiders", pipeline="fetch_full", params={"only": ["US_INSIDERS"]}))

        # 6. Data Inspection (Intelligence Phase 2)
        print("> Running Data Integrity Inspection (Flagging Only)")
        self.runner.run_task(spec=TaskSpec(task_name="weekly_inspection", pipeline="inspect_data", params={
            "walter_db": self.store.db_path,
            "filings_db": "data/db/filings.sqlite",
            "market_db": "data/db/market_snapshots.sqlite",
            "limit": 1000
        }))
        print("<<< Walter Weekly Cycle Finished")

def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Walter OS Orchestrator for Global Net-Net Scanner.")
    parser.add_argument(
        "mode",
        choices=["daily", "weekly", "all"],
        help="daily: FX+prices+shortlist, weekly: universe+ncav+full cache, all: weekly then daily.",
    )
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent), help="Repository root path.")
    parser.add_argument("--universe-csv", default="data/tickers/global_full.csv")
    parser.add_argument("--db", default="data/db/walter_os.sqlite", help="Path to Walter OS state DB.")

    parser.add_argument("--ncav-shards", type=int, default=2)
    parser.add_argument("--ncav-regional", action="store_true", help="If set, detect and run regional *_full.csv files in parallel instead of sharding.")
    parser.add_argument("--fetch-us-shards", type=int, default=2)
    parser.add_argument("--fetch-nonus-shards", type=int, default=2)

    parser.add_argument("--ncav-max-age-days", type=int, default=120)
    parser.add_argument("--ncav-min-cache-interval-days", type=int, default=7)
    parser.add_argument("--ncav-fetch-timeout", type=int, default=25)

    parser.add_argument("--price-batch-size", type=int, default=50)
    parser.add_argument("--price-min-batch-interval", type=float, default=1.2)
    args = parser.parse_args(list(argv) if argv is not None else None)

    repo_root = Path(args.root).resolve()
    if not repo_root.exists():
        raise SystemExit(f"Root does not exist: {repo_root}")

    # Ensure DB parent exists
    db_path = Path(args.db)
    if not db_path.is_absolute():
        db_path = (repo_root / db_path).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    walter = Walter(db_path=str(db_path))

    if args.mode in ("weekly", "all"):
        walter.run_weekly_cycle(
            universe_csv=args.universe_csv,
            ncav_shards=args.ncav_shards,
            fetch_us_shards=args.fetch_us_shards,
            fetch_nonus_shards=args.fetch_nonus_shards,
            ncav_max_age_days=args.ncav_max_age_days,
            ncav_min_cache_interval_days=args.ncav_min_cache_interval_days,
            ncav_fetch_timeout=args.ncav_fetch_timeout,
            ncav_regional=args.ncav_regional,
        )

    if args.mode in ("daily", "all"):
        walter.run_daily_cycle(
            universe_csv=args.universe_csv,
            price_batch_size=args.price_batch_size,
            price_min_batch_interval=args.price_min_batch_interval,
        )

if __name__ == "__main__":
    main()
