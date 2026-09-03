from pathlib import Path

import pytest

from repopilot.approval import ApprovalGate, ApprovalRejected
from repopilot.execution_tools import build_execution_tools
from repopilot.test_runner import TestResult as RepoTestResult
from repopilot.workspace import Workspace


class FakeTestRunner:
    command = ("uv", "run", "python", "-m", "pytest", "-q")

    def __init__(self) -> None:
        self.call_count = 0

    def run(self) -> RepoTestResult:
        self.call_count += 1

        return RepoTestResult(
            command=self.command,
            return_code=0,
            stdout="25 passed",
            stderr="",
            duration_seconds=0.5,
        )


def test_run_tests_after_approval(tmp_path: Path) -> None:
    runner = FakeTestRunner()
    gate = ApprovalGate(handler=lambda request: True)

    tools = build_execution_tools(
        workspace=Workspace(tmp_path),
        approval_gate=gate,
        test_runner=runner,
    )

    result = tools[0].execute()

    assert tools[0].name == "run_tests"
    assert runner.call_count == 1
    assert "PASSED" in result
    assert "25 passed" in result


def test_rejected_run_does_not_execute_tests(tmp_path: Path) -> None:
    runner = FakeTestRunner()
    gate = ApprovalGate(handler=lambda request: False)

    tools = build_execution_tools(
        workspace=Workspace(tmp_path),
        approval_gate=gate,
        test_runner=runner,
    )

    with pytest.raises(ApprovalRejected):
        tools[0].execute()

    assert runner.call_count == 0