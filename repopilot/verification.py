from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class VerificationTracker:
    """跟踪文件修改与测试验证状态。"""

    max_repair_attempts: int = 3
    successful_writes: int = 0
    test_runs: int = 0
    repair_attempts: int = 0
    last_test_passed: bool | None = None

    def record_tool_result(self, tool_name: str, content: str) -> None:
        """根据成功的工具结果更新验证状态。"""
        if tool_name == "write_file" and content.startswith("已写入文件："):
            if self.last_test_passed is False:
                self.repair_attempts += 1

            self.successful_writes += 1
            self.last_test_passed = None
            return

        if tool_name == "run_tests":
            if "测试状态：PASSED" in content:
                self.test_runs += 1
                self.last_test_passed = True
            elif "测试状态：FAILED" in content:
                self.test_runs += 1
                self.last_test_passed = False

    def repair_budget_exhausted(self) -> bool:
        """测试仍失败且修复次数达到上限时返回 True。"""
        return (
            self.last_test_passed is False
            and self.repair_attempts >= self.max_repair_attempts
        )

    def summary(self) -> dict[str, Any]:
        """返回可写入运行报告的验证指标。"""
        return {
            "successful_writes": self.successful_writes,
            "test_runs": self.test_runs,
            "repair_attempts": self.repair_attempts,
            "max_repair_attempts": self.max_repair_attempts,
            "last_test_passed": self.last_test_passed,
            "repair_budget_exhausted": self.repair_budget_exhausted(),
        }

    @classmethod
    def from_summary(
        cls,
        summary: dict[str, Any],
        default_max_repair_attempts: int = 3,
    ) -> "VerificationTracker":
        """从可信检查点恢复验证计数。"""
        return cls(
            max_repair_attempts=int(
                summary.get(
                    "max_repair_attempts",
                    default_max_repair_attempts,
                )
            ),
            successful_writes=int(summary.get("successful_writes", 0)),
            test_runs=int(summary.get("test_runs", 0)),
            repair_attempts=int(summary.get("repair_attempts", 0)),
            last_test_passed=summary.get("last_test_passed"),
        )

    def completion_blocker(self) -> str | None:
        """返回阻止任务完成的原因；没有原因时返回 None。"""
        if self.successful_writes == 0:
            return None

        if self.repair_budget_exhausted():
            return (
                "测试仍未通过，并且已达到最大修复次数"
                f"（{self.max_repair_attempts} 次）。"
            )

        if self.last_test_passed is None:
            return "代码已被修改，但修改后尚未运行测试。"

        if self.last_test_passed is False:
            return "代码已被修改，但最近一次测试没有通过。"

        return None
