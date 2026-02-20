# application/cli/main_fetch_full_cache.py

import argparse
from pathlib import Path

from application.fetch_cache_orchestrator import FetchCacheOrchestrator, FetchConfig


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shortlist", help="Override shortlist CSV path (relative to repo root)")

    # backwards-compatible convenience flags
    ap.add_argument("--force-us-core", action="store_true", help="Pass --force to US_CORE job (if supported)")
    ap.add_argument("--us-only", action="store_true", help="Run only US jobs (US_CORE [+ US_INSIDERS])")
    ap.add_argument("--nonus-only", action="store_true", help="Run only NON_US job")
    ap.add_argument("--skip-insiders", action="store_true", help="Skip US_INSIDERS job")

    # generic filters (for power users / future markets)
    ap.add_argument("--only", nargs="*", help="Explicit list of job names to run (e.g. US_CORE NON_US)")
    ap.add_argument("--skip", nargs="*", help="Explicit list of job names to skip (e.g. US_INSIDERS)")

    ap.add_argument("--verbose", action="store_true")

    # job-level sharding controls
    ap.add_argument("--us-core-shard", type=int, default=0, help="US_CORE shard index (1-based)")
    ap.add_argument("--us-core-of", type=int, default=0, help="US_CORE number of shards")
    ap.add_argument("--nonus-shard", type=int, default=0, help="NON_US shard index (1-based)")
    ap.add_argument("--nonus-of", type=int, default=0, help="NON_US number of shards")

    # performance controls
    pg = ap.add_mutually_exclusive_group()
    pg.add_argument("--parallel", action="store_true", help="Run market jobs in parallel (default)")
    pg.add_argument("--no-parallel", action="store_true", help="Run market jobs sequentially")
    ap.add_argument("--max-parallel", type=int, default=0,
                    help="Max parallel jobs (default: min(8, number of jobs))")

    args = ap.parse_args()

    cfg = FetchConfig()
    if args.shortlist:
        # allow both absolute and relative paths; relative is from repo_root
        custom = Path(args.shortlist)
        cfg.shortlist_csv = custom if custom.is_absolute() else (cfg.repo_root / custom)

    orch = FetchCacheOrchestrator(cfg)

    # --- build ONLY / SKIP sets based on flags ---

    only: set[str] = set(args.only or [])
    skip: set[str] = set(args.skip or [])

    # convenience flags mapped to registry job names
    # NOTE: these assume your registry uses "US_CORE", "NON_US", "US_INSIDERS"
    if args.us_only and args.nonus_only:
        raise SystemExit("--us-only and --nonus-only are mutually exclusive")

    if args.us_only:
        # run both US core & insiders unless user explicitly skips insiders
        only.update({"US_CORE", "US_INSIDERS"})
    elif args.nonus_only:
        only.add("NON_US")

    if args.skip_insiders:
        skip.add("US_INSIDERS")

    # if "only" stays empty, orchestrator will just run all jobs
    only_arg = only or None
    skip_arg = skip or None

    # --- extra args per job (force-refresh, etc.) ---

    extra_args: dict[str, list[str]] = {}

    if args.force_us_core:
        extra_args.setdefault("US_CORE", []).append("--force")

    if args.us_core_shard or args.us_core_of:
        if args.us_core_shard < 1 or args.us_core_of < 1:
            raise SystemExit("--us-core-shard and --us-core-of must both be >= 1")
        if args.us_core_shard > args.us_core_of:
            raise SystemExit("--us-core-shard must be <= --us-core-of")
        extra_args.setdefault("US_CORE", []).extend(
            ["--shard", str(args.us_core_shard), "--of", str(args.us_core_of)]
        )

    if args.nonus_shard or args.nonus_of:
        if args.nonus_shard < 1 or args.nonus_of < 1:
            raise SystemExit("--nonus-shard and --nonus-of must both be >= 1")
        if args.nonus_shard > args.nonus_of:
            raise SystemExit("--nonus-shard must be <= --nonus-of")
        extra_args.setdefault("NON_US", []).extend(
            ["--shard", str(args.nonus_shard), "--of", str(args.nonus_of)]
        )

    extra_args_arg = extra_args or None

    # --- run orchestration ---

    orch.run_all(
        verbose=args.verbose,
        only=only_arg,
        skip=skip_arg,
        extra_args=extra_args_arg,
        parallel=(not args.no_parallel),  # default: parallel on
        max_workers=(args.max_parallel if args.max_parallel and args.max_parallel > 0 else None),
    )


if __name__ == "__main__":
    main()
