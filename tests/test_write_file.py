from pathlib import Path

import pytest

from repopilot.approval import ApprovalGate, ApprovalRejected
from repopilot.file_tools import build_workspace_tools
from repopilot.workspace import Workspace, WorkspaceViolation


def make_write_tool(tmp_path: Path, approval_handler):
    gate = ApprovalGate(handler=approval_handler)
    tools = build_workspace_tools(
        Workspace(tmp_path),
        approval_gate=gate,
    )
    return {tool.name: tool for tool in tools}["write_file"]


def test_write_file_after_approval(tmp_path: Path) -> None:
    write_file = make_write_tool(
        tmp_path,
        approval_handler=lambda request: True,
    )

    result = write_file.execute(
        path="src/demo.py",
        content="print('hello')\n",
    )

    assert result == "已写入文件：src/demo.py"
    assert (tmp_path / "src" / "demo.py").read_text(
        encoding="utf-8"
    ) == "print('hello')\n"


def test_rejected_write_keeps_original_file(tmp_path: Path) -> None:
    target = tmp_path / "demo.txt"
    target.write_text("original", encoding="utf-8")

    write_file = make_write_tool(
        tmp_path,
        approval_handler=lambda request: False,
    )

    with pytest.raises(ApprovalRejected):
        write_file.execute(
            path="demo.txt",
            content="changed",
        )

    assert target.read_text(encoding="utf-8") == "original"


def test_write_rejects_escape_before_approval(tmp_path: Path) -> None:
    approval_requests = []

    write_file = make_write_tool(
        tmp_path,
        approval_handler=(
            lambda request: approval_requests.append(request) or True
        ),
    )

    with pytest.raises(WorkspaceViolation):
        write_file.execute(
            path="../outside.txt",
            content="unsafe",
        )

    assert approval_requests == []