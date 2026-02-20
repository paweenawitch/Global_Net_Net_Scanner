#application/cli/update_fx_cache.py
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Dict, Optional, Set, List, Any


# -------------------------
# Time / logging / IO
# -------------------------

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


class DualLogger:
    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        _ensure_dir(log_path.parent)
        self.write(f"--- update_fx_cache start {_utc_now_iso()} ---")

    def write(self, msg: str) -> None:
        line = f"{_utc_now_iso()} | {msg}"
        print(line)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def _atomic_write_json(path: Path, obj: Any) -> None:
    _ensure_dir(path.parent)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


# -------------------------
# Currency aliasing (Yahoo quirks)
# -------------------------

# Yahoo FX: prefer CNY ticker; normalize CNH requests to CNY.
# We still backfill both CNY and CNH in output rates for downstream compatibility.
_CCY_ALIAS = {
    "CNH": "CNY",
    # You can add more aliases if you encounter them.
}

def _normalize_ccy_for_fetch(ccy: str) -> str:
    c = (ccy or "").upper().strip()
    return _CCY_ALIAS.get(c, c)


def _backfill_aliases_in_rates(rates: Dict[str, float]) -> Dict[str, float]:
    """
    Publish both CNY and CNH using the same rate (USD per CCY) when either exists.
    This prevents downstream mismatches across data sources.
    """
    out = dict(rates)
    if "CNY" in out and "CNH" not in out:
        out["CNH"] = out["CNY"]
    if "CNH" in out and "CNY" not in out:
        out["CNY"] = out["CNH"]
    return out


# -------------------------
# Ticker suffix -> likely trading currency
# (keep consistent with your shortlist logic intent)
# -------------------------

def _target_currency_from_ticker(ticker: str) -> Optional[str]:
    t = (ticker or "").upper().strip()

    if t.endswith(".US"):
        return "USD"
    if t.endswith(".HK"):
        return "HKD"
    if t.endswith(".JP"):
        return "JPY"
    if t.endswith(".TH"):
        return "THB"
    if t.endswith(".SG"):
        return "SGD"
    if t.endswith(".KR"):
        return "KRW"
    if t.endswith(".TW"):
        return "TWD"
    if t.endswith(".AU"):
        return "AUD"
    if t.endswith(".CA"):
        return "CAD"
    if t.endswith(".GB") or t.endswith(".L"):
        return "GBP"

    # Common EUR venues
    if t.endswith(".DE") or t.endswith(".FR") or t.endswith(".IT") or t.endswith(".ES") or t.endswith(".NL"):
        return "EUR"

    return None


# -------------------------
# Cache scanning + skip policy
# -------------------------

def _age_days_from_mtime(path: Path) -> Optional[int]:
    if not path.exists():
        return None
    try:
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).date()
        return (date.today() - mtime).days
    except Exception:
        return None


def _should_skip_due_to_recent_fx_cache(out_path: Path, min_cache_interval_days: int) -> tuple[bool, str]:
    if min_cache_interval_days <= 0:
        return False, "fx_cache_interval_disabled"
    age = _age_days_from_mtime(out_path)
    if age is None:
        return False, "fx_cache_missing"
    if age < min_cache_interval_days:
        return True, f"fx_cache_recent_age_days={age}"
    return False, f"fx_cache_age_days={age}"


def _scan_currencies_from_ncav_cache(
    cache_dir: Path,
    *,
    include_targets: bool,
    limit_files: Optional[int],
    logger: DualLogger,
) -> tuple[Set[str], int]:
    """
    Discover currencies by scanning cached NCAV records on disk.

    Source of truth:
      - file stems (house ticker)
      - tools.ncav_cache.load_cached(ticker) -> rec.currency (FS currency)
      - optional target trading currency inferred from ticker suffix
    """
    from tools import ncav_cache  # uses your existing cache loader

    needed: Set[str] = set(["USD"])
    files = sorted(cache_dir.glob("*.json"))
    if limit_files is not None:
        files = files[:limit_files]

    missing_or_bad = 0

    for fp in files:
        ht = fp.stem  # house ticker
        try:
            rec = ncav_cache.load_cached(ht)
        except Exception:
            rec = None

        if rec is None:
            missing_or_bad += 1
            # Still can include target currency if asked
            if include_targets:
                tc = _target_currency_from_ticker(ht)
                if tc:
                    needed.add(_normalize_ccy_for_fetch(tc))
            continue

        # FS currency
        if getattr(rec, "currency", None):
            needed.add(_normalize_ccy_for_fetch(str(rec.currency)))

        # Target trading currency
        if include_targets:
            tc = _target_currency_from_ticker(ht)
            if tc:
                needed.add(_normalize_ccy_for_fetch(tc))

    logger.write(f"Scanned cache files: {len(files)} (missing/bad records: {missing_or_bad})")
    return needed, missing_or_bad


# -------------------------
# Main job
# -------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-dir", type=str, default="", help="NCAV cache dir (default: tools.ncav_cache.CACHE)")
    ap.add_argument("--out", type=str, default="cache/fx/usd_per_ccy.json", help="Output FX cache path (project-relative ok)")
    ap.add_argument("--log-dir", type=str, default="logs")
    ap.add_argument("--include-targets", action="store_true", help="Also include implied trading currencies from ticker suffix")
    ap.add_argument("--limit-files", type=int, default=None, help="Limit number of NCAV cache files scanned (debug)")
    ap.add_argument("--min-cache-interval-days", type=int, default=1,
                    help="Skip updating FX cache if output file was updated within N days (0 disables).")
    ap.add_argument("--force", action="store_true", help="Ignore min-cache-interval gate")
    args = ap.parse_args()

    project_root = Path(__file__).resolve().parents[2]

    # Resolve NCAV cache dir
    if args.cache_dir:
        cache_dir = Path(args.cache_dir)
        if not cache_dir.is_absolute():
            cache_dir = (project_root / cache_dir).resolve()
    else:
        from tools.ncav_cache import CACHE
        cache_dir = Path(CACHE)

    # Resolve outputs
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = (project_root / out_path).resolve()

    log_dir = Path(args.log_dir)
    if not log_dir.is_absolute():
        log_dir = (project_root / log_dir).resolve()
    _ensure_dir(log_dir)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"update_fx_cache_{ts}.log"
    logger = DualLogger(log_path)

    logger.write(f"Project root: {project_root}")
    logger.write(f"NCAV cache dir: {cache_dir}")
    logger.write(f"FX out: {out_path}")
    logger.write(f"include_targets={args.include_targets} limit_files={args.limit_files}")
    logger.write(f"min_cache_interval_days={args.min_cache_interval_days} force={args.force}")

    if not cache_dir.exists():
        logger.write(f"ERROR: cache dir not found: {cache_dir}")
        raise FileNotFoundError(f"NCAV cache dir not found: {cache_dir}")

    # Optional: skip if FX cache recently updated
    if not args.force:
        skip, reason = _should_skip_due_to_recent_fx_cache(out_path, args.min_cache_interval_days)
        if skip:
            logger.write(f"SKIP: {reason} (use --force to override)")
            logger.write("--- update_fx_cache end ---")
            return
        logger.write(f"FX cache gate: {reason}")

    needed_ccy, missing = _scan_currencies_from_ncav_cache(
        cache_dir,
        include_targets=args.include_targets,
        limit_files=args.limit_files,
        logger=logger,
    )

    needed_list = sorted(needed_ccy)
    logger.write(f"Currencies needed (normalized for fetch): {len(needed_list)}")
    logger.write(f"Sample: {needed_list[:30]}{'...' if len(needed_list) > 30 else ''}")

    # Fetch FX
    from infrastructure.sources.yahoo_fx_provider import YahooFxProvider
    fx = YahooFxProvider()

    started = _utc_now_iso()
    fx_map = fx.usd_per_ccy(needed_list)
    fx_map = {str(k).upper(): float(v) for k, v in fx_map.items()}
    fx_map.setdefault("USD", 1.0)

    # Backfill aliases (CNH -> CNY)
    fx_map = _backfill_aliases_in_rates(fx_map)

    payload = {
        "asof_utc": _utc_now_iso(),
        "started_utc": started,
        "source": "yahoo",
        "units": "usd_per_ccy",
        "notes": {
            "aliases": _CCY_ALIAS,
            "alias_behavior": "fetch normalized currency; publish both CNY and CNH when either is available",
        },
        "inputs": {
            "cache_dir": str(cache_dir),
            "include_targets": args.include_targets,
            "limit_files": args.limit_files,
            "missing_or_bad_records": missing,
        },
        "requested_ccy": needed_list,
        "returned_ccy": sorted(fx_map.keys()),
        "rates": dict(sorted(fx_map.items())),
    }

    _atomic_write_json(out_path, payload)

    missing_ccy = sorted(set(needed_list) - set([c for c in fx_map.keys()]))
    audit = {
        "finished_utc": _utc_now_iso(),
        "out": str(out_path),
        "requested_ccy": len(needed_list),
        "returned_ccy": len(fx_map),
        "missing_ccy": missing_ccy[:200],
        "log": str(log_path),
    }
    audit_path = out_path.with_suffix(".audit.json")
    _atomic_write_json(audit_path, audit)

    logger.write("--- SUMMARY ---")
    logger.write(f"requested_ccy={audit['requested_ccy']}")
    logger.write(f"returned_ccy={audit['returned_ccy']}")
    if audit["missing_ccy"]:
        logger.write(f"missing_ccy_sample={audit['missing_ccy'][:20]}")
    logger.write(f"wrote={out_path}")
    logger.write(f"audit={audit_path}")
    logger.write("--- update_fx_cache end ---")


if __name__ == "__main__":
    main()
