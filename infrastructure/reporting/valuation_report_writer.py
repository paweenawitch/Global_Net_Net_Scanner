# infrastructure/reporting/valuation_report_writer.py

from __future__ import annotations
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict

import pandas as pd

from domain.models.valuation_result import ValuationResult
from application.screening_service import ValuationWriter


class CsvJsonValuationWriter(ValuationWriter):
    """
    Persist a screening run to CSV + JSON, similar to the legacy screening_engine.py.
    """

    def __init__(self, public_dir: Path, internal_dir: Path) -> None:
        self._public_dir = public_dir
        self._internal_dir = internal_dir
        self._public_dir.mkdir(parents=True, exist_ok=True)
        self._internal_dir.mkdir(parents=True, exist_ok=True)

    def write(
        self,
        valuations: List[ValuationResult],
        fx_rates_ccy_to_usd: Dict[str, float],
    ) -> Dict[str, str]:
        now = datetime.now(timezone.utc)
        stamp = now.strftime("%Y%m%d_%H%M%S")
        date_stamp = now.strftime("%Y%m%d")

        results_csv = self._public_dir / f"{date_stamp}_results.csv"
        results_json = self._public_dir / f"{date_stamp}_results.json"
        debug_json = self._internal_dir / f"flags_debug_{stamp}.json"
        latest_dbg = self._internal_dir / "latest_flags_debug.json"

        # turn dataclasses into plain dicts
        rows = [asdict(v) for v in valuations]

        # CSV
        df = pd.DataFrame(rows)
        df.to_csv(results_csv, index=False)

        # JSON export of full rows
        results_json.write_text(json.dumps(rows, indent=2), encoding="utf-8")

        # debug payload (fx subset + metadata)
        debug_payload = {
            "generated_at": now.isoformat(timespec="seconds"),
            "rows_count": len(rows),
            "fx_rates_ccy_to_usd": fx_rates_ccy_to_usd,
        }
        debug_json.write_text(json.dumps(debug_payload, indent=2), encoding="utf-8")
        latest_dbg.write_text(json.dumps(debug_payload, indent=2), encoding="utf-8")

        return {
            "csv": str(results_csv),
            "json": str(results_json),
            "debug": str(debug_json),
            "latest_debug": str(latest_dbg),
        }
