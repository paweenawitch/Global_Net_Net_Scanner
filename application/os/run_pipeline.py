from __future__ import annotations

from typing import Any, Dict

# Import the CLI modules
from application.cli import (
    update_fx_cache,
    update_prices_cache,
    main_build_shortlist_cache_only,
    update_ncav_cache,
    main_fetch_full_cache,
    build_universe,
)

from application.os.data_inspection import DataInspectionService
from application.os.maintenance_audit import MaintenanceAuditService

def run_fx_update(params: Dict[str, Any]) -> Dict[str, Any]:
    update_fx_cache.run_cli(
        include_targets=params.get("include_targets", False),
        force=params.get("force", False),
    )
    return {"status": "SUCCESS"}

def run_prices_update(params: Dict[str, Any]) -> Dict[str, Any]:
    update_prices_cache.run_cli(
        universe_csv=params["universe_csv"],
        batch_size=params.get("batch_size", 50),
        min_batch_interval=params.get("min_batch_interval", 1.2),
        quote_currency=params.get("quote_currency", "none"),
    )
    return {"status": "SUCCESS"}

def run_build_shortlist(params: Dict[str, Any]) -> Dict[str, Any]:
    main_build_shortlist_cache_only.run_cli(
        tickers_csv=params["universe_csv"],
    )
    return {"status": "SUCCESS"}

def run_build_universe(params: Dict[str, Any]) -> Dict[str, Any]:
    build_universe.run_cli()
    return {"status": "SUCCESS"}

def run_ncav_update(params: Dict[str, Any]) -> Dict[str, Any]:
    update_ncav_cache.run_cli(
        universe_csv=params["universe_csv"],
        max_age_days=params.get("max_age_days", 120),
        min_cache_interval_days=params.get("min_cache_interval_days", 7),
        fetch_timeout_s=params.get("fetch_timeout", 25),
        shard=params.get("shard", 1),
        of=params.get("of", 1),
    )
    return {"status": "SUCCESS"}

def run_fetch_full_cache(params: Dict[str, Any]) -> Dict[str, Any]:
    main_fetch_full_cache.run_cli(
        us_only=params.get("us_only", False),
        nonus_only=params.get("nonus_only", False),
        only=params.get("only", []),
        shard=params.get("shard", 1),
        of=params.get("of", 1),
        parallel=params.get("parallel", 4),
    )
    return {"status": "SUCCESS"}

def run_data_inspection(params: Dict[str, Any]) -> Dict[str, Any]:
    from infrastructure.persistence.sqlite_os_state_store import SqliteOsStateStore
    store = SqliteOsStateStore(params["walter_db"])
    svc = DataInspectionService(
        filings_db=params["filings_db"],
        market_db=params["market_db"],
        state_store=store
    )
    res = svc.run_all(limit=params.get("limit"))
    return {"status": "SUCCESS", "findings": res.findings_created_or_updated}

def run_maintenance_audit(params: Dict[str, Any]) -> Dict[str, Any]:
    from infrastructure.persistence.sqlite_os_state_store import SqliteOsStateStore
    store = SqliteOsStateStore(params["walter_db"])
    svc = MaintenanceAuditService(
        state_store=store,
        db_paths=params["db_paths"]
    )
    res = svc.run_audit()
    return {"status": "SUCCESS", "db_stats": res.db_stats}
