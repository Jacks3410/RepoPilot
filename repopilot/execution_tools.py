from __future__ import annotations

import subprocess

from repopilot.tool import Tool

from repopilot.approval import ApprovalGate, ApprovalRequest
from repopilot.test_runner import TestRunner
from repopilot.workspace import Workspace


def build_execution_tools(
    workspace: Workspace,
    approval_gate: ApprovalGate,
    test_runner: TestRunner | None = None,
) -> list[Tool]:
    """创建需要人工审批的代码执行工具。"""
    runner = test_runner or TestRunner(workspace)

    def run_tests() -> str:
        command_text = subprocess.list2cmdline(list(runner.command))

        approval_gate.require(
            ApprovalRequest(
                action="run_tests",
                target=str(workspace.root),
                details=f"即将执行固定测试命令：\n{command_text}",
            )
        )

        result = runner.run()
        return result.render()

    return [
        Tool(
            name="run_tests",
            description=(
                "Run the repository's fixed pytest command and return its "
                "exit code, output and duration. Human approval is required."
            ),
            parameters={
                "type": "object",
                "properties": {},
            },
            fn=run_tests,
        )
    ]
