from pathlib import Path

import pytest

from repopilot.file_tools import build_workspace_tools
from repopilot.workspace import Workspace, WorkspaceViolation


def make_tool_map(root: Path):
    tools = build_workspace_tools(Workspace(root))
    return {tool.name: tool for tool in tools}


def test_build_workspace_tools(tmp_path: Path) -> None:
    tool_map = make_tool_map(tmp_path)

    assert set(tool_map) == {"list_files", "read_file"}


def test_list_files_tool(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "README.md").write_text("demo", encoding="utf-8")
    tool_map = make_tool_map(tmp_path)

    result = tool_map["list_files"].execute(path=".")

    assert "README.md" in result
    assert "src/" in result


def test_read_file_tool(tmp_path: Path) -> None:
    (tmp_path / "hello.txt").write_text(
        "hello RepoPilot",
        encoding="utf-8",
    )
    tool_map = make_tool_map(tmp_path)

    result = tool_map["read_file"].execute(path="hello.txt")

    assert result == "hello RepoPilot"


def test_tools_reject_path_escape(tmp_path: Path) -> None:
    tool_map = make_tool_map(tmp_path)

    with pytest.raises(WorkspaceViolation):
        tool_map["read_file"].execute(path="../secret.txt")