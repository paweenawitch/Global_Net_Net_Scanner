from __future__ import annotations

from domain.models.data_inspection_finding import DataInspectionFinding

ALLOWED_SEVERITIES = {"INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"}


def build_dedup_key(finding: DataInspectionFinding) -> str:
    return f"{finding.category}|{finding.scope}|{finding.signature}|{finding.anchor_date}"


def validate_finding(finding: DataInspectionFinding) -> None:
    if not finding.category.strip():
        raise ValueError("finding category is required")
    if finding.severity not in ALLOWED_SEVERITIES:
        raise ValueError(f"unsupported finding severity: {finding.severity}")
    if not finding.scope.strip():
        raise ValueError("finding scope is required")
    if not finding.signature.strip():
        raise ValueError("finding signature is required")
    if not finding.anchor_date.strip():
        raise ValueError("finding anchor_date is required")
    if not finding.title.strip():
        raise ValueError("finding title is required")
    if not finding.candidate_action.strip():
        raise ValueError("finding candidate_action is required")
