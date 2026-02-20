# How To Automate This Project

This guide explains how to automate background updates for this project using `main.py` and Windows Task Scheduler.

## Automation Scope

- Daily:
  - `update_fx_cache`
  - `update_prices_cache`
  - `main_build_shortlist_cache_only`
- Weekly:
  - `build_universe`
  - `update_ncav_cache` (sharded)
  - `main_fetch_full_cache` US core (sharded)
  - `main_fetch_full_cache` NON_US (sharded)
  - `main_fetch_full_cache` US insiders
- On-demand only:
  - `tools/screening_engine.py` (not scheduled)

## Orchestrator

The root file `main.py` is the orchestrator.

Modes:

- `daily`
- `weekly`
- `all` (runs weekly then daily)

Examples:

```powershell
python main.py daily
python main.py weekly
python main.py all
```

## Important Defaults

`main.py` defaults:

- Universe CSV: `data/tickers/global_full.csv`
- NCAV shards: `2`
- US fetch shards: `2`
- NON_US fetch shards: `2`
- NCAV max age days: `120`
- NCAV min cache interval days: `7`
- NCAV fetch timeout: `25`
- Price batch size: `50`
- Price min batch interval: `1.2`

Override example:

```powershell
python main.py weekly --ncav-shards 2 --fetch-us-shards 2 --fetch-nonus-shards 2
```

## Windows Scheduled Tasks

Recommended wrapper scripts:

- `scripts/run_daily_background.ps1`
- `scripts/run_weekly_background.ps1`

These scripts:

- `Set-Location` to repo root
- run `main.py` with the project venv Python
- write timestamped logs into `logs/`

Create tasks:

```powershell
schtasks /Create /F /TN "GlobalNetNet_Daily" /SC DAILY /ST 06:00 /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File D:\Projects\Global_Net_Net_Scanner\scripts\run_daily_background.ps1"
schtasks /Create /F /TN "GlobalNetNet_Weekly" /SC WEEKLY /D SUN /ST 07:00 /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File D:\Projects\Global_Net_Net_Scanner\scripts\run_weekly_background.ps1"
```

Run immediately for test:

```powershell
schtasks /Run /TN "\GlobalNetNet_Daily"
schtasks /Run /TN "\GlobalNetNet_Weekly"
```

Verify tasks exist:

```powershell
schtasks /Query /FO LIST | Select-String -Pattern "GlobalNetNet|TaskName:"
```

## Logs

Expected logs:

- Daily wrapper logs: `logs/scheduled_daily_YYYYMMDD_HHMMSS.log`
- Weekly wrapper logs: `logs/scheduled_weekly_YYYYMMDD_HHMMSS.log`
- Individual command logs:
  - `logs/update_fx_cache_*.log`
  - `logs/update_prices_cache_*.log`
  - `logs/update_ncav_cache_*.log`

## Troubleshooting

- `ERROR: The system cannot find the file specified.` when running task:
  - Task does not exist or task name/path is wrong.
  - Use `\GlobalNetNet_Daily` style name when running.
- Task exists but no output:
  - Check wrapper script path in task action.
  - Check Python path in wrapper script (`.venv\Scripts\python.exe`).
- Slow or throttled Yahoo runs:
  - Keep shard count modest (2 is recommended baseline).
  - Tune rate controls:
    - `YF_RPS` for NCAV cache fetch path.
    - `YF_MIN_BATCH_INTERVAL` / `--min-batch-interval` for price cache.

## Manual On-Demand Screening

`screening_engine.py` is not part of background schedule by design.
Run it manually when needed.
