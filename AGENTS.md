# AGENTS.md

Guidance for AI coding agents working in this repository.

## Project Overview

Global Net-Net Scanner is a Python + React system for finding global stocks trading below NCAV (Net Current Asset Value). It builds ticker universes, fetches price/fundamental data, normalizes FX, writes SQLite-backed caches, and exposes a local FastAPI + Vite dashboard.

The project follows Clean Architecture:

- `domain/`: core models and pure financial logic. No imports from `application`, `infrastructure`, or UI code.
- `application/`: use cases, orchestration, ports, CLI entry points, and Walter OS pipeline tasks.
- `infrastructure/`: data sources, SQLite persistence, repositories, scheduler/locking, reporting.
- `interfaces/api/`: FastAPI local API for the dashboard/control center.
- `interfaces/ui/`: React/Vite frontend.
- `docs/`: architecture, data-source, automation, and market-extension documentation.
- `scripts/`: maintenance, migration, and verification scripts.

## Non-Negotiable Architecture Rules

Keep dependency direction inward:

- `domain/` must stay independent and pure. Do not import `application`, `infrastructure`, `interfaces`, filesystem, HTTP clients, SQLite, or UI concerns into domain code.
- Put financial formulas, flag classification, FX math helpers, and model-level decisions in `domain/`.
- Put workflow coordination in `application/`.
- Put external data adapters, HTTP calls, SEC/Yahoo/exchange parsing, SQLite details, and file persistence in `infrastructure/`.
- Put presentation and API request/response shaping in `interfaces/`.

The architecture test is `tests/architecture/test_dependency_rules.py`; run it or the full check script after changes that touch imports.

## Setup

Python dependencies:

```powershell
pip install -r requirements.txt
```

Frontend dependencies:

```powershell
npm --prefix interfaces/ui install
```

This repo commonly uses local generated data under `data/`, `cache/`, `reports/`, `logs/`, and SQLite databases in `data/db/`. Treat those as runtime artifacts unless a task explicitly asks to inspect or migrate them.

## Common Commands

Run all Python tests:

```powershell
python -m pytest tests/
```

Run the project check script:

```powershell
.\scripts\check.ps1
```

Show Walter OS orchestrator options:

```powershell
python main.py --help
```

Run Walter cycles:

```powershell
python main.py daily
python main.py weekly
python main.py all
```

Run the FastAPI backend:

```powershell
python -m uvicorn interfaces.api.main:app --port 8001 --host 0.0.0.0
```

Run the React UI:

```powershell
npm --prefix interfaces/ui run dev
```

Build or lint the UI:

```powershell
npm --prefix interfaces/ui run build
npm --prefix interfaces/ui run lint
```

Windows launcher for local users:

```powershell
.\run_scanner.bat
```

## Data Pipeline Cheatsheet

Manual step-by-step flow:

```powershell
python -m application.cli.build_universe
python -m application.cli.update_ncav_cache --csv data/tickers/global_full.csv
python -m application.cli.update_prices_cache --csv data/tickers/global_full.csv
python -m application.cli.update_fx_cache
python -m application.cli.main_build_shortlist_cache_only --tickers_csv data/tickers/global_full.csv
python -m application.cli.main_fetch_full_cache
python -m application.cli.run_screening
```

Default persistent stores:

- `data/db/filings.sqlite`: universe, NCAV records, shortlist, filings, insiders, screening snapshots.
- `data/db/market_snapshots.sqlite`: prices and market snapshots.
- `data/db/walter_os.sqlite`: Walter OS task runs, locks, and incidents.

Be careful with pipeline commands: many fetch live data from Yahoo Finance, SEC EDGAR, exchange sources, or FX providers and may take time. Prefer focused tests for code changes unless the task specifically requires a live data refresh.

## Adding or Changing Markets

Read `docs/ADDING_MARKETS.md` first. The expected market path is:

```text
Universe -> NCAV cache -> Shortlist -> NON-US fetch -> Screening
```

Important conventions:

- House tickers use suffixes such as `AAPL.US`, `7203.JP`, `0005.HK`, `PTTEP.TH`.
- Universe CSV schema is `ticker_base,ticker,name,country,mic`.
- Market sources should ensure their `<market>_full.csv` exists, load it, and return the required DataFrame without downstream filtering.
- Avoid adding special cases downstream when a market can be handled by source registration, ticker mapping, and currency mapping.
- Never default non-US currency logic to USD unless the data proves it.

## Coding Style

- Prefer small, explicit changes that match nearby code.
- Use standard library and existing local abstractions before adding dependencies.
- Preserve CLI argument names where the UI/API discover or call them.
- Keep comments rare and useful.
- Use `pathlib.Path` for filesystem paths in Python when touching path logic.
- Use structured parsers/APIs for CSV, JSON, SQLite, or HTML data instead of ad hoc string parsing.
- Do not commit generated caches, reports, logs, virtual environments, package installs, or local data snapshots.

## Testing Guidance

Choose tests based on the changed surface:

- Domain math/model changes: run the relevant `tests/test_*.py` file and `tests/architecture/test_dependency_rules.py`.
- Import/layer changes: run `python -m pytest tests/architecture/test_dependency_rules.py`.
- CLI changes: run relevant CLI tests, especially `tests/test_run_screening_cli.py`, plus a help command if argparse changed.
- Source/repository changes: add or update focused tests with fixtures/mocks when possible; avoid requiring live network access in tests.
- UI changes: run `npm --prefix interfaces/ui run lint` and `npm --prefix interfaces/ui run build`.
- Broad changes: run `.\scripts\check.ps1`.

## API and UI Notes

The API in `interfaces/api/main.py` reads local SQLite stores and starts subprocess pipeline tasks. It expects repository-relative defaults such as `data/db/filings.sqlite`.

The UI in `interfaces/ui/` is a Vite React app. Keep dashboard changes dense and operational: this is a financial terminal/control surface, not a marketing page. Avoid breaking task argument names that the API discovers or the UI submits.

## Git and Workspace Cautions

- The worktree may contain user-generated data and local artifacts.
- Do not reset, clean, or delete runtime data unless the user explicitly asks.
- If Git reports dubious ownership, the safe-directory fix is:

```powershell
git config --global --add safe.directory D:/Projects/Global_Net_Net_Scanner
```

- If `git status` warns about unreadable cache directories, do not treat that as a code failure.

## Useful References

- `docs/README.md`: product overview and manual pipeline.
- `docs/architecture.md`: Clean Architecture and C4 overview.
- `docs/ADDING_MARKETS.md`: checklist for new market support.
- `docs/DATA_SOURCES.md`: source attribution and data-source expectations.
- `docs/how_to_automate.md`: automation notes.
- `docs/WALTER.md`: Walter OS orchestration details.
