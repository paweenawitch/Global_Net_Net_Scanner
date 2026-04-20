from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class DataInspectionFinding:
    category: str
    severity: str
    scope: str
    signature: str
    anchor_date: str
    title: str
    details: dict[str, Any]
    candidate_action: str
