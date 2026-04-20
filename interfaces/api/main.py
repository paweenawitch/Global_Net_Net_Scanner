from __future__ import annotations

import os
import sys
import sqlite3
import json
import logging
import subprocess
import signal
import asyncio
from pathlib import Path
from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scanner_api")

app = FastAPI(title="Global Net-Net Scanner API")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
FILINGS_DB = ROOT_DIR / "data" / "db" / "filings.sqlite"
MARKET_DB = ROOT_DIR / "data" / "db" / "market_snapshots.sqlite"
WALTER_DB = ROOT_DIR / "data" / "db" / "walter_os.sqlite"

# --- Models ---
class TaskRequest(BaseModel):
    task_type: str = "cycle" # "cycle" (daily/weekly) or "direct" (application/cli scripts)
    mode: str # cycle name (daily/weekly) or script name (without .py)
    args: Dict[str, Any] = {}

class ProcessInfo(BaseModel):
    pid: int
    mode: str
    task_type: str
    started_at: str

# --- Pipeline Metadata ---
TASK_METADATA = {
    "build_universe": {
        "order": 1,
        "group": "CORE PIPELINE",
        "label": "Step 1: Universe Building",
        "description": "Initialize Ticker Universe. Generates regional or global ticker lists from exchange sources."
    },
    "update_ncav_cache": {
        "order": 2,
        "group": "CORE PIPELINE",
        "label": "Step 2: Balance Sheet Sync",
        "description": "Baseline Balance Sheet Sync. Fetches latest current assets/liabilities for initial shortlist filtering. [Recommended: Weekly Run]"
    },
    "update_prices_cache": {
        "order": 3,
        "group": "CORE PIPELINE",
        "label": "Step 3: Price Sync",
        "description": "Sync Market Prices. Synchronizes latest market closing prices from Yahoo Finance."
    },
    "update_fx_cache": {
        "order": 4,
        "group": "CORE PIPELINE",
        "label": "Step 4: FX Sync",
        "description": "Sync FX Rates. Updates real-time spot rates for global currency normalization."
    },
    "main_build_shortlist_cache_only": {
        "order": 5,
        "group": "CORE PIPELINE",
        "label": "Step 5: Generate Shortlist",
        "description": "High-Efficiency Filtering. Re-filters universe based on latest Data Sync. [Required after any Sync]"
    },
    "main_fetch_full_cache": {
        "order": 6,
        "group": "CORE PIPELINE",
        "label": "Step 6: Deep-Dive Sync",
        "description": "Fundamental Analysis. Analyzes cash flow, capital structure, and insider behavior. [Recommended: Weekly Run]"
    },
    "run_screening": {
        "order": 7,
        "group": "CORE PIPELINE",
        "label": "Step 7: Screening Engine",
        "description": "Final Engine Run. Compiles results and populates the High-Density Dashboard."
    }
}

# --- State Management ---
active_processes: Dict[int, subprocess.Popen] = {}
process_metadata: Dict[int, Dict[str, Any]] = {}

def get_db_connection(db_path: Path):
    conn = sqlite3.connect(db_path, timeout=30.0) # Add busy timeout
    conn.execute("PRAGMA journal_mode=WAL;") # Enable WAL mode for concurrency
    conn.row_factory = sqlite3.Row
    return conn

def discover_args(file_path: Path) -> List[str]:
    """Scans a python file for argparse argument definitions."""
    try:
        content = file_path.read_text(encoding="utf-8")
        # Find all --arg-name or --arg_name in add_argument calls, handling optional short flags and whitespace
        matches = re.findall(r'\.add_argument\(\s*(?:["\'][^"\']+["\']\s*,\s*)*["\']--([^"\']+)["\']', content)
        return sorted(list(set(matches)))
    except Exception as e:
        logger.error(f"Failed to scan args for {file_path}: {e}")
        return []

# --- Endpoints ---

@app.get("/health")
def health_check():
    return {"status": "ONLINE", "timestamp": datetime.now(timezone.utc).isoformat()}

@app.get("/screener/runs")
def get_screening_runs():
    if not FILINGS_DB.exists():
        return []
    with get_db_connection(FILINGS_DB) as conn:
        rows = conn.execute("SELECT DISTINCT run_date FROM screening_snapshots ORDER BY run_date DESC").fetchall()
        return [r["run_date"] for r in rows]

@app.get("/screener")
def get_screener_results(run_date: Optional[str] = None):
    if not FILINGS_DB.exists():
        return []
    
    with get_db_connection(FILINGS_DB) as conn:
        # If run_date is provided, we filter by it.
        # If not, we find the absolute latest run_date available in the table.
        if not run_date:
            latest_row = conn.execute("SELECT MAX(run_date) as max_date FROM screening_snapshots").fetchone()
            if not latest_row or not latest_row["max_date"]:
                return []
            run_date = latest_row["max_date"]

        logger.info(f"Fetching results for run_date: {run_date}")
        
        # Use LEFT JOIN to be more resilient
        query = """
            SELECT 
                u.name, 
                u.country,
                n.financials_json as raw_json,
                s.valuation_json as val_json
            FROM screening_snapshots s
            LEFT JOIN universe_tickers u ON u.ticker = s.ticker
            LEFT JOIN ncav_records n ON n.ticker = s.ticker
            WHERE s.run_date = ?
            ORDER BY s.ticker ASC
        """
        rows = conn.execute(query, (run_date,)).fetchall()
        logger.info(f"Found {len(rows)} matching snapshots")
        
        results = []
        for r in rows:
            val = json.loads(r["val_json"])
            raw = json.loads(r["raw_json"])
            
            # Map fields to what the UI expects, plus add the NEW "Full Stack" data
            results.append({
                "ticker": val.get("ticker"),
                "name": r["name"],
                "country": r["country"],
                "fs_date": val.get("latest_fs_date"),
                "currency": val.get("reporting_currency"),
                "ncav_ps": val.get("ncav_per_share"),
                "shares_out": val.get("shares_out"),
                "assets_current": raw.get("assets_current"),
                "liab_total": raw.get("liab_total"),
                
                # --- New Full Stack Parameters ---
                "current_ratio": val.get("current_ratio"),
                "debt_to_equity": val.get("debt_to_equity"),
                "price_to_ncav": val.get("price_to_ncavps"),
                "margin_of_safety": val.get("margin_of_safety"),
                
                "ncav_change_qoq": val.get("ncav_change_qoq"),
                "ncav_change_hoh": val.get("ncav_change_hoh"),
                "ncav_change_yoy": val.get("ncav_change_yoy"),
                
                "dilution_qoq": val.get("dilution_qoq"),
                "dilution_hoh": val.get("dilution_hoh"),
                "dilution_yoy": val.get("dilution_yoy"),
                
                "insider_signal": val.get("insider_signal"),
                "green_flags": val.get("green_flags", []),
                "red_flags": val.get("red_flags", []),
                
                "passes_price_to_ncav_rule": val.get("passes_price_to_ncav_rule"),
                "last_price": val.get("last_price"),
                "is_outdated": val.get("is_outdated"),
            })
        return results

@app.get("/walter/stats")
def get_walter_stats():
    if not WALTER_DB.exists():
        return {"incidents": [], "recent_runs": []}
    
    with get_db_connection(WALTER_DB) as conn:
        incidents = conn.execute("SELECT * FROM incidents WHERE status = 'OPEN' ORDER BY updated_at DESC LIMIT 5").fetchall()
        runs = conn.execute("SELECT * FROM task_runs ORDER BY started_at DESC LIMIT 10").fetchall()
        
        return {
            "incidents": [dict(i) for i in incidents],
            "recent_runs": [dict(r) for r in runs]
        }

@app.get("/workflow/tasks")
def get_tasks():
    cli_dir = ROOT_DIR / "application" / "cli"
    tasks = []
    if cli_dir.exists():
        for f in cli_dir.glob("*.py"):
            if f.name == "__init__.py": continue
            
            meta = TASK_METADATA.get(f.stem, {
                "order": 99,
                "group": "ADDITIONAL UTILITIES",
                "label": f.stem,
                "description": f"CLI Script: {f.name}"
            })
            
            supported = discover_args(f)
            tasks.append({
                "name": f.stem,
                "path": str(f.relative_to(ROOT_DIR)),
                "label": meta["label"],
                "description": meta["description"],
                "group": meta["group"],
                "order": meta["order"],
                "supported_args": supported
            })
    
    # Sort by group (Core first) then by order
    return sorted(tasks, key=lambda x: (x["group"] != "CORE PIPELINE", x["order"]))

@app.get("/workflow/active")
def get_active_tasks():
    results = []
    # Clean up dead processes first
    dead_pids = []
    for pid, proc in active_processes.items():
        if proc.poll() is not None:
            dead_pids.append(pid)
        else:
            meta = process_metadata.get(pid, {})
            results.append({
                "pid": pid,
                "mode": meta.get("mode"),
                "task_type": meta.get("task_type"),
                "started_at": meta.get("started_at")
            })
    
    for pid in dead_pids:
        del active_processes[pid]
        if pid in process_metadata:
            del process_metadata[pid]
            
    return results

@app.post("/workflow/run")
def run_task(request: TaskRequest, background_tasks: BackgroundTasks):
    # Construct command
    if request.task_type == "cycle":
        cmd = [sys.executable, "-m", "main", request.mode]
    else:
        # Direct CLI script
        cmd = [sys.executable, "-m", f"application.cli.{request.mode}"]
    
    for key, value in request.args.items():
        arg_name = f"--{key.replace('_', '-')}"
        if isinstance(value, bool):
            if value:
                cmd.append(arg_name)
        elif value is not None:
            cmd.append(arg_name)
            cmd.append(str(value))
    
    logger.info(f"Starting task: {' '.join(cmd)}")
    
    # Spawn process
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=ROOT_DIR,
        bufsize=1,
        universal_newlines=True
    )
    
    active_processes[process.pid] = process
    process_metadata[process.pid] = {
        "mode": request.mode,
        "task_type": request.task_type,
        "started_at": datetime.now(timezone.utc).isoformat()
    }
    
    return {"pid": process.pid, "mode": request.mode, "status": "STARTED"}

@app.post("/workflow/kill/{pid}")
def kill_task(pid: int):
    if pid not in active_processes:
        raise HTTPException(status_code=404, detail="Process not found")
    
    process = active_processes[pid]
    process.terminate()
    del active_processes[pid]
    
    return {"status": "KILLED", "pid": pid}

@app.websocket("/workflow/stream/{pid}")
async def stream_logs(websocket: WebSocket, pid: int):
    await websocket.accept()
    if pid not in active_processes:
        await websocket.send_text("Error: Process not found")
        await websocket.close()
        return
    
    process = active_processes[pid]
    try:
        # We need to read from the pipe asynchronously
        # This is simple blocking read for demonstration, better would be a non-blocking queue
        while True:
            line = process.stdout.readline()
            if not line:
                if process.poll() is not None:
                    break
                await asyncio.sleep(0.1)
                continue
            await websocket.send_text(line.strip())
            await asyncio.sleep(0.01)
    except WebSocketDisconnect:
        logger.info(f"Client disconnected from log stream {pid}")
    except Exception as e:
        logger.error(f"Error streaming logs: {e}")
    finally:
        await websocket.close()
