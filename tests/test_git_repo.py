import subprocess
from pathlib import Path

import pytest

from repopilot.git_repo import GitCommandError, GitRepository


def run_git(root: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", *arguments],
        cwd=root,
        capture_output=True,
        check=True,
    )


def initialize_repository(root: Path) -> None:
    run_git(root, "init")
    run_git(root, "config", "user.name", "RepoPilot Test")
    run_git(root, "config", "user.email", "test@example.com")

    tracked = root / "tracked.txt"
    tracked.write_text("before\n", encoding="utf-8")

    run_git(root, "add", "tracked.txt")
    run_git(root, "commit", "-m", "initial")


def test_rejects_non_git_directory(tmp_path: Path) -> None:
    with pytest.raises(GitCommandError):
        GitRepository(tmp_path)


def test_reports_tracked_and_untracked_changes(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    repository = GitRepository(tmp_path)

    (tmp_path / "tracked.txt").write_text(
        "after\n",
        encoding="utf-8",
    )
    (tmp_path / "new.txt").write_text(
        "new file\n",
        encoding="utf-8",
    )

    status = repository.status_short()
    diff = repository.diff()

    assert "tracked.txt" in status
    assert "new.txt" in status
    assert "-before" in diff
    assert "+after" in diff
    assert "b/new.txt" in diff
    assert "+new file" in diff