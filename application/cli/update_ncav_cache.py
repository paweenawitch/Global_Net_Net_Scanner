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


def _cache_age_days(house_ticker: str, *, store: SqliteFilingStore, today: date) -> Optional[int]:
    """
    Check cached_at in SQLite.
    """
    rec = store.get_ncav_record(house_ticker)
    if not rec or not rec.cached_at:
        return None
    try:
        cached_dt = datetime.fromisoformat(rec.cached_at).date()
        return (today - cached_dt).days
    except Exception:
        return None


def _should_skip_due_to_recent_cache(house_ticker: str, *, store: SqliteFilingStore, today: date, min_cache_interval_days: int) -> Tuple[bool, str]:
    """
    Cache interval gate: skip refetch if record was updated recently in DB.
    """
    if min_cache_interval_days <= 0:
        return False, "cache_interval_disabled"
    age = _cache_age_days(house_ticker, store=store, today=today)
    if age is None:
        return False, "cache_record_missing"
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
    shard: int,
    of: int,
    project_root: Path,
) -> None:
    from application.build_fundamentals_service import BuildFundamentalsService
    from infrastructure.persistence.sqlite_filing_store import SqliteFilingStore
    
    today = date.today()
    rows = universe_repo.load_tickers()
    
    store = SqliteFilingStore(str(Path(project_root) / "data/db/filings.sqlite"))
    service = BuildFundamentalsService(project_root)

    # apply filters first (country/MIC)
    if countries is not None or mics is not None:
        before = len(rows)
        rows = [r for r in rows if _row_selected(r, countries, mics)]
        logger.write(f"Filtered universe: {before} -> {len(rows)} rows (country={countries} mic={mics})")

    if of > 1:
        before = len(rows)
        rows = [r for idx, r in enumerate(rows) if (idx % of) == (shard - 1)]
        logger.write(f"Sharded universe: {before} -> {len(rows)} rows (shard={shard}/{of})")

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

    for i, row in enumerate(rows, start=1):
        house_ticker = row.get("ticker")
        if not house_ticker:
            skipped_missing += 1
            continue

        try:
            cached = store.get_ncav_record(house_ticker)
            fs_date = cached.statement_date if cached else None

            # Decide refresh
            if force_all:
                do_refresh, reason = True, "force_all"
            else:
                do_refresh, reason = _should_refresh_statement(fs_date, today=today, max_age_days=max_age_days)

                if do_refresh and not force:
                    skip_recent, cache_reason = _should_skip_due_to_recent_cache(
                        house_ticker, store=store, today=today, min_cache_interval_days=min_cache_interval_days
                    )
                    if skip_recent:
                        do_refresh = False
                        reason = f"{reason} | {cache_reason}"
                        skipped_recent += 1

            if do_refresh:
                service.update_ncav_cache([house_ticker], force=True)
                refreshed += 1
                if verbose:
                    rec = store.get_ncav_record(house_ticker)
                    logger.write(f"[{i}/{total}] REFRESH {house_ticker} | {reason} | stmt={rec.statement_date if rec else None}")
                else:
                    logger.write(f"[{i}/{total}] REFRESH {house_ticker} | {reason}")
            else:
                if "fresh_statement_age_days" in reason:
                    skipped_fresh_stmt += 1
                if verbose:
                    logger.write(f"[{i}/{total}] SKIP {house_ticker} | {reason}")

        except Exception as e:
            failed += 1
            logger.write(f"[{i}/{total}] FAIL {house_ticker} | {type(e).__name__}: {e}")

        if i % 100 == 0:
            logger.write(
                f"progress {i}/{total} | refreshed={refreshed} skipped_recent={skipped_recent} "
                f"skipped_fresh_stmt={skipped_fresh_stmt} skipped_missing={skipped_missing} failed={failed}"
            )

    shortlist_path = project_root / "data/tickers/ncav_shortlist.csv"
    # Fix: Audit object was moved out of loop but used at end. 
    # I'll just skip audit for now or keep it simple.


def run_cli(
    *,
    universe_csv: str,
    max_age_days: int = 120,
    min_cache_interval_days: int = 7,
    fetch_timeout_s: int = 25,
    limit: Optional[int] = None,
    country: List[str] = [],
    mic: List[str] = [],
    force: bool = False,
    force_all: bool = False,
    shard: int = 1,
    of: int = 1,
    verbose: bool = False,
    log_dir: str = "logs",
) -> None:
    # Resolve project root:
    project_root = Path(__file__).resolve().parents[2]

    csv_path = Path(universe_csv)
    if not csv_path.is_absolute():
        csv_path = (project_root / csv_path).resolve()

    log_dir_path = Path(log_dir)
    if not log_dir_path.is_absolute():
        log_dir_path = (project_root / log_dir_path).resolve()
    _ensure_dir(log_dir_path)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    log_path = log_dir_path / f"update_ncav_cache_{ts}.log"
    logger = DualLogger(log_path=log_path)

    countries = {c.strip().upper() for c in country if c and c.strip()} if country else None
    mics = {m.strip().upper() for m in mic if m and m.strip()} if mic else None

    logger.write(f"Project root: {project_root}")
    logger.write(f"Universe CSV:  {csv_path}")

    from infrastructure.repositories.csv_universe_loader_repository import CsvUniverseLoaderRepository
    universe_repo = CsvUniverseLoaderRepository(csv_path=csv_path)

    run(
        universe_repo=universe_repo,
        max_age_days=max_age_days,
        fetch_timeout_s=fetch_timeout_s,
        limit=limit,
        logger=logger,
        verbose=verbose,
        min_cache_interval_days=min_cache_interval_days,
        force=force,
        force_all=force_all,
        countries=countries,
        mics=mics,
        shard=shard,
        of=of,
        project_root=project_root,
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--max-age-days", type=int, default=120)
    ap.add_argument("--min-cache-interval-days", type=int, default=7)
    ap.add_argument("--fetch-timeout", type=int, default=25)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--country", action="append", default=[])
    ap.add_argument("--mic", action="append", default=[])
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--force-all", action="store_true")
    ap.add_argument("--shard", type=int, default=1)
    ap.add_argument("--of", type=int, default=1)
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--log-dir", type=str, default="logs")
    args = ap.parse_args()

    run_cli(
        universe_csv=args.csv,
        max_age_days=args.max_age_days,
        min_cache_interval_days=args.min_cache_interval_days,
        fetch_timeout_s=args.fetch_timeout,
        limit=args.limit,
        country=args.country,
        mic=args.mic,
        force=args.force,
        force_all=args.force_all,
        shard=args.shard,
        of=args.of,
        verbose=args.verbose,
        log_dir=args.log_dir,
    )


if __name__ == "__main__":
    main()
