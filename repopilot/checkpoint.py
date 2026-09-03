from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from repopilot.audit import redact_sensitive_data
from repopilot.state import TaskState, TaskStatus


_TASK_ID_PATTERN = re.compile(r"^[a-f0-9]{12}$")
@dataclass(frozen=True)
class TaskCheckpointStore:
    """安全保存并恢复不包含模型上下文的任务检查点。"""

    workspace: Path

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "workspace",
            Path(self.workspace).resolve(),
        )

    @property
    def checkpoints_dir(self) -> Path:
        return self.workspace / ".repopilot" / "checkpoints"

    def save(self, state: TaskState) -> Path:
        if not _TASK_ID_PATTERN.fullmatch(state.task_id):
            raise ValueError("任务 ID 格式无效")

        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
        target = self.checkpoints_dir / f"{state.task_id}.json"
        temporary = self.checkpoints_dir / f"{state.task_id}.json.tmp"
        payload = {
            "schema_version": 1,
            "task": {
                "task_id": state.task_id,
                "goal": state.goal,
                "workspace": str(state.workspace),
                "status": state.status.value,
                "step_count": state.step_count,
                "max_steps": state.max_steps,
                "events": state.events,
                "tool_calls": state.tool_calls,
                "last_error": state.last_error,
                "verification": state.verification,
                "model_usage": state.model_usage,
            },
        }
        safe_payload = redact_sensitive_data(payload)

        temporary.write_text(
            json.dumps(safe_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(target)
        return target

    def load(self, task_id: str) -> TaskState:
        if not _TASK_ID_PATTERN.fullmatch(task_id):
            raise ValueError("任务 ID 格式无效")

        path = self.checkpoints_dir / f"{task_id}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))

        if payload.get("schema_version") != 1:
            raise ValueError("不支持的检查点版本")

        task = payload["task"]
        if task.get("task_id") != task_id:
            raise ValueError("检查点任务 ID 与文件名不一致")

        checkpoint_workspace = Path(task["workspace"]).resolve()
        if checkpoint_workspace != self.workspace:
            raise ValueError("检查点不属于当前工作目录")

        return TaskState(
            goal=str(task["goal"]),
            workspace=checkpoint_workspace,
            task_id=str(task["task_id"]),
            status=TaskStatus(task["status"]),
            step_count=int(task["step_count"]),
            max_steps=int(task["max_steps"]),
            events=list(task.get("events", [])),
            tool_calls=list(task.get("tool_calls", [])),
            last_error=task.get("last_error"),
            verification=dict(task.get("verification", {})),
            model_usage={
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                **dict(task.get("model_usage", {})),
            },
        )

    def latest_recoverable(self) -> TaskState | None:
        if not self.checkpoints_dir.exists():
            return None

        paths = sorted(
            self.checkpoints_dir.glob("*.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )

        for path in paths:
            try:
                state = self.load(path.stem)
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
                continue

            if state.status == TaskStatus.RUNNING:
                return state

        return None
