from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from repopilot.evaluation import EvaluationSummary, evaluate_report_files


@dataclass(frozen=True)
class DashboardSnapshot:
    evaluation: EvaluationSummary
    reports: tuple[dict[str, Any], ...]
    comparison: dict[str, Any] | None


def _load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("JSON 根节点必须是对象")
    return payload


def load_dashboard_snapshot(project_root: Path) -> DashboardSnapshot:
    project_root = Path(project_root).resolve()
    reports_dir = project_root / ".repopilot" / "runs"
    report_paths = sorted(
        reports_dir.glob("*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    ) if reports_dir.exists() else []

    reports: list[dict[str, Any]] = []
    for path in report_paths:
        try:
            payload = _load_object(path)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue
        if payload.get("schema_version") == 2:
            reports.append(payload)

    comparison_path = (
        project_root / ".repopilot" / "comparisons" / "latest.json"
    )
    comparison: dict[str, Any] | None = None
    if comparison_path.is_file():
        try:
            candidate = _load_object(comparison_path)
            if candidate.get("comparison_version") == 1:
                comparison = candidate
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            comparison = None

    return DashboardSnapshot(
        evaluation=evaluate_report_files(report_paths),
        reports=tuple(reports),
        comparison=comparison,
    )
