# application/cli/build_universe.py
from __future__ import annotations
from pathlib import Path
import argparse
import sys

from application.build_universe_service import BuildUniverseService
from infrastructure.repositories.csv_universe_writer_repository import CsvUniverseWriterRepository
from infrastructure.sources.us_sec_source import USSecSource
from infrastructure.sources.jp_jpx_source import JPJpxSource
from infrastructure.sources.hk_hkex_source import HKHKEXSource
from infrastructure.sources.th_set_source import THSetSource

def _find_repo_root(start: Path) -> Path:
    """
    Heuristics:
      1) If current or any parent contains "tools/build_universe", that's the repo root.
      2) Else if current or any parent contains both "application" and "infrastructure", use it.
      3) Fallback to two levels up from this file: <root>/application/cli/build_universe.py -> parents[2] == <root>.
    """
    cur = start.resolve()
    for p in [cur, *cur.parents]:
        if (p / "tools" / "build_universe").exists():
            return p
        if (p / "application").exists() and (p / "infrastructure").exists():
            return p
    return Path(__file__).resolve().parents[2]

def run_cli(*, root: Optional[str] = None) -> None:
    if root:
        project_root = Path(root).resolve()
    else:
        project_root = Path(__file__).resolve().parents[2]

    from infrastructure.repositories.composite_universe_repository import CompositeUniverseRepository
    repo = CompositeUniverseRepository(project_root)
    sources = [
        USSecSource(project_root),
        JPJpxSource(project_root),
        HKHKEXSource(project_root),
        THSetSource(project_root),
    ]
    svc = BuildUniverseService(sources=sources, repo=repo)
    result = svc.run()
    print(f"Global universe built: {result['rows']} rows at {project_root / 'data' / 'tickers'}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=str, default=None)
    args = parser.parse_args()

    run_cli(root=args.root)


if __name__ == "__main__":
    main()
