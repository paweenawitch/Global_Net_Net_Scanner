from __future__ import annotations

import argparse
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable, Sequence


def _run_cmd(
    repo_root: Path,
    argv: Sequence[str],
    *,
    env_overrides: dict[str, str] | None = None,
) -> None:
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    print("[RUN]", " ".join(argv))
    proc = subprocess.run(argv, cwd=str(repo_root), env=env)
    if proc.returncode != 0:
        raise SystemExit(f"Command failed (rc={proc.returncode}): {' '.join(argv)}")


def _run_parallel_shards(
    repo_root: Path,
    *,
    python_exec: str,
    shard_count: int,
    shard_builder,
    env_overrides: dict[str, str] | None = None,
) -> None:
    if shard_count < 1:
        raise SystemExit("shard_count must be >= 1")
    jobs = [list(shard_builder(i, shard_count)) for i in range(1, shard_count + 1)]
    if shard_count == 1:
        _run_cmd(repo_root, jobs[0], env_overrides=env_overrides)
        return

    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=shard_count) as ex:
        futs = {
            ex.submit(_run_cmd, repo_root, job, env_overrides=env_overrides): idx + 1
            for idx, job in enumerate(jobs)
        }
        for fut in as_completed(futs):
            shard = futs[fut]
            try:
                fut.result()
            except Exception as e:
                failures.append(f"shard {shard}: {e}")
    if failures:
        raise SystemExit("; ".join(failures))


def run_daily(
    repo_root: Path,
    *,
    python_exec: str,
    universe_csv: str,
    price_batch_size: int,
    price_min_batch_interval: float,
) -> None:
    _run_cmd(
        repo_root,
        [
            python_exec,
            "-m",
            "application.cli.update_fx_cache",
            "--include-targets",
        ],
    )
    _run_cmd(
        repo_root,
        [
            python_exec,
            "-m",
            "application.cli.update_prices_cache",
            "--csv",
            universe_csv,
            "--batch-size",
            str(price_batch_size),
            "--min-batch-interval",
            str(price_min_batch_interval),
        ],
    )
    _run_cmd(
        repo_root,
        [
            python_exec,
            "-m",
            "application.cli.main_build_shortlist_cache_only",
            "--tickers_csv",
            universe_csv,
        ],
    )


def run_weekly(
    repo_root: Path,
    *,
    python_exec: str,
    universe_csv: str,
    ncav_shards: int,
    fetch_us_shards: int,
    fetch_nonus_shards: int,
    ncav_max_age_days: int,
    ncav_min_cache_interval_days: int,
    ncav_fetch_timeout: int,
) -> None:
    _run_cmd(repo_root, [python_exec, "-m", "application.cli.build_universe"])

    _run_parallel_shards(
        repo_root,
        python_exec=python_exec,
        shard_count=ncav_shards,
        shard_builder=lambda shard, of: [
            python_exec,
            "-m",
            "application.cli.update_ncav_cache",
            "--csv",
            universe_csv,
            "--max-age-days",
            str(ncav_max_age_days),
            "--min-cache-interval-days",
            str(ncav_min_cache_interval_days),
            "--fetch-timeout",
            str(ncav_fetch_timeout),
            "--shard",
            str(shard),
            "--of",
            str(of),
        ],
    )

    _run_parallel_shards(
        repo_root,
        python_exec=python_exec,
        shard_count=fetch_us_shards,
        shard_builder=lambda shard, of: [
            python_exec,
            "-m",
            "application.cli.main_fetch_full_cache",
            "--us-only",
            "--skip-insiders",
            "--no-parallel",
            "--us-core-shard",
            str(shard),
            "--us-core-of",
            str(of),
        ],
    )

    _run_parallel_shards(
        repo_root,
        python_exec=python_exec,
        shard_count=fetch_nonus_shards,
        shard_builder=lambda shard, of: [
            python_exec,
            "-m",
            "application.cli.main_fetch_full_cache",
            "--nonus-only",
            "--no-parallel",
            "--nonus-shard",
            str(shard),
            "--nonus-of",
            str(of),
        ],
    )

    _run_cmd(
        repo_root,
        [
            python_exec,
            "-m",
            "application.cli.main_fetch_full_cache",
            "--only",
            "US_INSIDERS",
            "--no-parallel",
        ],
    )


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Background update orchestrator for daily/weekly jobs.")
    parser.add_argument(
        "mode",
        choices=["daily", "weekly", "all"],
        help="daily: FX+prices+shortlist, weekly: universe+ncav+full cache, all: weekly then daily.",
    )
    parser.add_argument("--python", default=sys.executable, help="Python executable used for subcommands.")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent), help="Repository root path.")
    parser.add_argument("--universe-csv", default="data/tickers/global_full.csv")

    parser.add_argument("--ncav-shards", type=int, default=2)
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

    if args.mode in ("weekly", "all"):
        run_weekly(
            repo_root,
            python_exec=args.python,
            universe_csv=args.universe_csv,
            ncav_shards=args.ncav_shards,
            fetch_us_shards=args.fetch_us_shards,
            fetch_nonus_shards=args.fetch_nonus_shards,
            ncav_max_age_days=args.ncav_max_age_days,
            ncav_min_cache_interval_days=args.ncav_min_cache_interval_days,
            ncav_fetch_timeout=args.ncav_fetch_timeout,
        )

    if args.mode in ("daily", "all"):
        run_daily(
            repo_root,
            python_exec=args.python,
            universe_csv=args.universe_csv,
            price_batch_size=args.price_batch_size,
            price_min_batch_interval=args.price_min_batch_interval,
        )


if __name__ == "__main__":
    main()
