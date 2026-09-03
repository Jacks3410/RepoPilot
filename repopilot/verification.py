from __future__ import annotations

from dataclasses import dataclass


@dataclass
class VerificationTracker:
    """跟踪文件修改与测试验证状态。"""

    successful_writes: int = 0
    test_runs: int = 0
    last_test_passed: bool | None = None

    def record_tool_result(self, tool_name: str, content: str) -> None:
        """根据成功的工具结果更新验证状态。"""
        if tool_name == "write_file" and content.startswith("已写入文件："):
            self.successful_writes += 1
            self.last_test_passed = None
            return

        if tool_name == "run_tests":
            self.test_runs += 1

            if "测试状态：PASSED" in content:
                self.last_test_passed = True
            elif "测试状态：FAILED" in content:
                self.last_test_passed = False

    def completion_blocker(self) -> str | None:
        """返回阻止任务完成的原因；没有原因时返回 None。"""
        if self.successful_writes == 0:
            return None

        if self.last_test_passed is None:
            return "代码已被修改，但修改后尚未运行测试。"

        if self.last_test_passed is False:
            return "代码已被修改，但最近一次测试没有通过。"

        return None