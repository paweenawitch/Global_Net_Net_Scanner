# application/cli/run_screening.py
from __future__ import annotations
import argparse
import logging
from pathlib import Path

from application.screening_service import ScreeningService
from infrastructure.repositories.sqlite_shortlist_repository import SqliteShortlistRepository
from infrastructure.repositories.sec_core_fs_repository import SecCoreFsRepository
from infrastructure.repositories.sqlite_insider_repository import SqliteInsiderRepository
from infrastructure.sources.yahoo_source import YahooSource # For FX if needed
from infrastructure.fx.exchangerate_host_provider import ExchangerateHostFxProvider
from infrastructure.reporting.valuation_report_writer import CsvJsonValuationWriter

def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    
    parser = argparse.ArgumentParser(description="Run Global Net-Net Screening")
    parser.add_argument("--db", type=str, default="data/db/filings.sqlite", help="Path to SQLite DB")
    parser.add_argument("--fx-cache", type=str, default="cache/fx/latest.json", help="Path to FX cache")
    parser.add_argument("--out-dir", type=str, default="public/reports", help="Output directory for reports")
    args = parser.parse_args()

    db_path = args.db
    fx_cache = Path(args.fx_cache)
    public_dir = Path(args.out_dir)
    internal_dir = Path("reports/_internal")

    # Instantiate infrastructure using SQLite repositories
    shortlist_repo = SqliteShortlistRepository(db_path=db_path)
    core_repo = SecCoreFsRepository(db_path=db_path)
    insider_repo = SqliteInsiderRepository(db_path=db_path)
    
    # FX Provider (can be refactored further later, but for now we use existing one)
    fx_provider = ExchangerateHostFxProvider(cache_file=fx_cache)
    
    writer = CsvJsonValuationWriter(public_dir=public_dir, internal_dir=internal_dir)

    # Application service
    service = ScreeningService(
        shortlist_repo=shortlist_repo,
        core_repo=core_repo,
        insider_repo=insider_repo,
        fx_provider=fx_provider,
        writer=writer,
    )

    logging.info("Starting screening run from SQLite DB...")
    # For SQLite repo, 'shortlist_path' is ignored or used as a hint
    summary = service.screen_shortlist(Path("not_used_by_sqlite_repo"))
    
    paths = summary.output_paths
    logging.info(f"✅ Results saved: {paths.get('csv')}, {paths.get('json')}")
    logging.info(f"📊 Tickers screened: {summary.count}")

if __name__ == "__main__":
    main()
