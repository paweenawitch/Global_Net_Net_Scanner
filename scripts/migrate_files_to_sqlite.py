# scripts/migrate_files_to_sqlite.py
import json
import os
import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone

from infrastructure.persistence.sqlite_filing_store import SqliteFilingStore
from domain.models.fundamentals import NcavRecord

def main():
    root = Path(__file__).resolve().parents[1]
    db_path = root / "data" / "db" / "filings.sqlite"
    store = SqliteFilingStore(str(db_path))

    # 1. Migrate Universe
    univ_csv = root / "data" / "tickers" / "global_full.csv"
    if univ_csv.exists():
        print(f"Migrating universe from {univ_csv}...")
        df = pd.read_csv(univ_csv)
        for _, row in df.iterrows():
            d = row.to_dict()
            store.upsert_universe_ticker(d)
        print(f"Done: {len(df)} tickers migrated.")

    # 2. Migrate Shortlist
    short_csv = root / "data" / "tickers" / "ncav_shortlist.csv"
    if short_csv.exists():
        print(f"Migrating shortlist from {short_csv}...")
        df = pd.read_csv(short_csv)
        store.clear_shortlist()
        count = 0
        for _, row in df.iterrows():
            t = row.get("ticker")
            p = row.get("price")
            c = row.get("currency")
            if t and not pd.isna(p):
                store.upsert_shortlist_item(str(t), float(p), str(c) if not pd.isna(c) else None)
                count += 1
        print(f"Done: {count} shortlist items migrated.")

    # 3. Migrate Core (SEC/Yahoo)
    core_dir = root / "cache" / "sec_core"
    if core_dir.exists():
        print(f"Migrating core snapshots from {core_dir}...")
        files = list(core_dir.glob("*_core.json"))
        for f in files:
            ticker = f.name.replace("_core.json", "")
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                store.upsert_sec_core(ticker, data)
            except Exception as e:
                print(f"Error migrating {f.name}: {e}")
        print(f"Done: {len(files)} core snapshots migrated.")

    # 4. Migrate Insider
    ins_dir = root / "cache" / "sec_insider"
    if ins_dir.exists():
        print(f"Migrating insider snapshots from {ins_dir}...")
        files = list(ins_dir.glob("*.json"))
        for f in files:
            ticker = f.stem
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                store.upsert_insider(ticker, data)
            except Exception as e:
                print(f"Error migrating {f.name}: {e}")
        print(f"Done: {len(files)} insider snapshots migrated.")

    print("\nMigration complete.")

if __name__ == "__main__":
    main()
