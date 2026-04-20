from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TaskSpec:
    task_name: str
    pipeline: str
    params: dict[str, Any] = field(default_factory=dict)
    allow_overlap: bool = False
    max_retries: int = 0
