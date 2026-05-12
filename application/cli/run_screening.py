# application/cli/run_screening.py
from __future__ import annotations
import argparse
import logging
from datetime import datetime
from pathlib import Path

from application.screening_service import ScreeningService
from infrastructure.repositories.sqlite_shortlist_repository import SqliteShortlistRepository
from infrastructure.repositories.sec_core_fs_repository import SecCoreFsRepository
from infrastructure.repositories.sqlite_insider_repository import SqliteInsiderRepository
from infrastructure.repositories.sqlite_screening_repository import SqliteScreeningRepository
from infrastructure.sources.yahoo_source import YahooSource # For FX if needed
from infrastructure.sources.yahoo_fx_provider import YahooFxProvider
from infrastructure.reporting.valuation_report_writer import CsvJsonValuationWriter


def _run_date(value: str) -> str:
    try:
        datetime.strptime(value, "%Y%m%d")
    except ValueError as exc:
        raise argparse.ArgumentTypeError("run date must use YYYYMMDD format") from exc
    return value


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    
    parser = argparse.ArgumentParser(description="Run Global Net-Net Screening")
    parser.add_argument("--db", type=str, default="data/db/filings.sqlite", help="Path to SQLite DB")
    parser.add_argument("--fx-cache", type=str, default="cache/fx/latest.json", help="Path to FX cache")
    parser.add_argument("--out-dir", type=str, default="public/reports", help="Output directory for reports")
    parser.add_argument("--run-date", type=_run_date, default=None, help="Screening snapshot date in YYYYMMDD format")
    args = parser.parse_args()

    db_path = args.db
    fx_cache = Path(args.fx_cache)
    public_dir = Path(args.out_dir)
    internal_dir = Path("reports/_internal")

    # Instantiate infrastructure using SQLite repositories
    shortlist_repo = SqliteShortlistRepository(db_path=db_path)
    core_repo = SecCoreFsRepository(db_path=db_path)
    insider_repo = SqliteInsiderRepository(db_path=db_path)
    
    # FX Provider: Consolidated to Yahoo Finance (Spot-Only)
    fx_provider = YahooFxProvider(cache_file=fx_cache)
    
    writer = CsvJsonValuationWriter(public_dir=public_dir, internal_dir=internal_dir)
    screening_repo = SqliteScreeningRepository(db_path=db_path)

    # Application service
    service = ScreeningService(
        shortlist_repo=shortlist_repo,
        core_repo=core_repo,
        insider_repo=insider_repo,
        fx_provider=fx_provider,
        writer=writer,
        screening_repo=screening_repo,
    )

    logging.info("Starting screening run from SQLite DB...")
    # For SQLite repo, 'shortlist_path' is ignored or used as a hint
    summary = service.screen_shortlist(Path("not_used_by_sqlite_repo"), run_date=args.run_date)
    
    paths = summary.output_paths
    logging.info(f"✅ Results saved: {paths.get('csv')}, {paths.get('json')}")
    logging.info(f"📊 Tickers screened: {summary.count}")

if __name__ == "__main__":
    main()
