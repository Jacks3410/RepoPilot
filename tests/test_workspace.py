from pathlib import Path

import pytest

from repopilot.workspace import Workspace, WorkspaceViolation


def test_resolve_normal_path(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path)

    result = workspace.resolve("src/main.py")

    assert result == (tmp_path / "src" / "main.py").resolve()


def test_reject_parent_directory_escape(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path)

    with pytest.raises(WorkspaceViolation):
        workspace.resolve("../secret.txt")


def test_read_text(tmp_path: Path) -> None:
    target = tmp_path / "hello.txt"
    target.write_text("hello RepoPilot", encoding="utf-8")
    workspace = Workspace(tmp_path)

    result = workspace.read_text("hello.txt")

    assert result == "hello RepoPilot"


def test_list_dir(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "README.md").write_text("demo", encoding="utf-8")
    workspace = Workspace(tmp_path)

    result = workspace.list_dir()

    assert "README.md" in result
    assert "src/" in result