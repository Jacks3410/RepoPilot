from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from uuid import uuid4


class TaskStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class TaskState:
    goal: str
    workspace: Path
    task_id: str = field(default_factory=lambda: uuid4().hex[:12])
    status: TaskStatus = TaskStatus.CREATED
    step_count: int = 0
    max_steps: int = 12
    events: list[str] = field(default_factory=list)
    last_error: str | None = None

    @classmethod
    def create(
        cls,
        goal: str,
        workspace: str | Path,
        max_steps: int = 12,
    ) -> "TaskState":
        goal = goal.strip()
        if not goal:
            raise ValueError("任务目标不能为空")

        return cls(
            goal=goal,
            workspace=Path(workspace).resolve(),
            max_steps=max_steps,
        )

    def start(self) -> None:
        self.status = TaskStatus.RUNNING
        self.record("任务开始")

    def begin_step(self, description: str) -> None:
        if self.status != TaskStatus.RUNNING:
            raise RuntimeError("任务当前不处于运行状态")

        if self.step_count >= self.max_steps:
            self.status = TaskStatus.BLOCKED
            self.record("达到最大执行步数")
            raise RuntimeError("达到最大执行步数")

        self.step_count += 1
        self.record(f"步骤 {self.step_count}: {description}")

    def complete(self) -> None:
        self.status = TaskStatus.COMPLETED
        self.record("任务完成")

    def fail(self, error: Exception | str) -> None:
        self.last_error = str(error)
        self.status = TaskStatus.FAILED
        self.record(f"任务失败: {self.last_error}")

    def record(self, message: str) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        self.events.append(f"{timestamp} {message}")