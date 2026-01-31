from __future__ import annotations

from pathlib import Path
import runpy
import pandas as pd


class THSetSource:
    market_code = "TH"

    def __init__(self, project_root: Path):
        self.root = Path(project_root).resolve()

    def fetch(self) -> pd.DataFrame:
        out_csv = self.root / "data" / "tickers" / "th_full.csv"
        tool = self.root / "tools" / "build_universe" / "th_set.py"

        if not out_csv.exists():
            if not tool.exists():
                raise FileNotFoundError(f"Missing Thailand builder script: {tool}")

            try:
                # Always rebuild Thailand universe
                runpy.run_path(str(tool), run_name="__main__")
            except Exception as e:
                raise RuntimeError(
                    f"Thailand builder crashed: {tool}\n"
                    f"Underlying error: {type(e).__name__}: {e}\n"
                    f"Tip: run manually to see full logs:\n"
                    f"  python {tool}"
                ) from e

        if not out_csv.exists():
            # If it *still* doesn't exist, builder didn't write output (bug)
            raise FileNotFoundError(
                f"Thailand universe not created: {out_csv}\n"
                f"Tip: run manually:\n"
                f"  python {tool}"
            )

        df = pd.read_csv(out_csv)
        required = {"ticker_base", "ticker", "name", "country", "mic"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"th_full.csv missing columns: {sorted(missing)}")

        return df
