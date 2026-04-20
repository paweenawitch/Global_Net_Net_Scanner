from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List

import pandas as pd

from application.ports import TickerSource, UniverseBuilder, UniverseRepository
from application.universe_schema import (
    UniverseSchema,
    normalize_universe_df,
    universe_qc,
)


def _dedupe_global(df: pd.DataFrame) -> pd.DataFrame:
    """
    Conservative global dedupe:
      1) instrument_id (absolute)
      2) (country, ticker) (absolute)
      3) (country, ticker_base) (reasonable)
      4) do NOT dedupe by name (unsafe globally)
    """
    if df is None or df.empty:
        return df

    x = df.copy()
    x = x.drop_duplicates(subset=["instrument_id"], keep="first")
    x = x.drop_duplicates(subset=["country", "ticker"], keep="first")
    x = x.drop_duplicates(subset=["country", "ticker_base"], keep="first")
    return x.reset_index(drop=True)


@dataclass
class BuildUniverseService(UniverseBuilder):
    sources: List[TickerSource]
    repo: UniverseRepository

    def run(self) -> Dict[str, Any]:
        prov: Dict[str, Any] = {}
        frames: List[pd.DataFrame] = []

        for src in self.sources:
            raw_df = src.fetch()
            df = normalize_universe_df(raw_df)

            meta = {
                "source": getattr(src, "source_label", src.__class__.__name__),
                "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "rows": int(len(df)),

                # Schema contract + semantics
                "schema": {
                    "required": list(UniverseSchema.required),
                    "recommended": list(UniverseSchema.recommended),
                    "canonical_columns": list(UniverseSchema.canonical_columns()),
                },

                # Nice-to-have A: policy stamp
                "universe_policy": UniverseSchema.universe_policy(),
            }

            self.repo.write_market(src.market_code, df, meta)
            print(f"OK: {src.market_code}: {len(df)} rows")
            prov[src.market_code] = meta

            if not df.empty:
                frames.append(df)

        all_df = (
            pd.concat(frames, ignore_index=True)
            if frames
            else pd.DataFrame(columns=list(UniverseSchema.canonical_columns()))
        )
        all_df = _dedupe_global(all_df)

        qc = universe_qc(all_df)

        global_meta = {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "markets": prov,
            "total_rows": int(len(all_df)),

            # Nice-to-have A: policy stamp
            "universe_policy": UniverseSchema.universe_policy(),

            # Nice-to-have B: QC summary
            "qc": qc,
        }

        self.repo.write_global(all_df, global_meta)

        # Optional: print QC to console
        print("--- Universe QC ---")
        for k, v in qc.items():
            print(f"  {k}: {v}")

        return {"meta": global_meta, "rows": int(len(all_df))}
