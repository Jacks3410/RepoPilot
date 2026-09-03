from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from repopilot.state import TaskState


@dataclass(frozen=True)
class RunReportWriter:
    """将一次 Agent 运行保存为可审计的 JSON 报告。"""

    workspace: Path

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "workspace",
            Path(self.workspace).resolve(),
        )

    @property
    def reports_dir(self) -> Path:
        return self.workspace / ".repopilot" / "runs"

    def build_payload(
        self,
        state: TaskState,
        git_status: str = "",
        git_diff: str = "",
    ) -> dict[str, Any]:
        """构建版本化、可 JSON 序列化的报告内容。"""
        return {
            "schema_version": 2,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "task": {
                "task_id": state.task_id,
                "goal": state.goal,
                "workspace": str(state.workspace),
                "status": state.status.value,
                "step_count": state.step_count,
                "max_steps": state.max_steps,
                "last_error": state.last_error,
            },
            "verification": dict(state.verification),
            "events": list(state.events),
            "tool_calls": list(state.tool_calls),
            "git": {
                "status": git_status,
                "diff": git_diff,
            },
        }

    def write(
        self,
        state: TaskState,
        git_status: str = "",
        git_diff: str = "",
    ) -> Path:
        """原子写入报告并返回报告的绝对路径。"""
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        target = self.reports_dir / f"{state.task_id}.json"
        temporary = self.reports_dir / f"{state.task_id}.json.tmp"
        payload = self.build_payload(state, git_status, git_diff)

        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(target)
        return target
