import sqlite3
import json

conn = sqlite3.connect('data/db/filings.sqlite')
conn.row_factory = sqlite3.Row

# Check core snapshots
print("--- SEC CORE SNAPSHOTS ---")
c = conn.execute("SELECT core_json FROM sec_core_snapshots WHERE ticker = '3189.JP'").fetchone()
if c:
    core = json.loads(c[0])
    periods = core.get("periods", [])
    print("Periods count:", len(periods))
    for p in periods:
        print(p.get("date", p.get("statement_date")), "shares:", p.get("shares_out", p.get("balance", {}).get("shares_out")))
else:
    print("No core data for 3189.JP in sec_core_snapshots")

# Check ncav records
print("\n--- NCAV RECORDS ---")
r = conn.execute("SELECT financials_json FROM ncav_records WHERE ticker = '3189.JP'").fetchone()
if r:
    ncav = json.loads(r[0])
    print(ncav.get("statement_date"), "shares:", ncav.get("shares_out"))
else:
    print("No NCAV record for 3189.JP")
