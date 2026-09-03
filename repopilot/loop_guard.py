from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


Observation = tuple[str, str, str]
_PROGRESS_TOOLS = {"write_file", "run_tests"}


@dataclass
class ToolLoopGuard:
    """通过调用与结果指纹检测没有进展的工具循环。"""

    max_repeats: int = 3
    history_limit: int = 8
    _history: list[Observation] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.max_repeats < 2:
            raise ValueError("重复调用阈值不能小于 2")
        if self.history_limit < self.max_repeats:
            raise ValueError("历史窗口不能小于重复调用阈值")

    @classmethod
    def from_audit_records(
        cls,
        records: list[dict[str, Any]],
        max_repeats: int = 3,
        history_limit: int = 8,
    ) -> "ToolLoopGuard":
        guard = cls(
            max_repeats=max_repeats,
            history_limit=history_limit,
        )
        for record in records[-history_limit:]:
            observation = guard._observation(record)
            if observation is not None:
                guard._remember(observation)
        return guard

    def observe(self, record: dict[str, Any]) -> str | None:
        observation = self._observation(record)
        if observation is None:
            return None

        self._remember(observation)
        repeats = self._history.count(observation)

        if repeats >= self.max_repeats:
            tool_name = observation[0]
            return (
                "检测到重复工具调用且结果未变化："
                f"{tool_name} 已重复 {repeats} 次"
            )
        return None

    @staticmethod
    def _observation(record: dict[str, Any]) -> Observation | None:
        tool_name = str(record.get("tool_name", ""))
        call_fingerprint = str(record.get("call_fingerprint", ""))
        result_fingerprint = str(record.get("result_fingerprint", ""))
        if not tool_name or not call_fingerprint or not result_fingerprint:
            return None
        return tool_name, call_fingerprint, result_fingerprint

    def _remember(self, observation: Observation) -> None:
        tool_name = observation[0]
        if (
            tool_name in _PROGRESS_TOOLS
            and self._history
            and self._history[-1] != observation
        ):
            self._history.clear()

        self._history.append(observation)
        if len(self._history) > self.history_limit:
            del self._history[:-self.history_limit]
