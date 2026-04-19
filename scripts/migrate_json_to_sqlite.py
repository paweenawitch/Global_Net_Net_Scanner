# scripts/migrate_json_to_sqlite.py
from __future__ import annotations

import json
import logging
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.ncav_cache import NcavRecord
from application.ports import PricePoint
from infrastructure.persistence.sqlite_filing_store import SqliteFilingStore
from infrastructure.persistence.sqlite_market_snapshot_store import SqliteMarketSnapshotStore

ROOT = Path(__file__).resolve().parents[1]
LOG = logging.getLogger("migration")

def setup_logging():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")


def migrate_ncav_records():
    cache_dir = ROOT / "cache" / "ncav"
    if not cache_dir.exists():
        LOG.warning(f"No NCAV cache dir found at {cache_dir}")
        return

    db_path = str(ROOT / "data" / "db" / "filings.sqlite")
    store = SqliteFilingStore(db_path)

    files = list(cache_dir.glob("*.json"))
    LOG.info(f"Found {len(files)} NCAV JSON files to migrate.")

    success = 0
    failed = 0
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            rec = NcavRecord(**data)
            store.upsert_ncav_record(rec)
            success += 1
        except Exception as e:
            failed += 1
            LOG.error(f"Failed to migrate {f.name}: {e}")

    LOG.info(f"NCAV Migration complete. Success: {success}, Failed: {failed}")


def migrate_prices():
    prices_file = ROOT / "cache" / "prices" / "latest.json"
    if not prices_file.exists():
        LOG.warning(f"No prices cache found at {prices_file}")
        return

    db_path = str(ROOT / "data" / "db" / "market_snapshots.sqlite")
    store = SqliteMarketSnapshotStore(db_path)

    try:
        data = json.loads(prices_file.read_text(encoding="utf-8"))
        prices_dict = data.get("prices", {})
        points = []
        for sym, pdict in prices_dict.items():
            points.append(
                PricePoint(
                    symbol=pdict.get("symbol", sym),
                    price=pdict.get("price"),
                    asof=pdict.get("asof"),
                    currency=pdict.get("currency"),
                    updated_at=pdict.get("updated_at", "")
                )
            )

        store.upsert_many_prices(points)
        LOG.info(f"Prices Migration complete. Migrated {len(points)} price points.")
    except Exception as e:
        LOG.error(f"Failed to migrate prices: {e}")

def main():
    setup_logging()
    LOG.info("Starting JSON to SQLite migration...")
    migrate_ncav_records()
    migrate_prices()
    LOG.info("Migration finished.")


if __name__ == "__main__":
    main()
