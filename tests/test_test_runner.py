import sys
from pathlib import Path

from repopilot.test_runner import TestRunner as RepoTestRunner
from repopilot.workspace import Workspace


def test_runner_reports_success(tmp_path: Path) -> None:
    runner = RepoTestRunner(
        workspace=Workspace(tmp_path),
        command=(
            sys.executable,
            "-c",
            "print('tests passed')",
        ),
    )

    result = runner.run()

    assert result.passed is True
    assert result.return_code == 0
    assert "tests passed" in result.stdout
    assert "PASSED" in result.render()


def test_runner_reports_failure(tmp_path: Path) -> None:
    runner = RepoTestRunner(
        workspace=Workspace(tmp_path),
        command=(
            sys.executable,
            "-c",
            "import sys; print('tests failed'); sys.exit(3)",
        ),
    )

    result = runner.run()

    assert result.passed is False
    assert result.return_code == 3
    assert "tests failed" in result.stdout
    assert "FAILED" in result.render()


def test_runner_stops_after_timeout(tmp_path: Path) -> None:
    runner = RepoTestRunner(
        workspace=Workspace(tmp_path),
        command=(
            sys.executable,
            "-c",
            "import time; time.sleep(2)",
        ),
        timeout_seconds=0.1,
    )

    result = runner.run()

    assert result.passed is False
    assert result.timed_out is True
    assert result.return_code == 124