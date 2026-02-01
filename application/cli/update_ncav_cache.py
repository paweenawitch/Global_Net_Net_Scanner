#application/cli/update_ncav_cache.py
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional, Any, Dict, Tuple, List, Set


# -------------------------
# Time / paths / logging
# -------------------------

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


class DualLogger:
    """
    Print to console + append to log file.
    """
    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        _ensure_dir(log_path.parent)
        self.write(f"--- update_ncav_cache start {_utc_now_iso()} ---")

    def write(self, msg: str) -> None:
        line = f"{_utc_now_iso()} | {msg}"
        print(line)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


# -------------------------
# Refresh policies
# -------------------------

def _should_refresh_statement(statement_date: Optional[str], *, today: date, max_age_days: int) -> Tuple[bool, str]:
    """
    Statement freshness gate.
    """
    if not statement_date:
        return True, "missing_statement_date"
    try:
        age = (today - date.fromisoformat(statement_date)).days
        if age > max_age_days:
            return True, f"stale_statement_age_days={age}"
        return False, f"fresh_statement_age_days={age}"
    except Exception:
        return True, "bad_statement_date_format"


def _cache_file_path(house_ticker: str) -> Optional[Path]:
    """
    Derive cache file path from tools/ncav_cache.py convention:
      ROOT/cache/ncav/{house_ticker}.json
    """
    try:
        from tools.ncav_cache import CACHE  # Path
        return Path(CACHE) / f"{house_ticker}.json"
    except Exception:
        return None


def _cache_age_days(house_ticker: str, *, today: date) -> Optional[int]:
    """
    Use file mtime as "last fetched date". No schema change needed.
    """
    p = _cache_file_path(house_ticker)
    if p is None or not p.exists():
        return None
    try:
        mtime_dt = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).date()
        return (today - mtime_dt).days
    except Exception:
        return None


def _should_skip_due_to_recent_cache(house_ticker: str, *, today: date, min_cache_interval_days: int) -> Tuple[bool, str]:
    """
    Cache interval gate: skip refetch if file was updated recently.
    """
    if min_cache_interval_days <= 0:
        return False, "cache_interval_disabled"
    age = _cache_age_days(house_ticker, today=today)
    if age is None:
        return False, "cache_file_missing"
    if age < min_cache_interval_days:
        return True, f"recent_cache_age_days={age}"
    return False, f"cache_age_days={age}"


def _extract_filters(args) -> Tuple[Optional[Set[str]], Optional[Set[str]]]:
    countries = None
    mics = None
    if args.country:
        countries = {c.strip().upper() for c in args.country if c and c.strip()}
    if args.mic:
        mics = {m.strip().upper() for m in args.mic if m and m.strip()}
    return countries, mics


def _row_selected(row: Dict[str, Any], countries: Optional[Set[str]], mics: Optional[Set[str]]) -> bool:
    if countries is not None:
        rc = (row.get("country") or "").strip().upper()
        if rc not in countries:
            return False
    if mics is not None:
        rm = (row.get("mic") or "").strip().upper()
        if rm not in mics:
            return False
    return True


# -------------------------
# Job
# -------------------------

def run(
    *,
    universe_repo,
    max_age_days: int,
    fetch_timeout_s: int,
    limit: Optional[int],
    logger: DualLogger,
    verbose: bool,
    min_cache_interval_days: int,
    force: bool,
    force_all: bool,
    countries: Optional[Set[str]],
    mics: Optional[Set[str]],
) -> None:
    from tools import ncav_cache

    today = date.today()
    rows = universe_repo.load_tickers()

    # apply filters first (country/MIC)
    if countries is not None or mics is not None:
        before = len(rows)
        rows = [r for r in rows if _row_selected(r, countries, mics)]
        logger.write(f"Filtered universe: {before} -> {len(rows)} rows (country={countries} mic={mics})")

    if limit is not None:
        rows = rows[:limit]

    total = len(rows)
    logger.write(f"Universe rows selected: {total}")
    logger.write(f"Policy: statement max_age_days={max_age_days}")
    logger.write(f"Policy: min_cache_interval_days={min_cache_interval_days} (force={force}, force_all={force_all})")
    logger.write(f"Fetch timeout: {fetch_timeout_s}s")

    refreshed = 0
    skipped_recent = 0
    skipped_fresh_stmt = 0
    skipped_missing = 0
    failed = 0

    audit: Dict[str, Any] = {
        "started_at": _utc_now_iso(),
        "max_age_days": max_age_days,
        "min_cache_interval_days": min_cache_interval_days,
        "force": force,
        "force_all": force_all,
        "fetch_timeout_s": fetch_timeout_s,
        "limit": limit,
        "countries": sorted(list(countries)) if countries else None,
        "mics": sorted(list(mics)) if mics else None,
        "total_rows_selected": total,
        "refreshed": 0,
        "skipped_recent": 0,
        "skipped_fresh_stmt": 0,
        "skipped_missing": 0,
        "failed": 0,
    }

    for i, row in enumerate(rows, start=1):
        house_ticker = row.get("ticker")
        if not house_ticker:
            skipped_missing += 1
            if verbose:
                logger.write(f"[{i}/{total}] SKIP missing ticker")
            continue

        try:
            cached = ncav_cache.load_cached(house_ticker)
            fs_date = cached.statement_date if cached else None

            # Decide refresh
            if force_all:
                do_refresh, reason = True, "force_all"
            else:
                do_refresh, reason = _should_refresh_statement(fs_date, today=today, max_age_days=max_age_days)

                # If statement says refresh, still respect min-cache-interval unless --force
                if do_refresh and not force:
                    skip_recent, cache_reason = _should_skip_due_to_recent_cache(
                        house_ticker, today=today, min_cache_interval_days=min_cache_interval_days
                    )
                    if skip_recent:
                        do_refresh = False
                        reason = f"{reason} | {cache_reason}"
                        skipped_recent += 1

            if do_refresh:
                rec = ncav_cache.build_or_update(house_ticker, fetch_timeout=fetch_timeout_s)
                refreshed += 1
                if verbose:
                    logger.write(f"[{i}/{total}] REFRESH {house_ticker} | {reason} | stmt={rec.statement_date} sig={rec.statement_sig}")
                else:
                    logger.write(f"[{i}/{total}] REFRESH {house_ticker} | {reason}")
            else:
                # It was fresh statement OR skipped due to recent cache gate
                if "fresh_statement_age_days" in reason:
                    skipped_fresh_stmt += 1
                # recent-cache skips already counted above
                if verbose:
                    logger.write(f"[{i}/{total}] SKIP {house_ticker} | {reason} | stmt={fs_date}")

        except Exception as e:
            failed += 1
            logger.write(f"[{i}/{total}] FAIL {house_ticker} | {type(e).__name__}: {e}")

        if i % 100 == 0:
            logger.write(
                f"progress {i}/{total} | refreshed={refreshed} skipped_recent={skipped_recent} "
                f"skipped_fresh_stmt={skipped_fresh_stmt} skipped_missing={skipped_missing} failed={failed}"
            )

    audit["finished_at"] = _utc_now_iso()
    audit["refreshed"] = refreshed
    audit["skipped_recent"] = skipped_recent
    audit["skipped_fresh_stmt"] = skipped_fresh_stmt
    audit["skipped_missing"] = skipped_missing
    audit["failed"] = failed

    logger.write("--- SUMMARY ---")
    logger.write(f"refreshed={refreshed}")
    logger.write(f"skipped_recent={skipped_recent}")
    logger.write(f"skipped_fresh_stmt={skipped_fresh_stmt}")
    logger.write(f"skipped_missing={skipped_missing}")
    logger.write(f"failed={failed}")
    logger.write(f"total_selected={total}")
    logger.write("--- update_ncav_cache end ---")

    audit_path = logger.log_path.with_suffix(".json")
    audit_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="Path to universe CSV (absolute or project-relative)")
    ap.add_argument("--max-age-days", type=int, default=120)
    ap.add_argument("--min-cache-interval-days", type=int, default=7,
                    help="Skip refetch if cache file mtime is within N days (0 disables).")
    ap.add_argument("--fetch-timeout", type=int, default=25)
    ap.add_argument("--limit", type=int, default=None)

    ap.add_argument("--country", action="append", default=[],
                    help="Filter by country code (repeatable). Example: --country US --country JP")
    ap.add_argument("--mic", action="append", default=[],
                    help="Filter by MIC (repeatable). Example: --mic XNAS --mic XHKG")

    ap.add_argument("--force", action="store_true",
                    help="Ignore min-cache-interval gate when statement is stale/missing.")
    ap.add_argument("--force-all", action="store_true",
                    help="Refresh everything selected (ignores statement age AND cache interval).")

    ap.add_argument("--verbose", action="store_true", help="Log per-ticker SKIP lines too")
    ap.add_argument("--log-dir", type=str, default="logs", help="Directory for logs (project-relative)")
    args = ap.parse_args()

    # Resolve project root:
    project_root = Path(__file__).resolve().parents[2]

    csv_path = Path(args.csv)
    if not csv_path.is_absolute():
        csv_path = (project_root / csv_path).resolve()

    log_dir = Path(args.log_dir)
    if not log_dir.is_absolute():
        log_dir = (project_root / log_dir).resolve()
    _ensure_dir(log_dir)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"update_ncav_cache_{ts}.log"
    logger = DualLogger(log_path=log_path)

    countries, mics = _extract_filters(args)

    logger.write(f"Project root: {project_root}")
    logger.write(f"Universe CSV:  {csv_path}")
    logger.write(f"country={countries} mic={mics}")

    from infrastructure.repositories.csv_universe_loader_repository import CsvUniverseLoaderRepository
    universe_repo = CsvUniverseLoaderRepository(csv_path)

    run(
        universe_repo=universe_repo,
        max_age_days=args.max_age_days,
        fetch_timeout_s=args.fetch_timeout,
        limit=args.limit,
        logger=logger,
        verbose=args.verbose,
        min_cache_interval_days=args.min_cache_interval_days,
        force=args.force,
        force_all=args.force_all,
        countries=countries,
        mics=mics,
    )


if __name__ == "__main__":
    main()
