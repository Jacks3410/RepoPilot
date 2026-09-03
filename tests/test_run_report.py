import json
from pathlib import Path

from repopilot.run_report import RunReportWriter
from repopilot.state import TaskState, TaskStatus


def make_completed_state(tmp_path: Path) -> TaskState:
    state = TaskState.create(
        goal="修复中文接口",
        workspace=tmp_path,
        max_steps=8,
    )
    state.start()
    state.begin_step("调用模型")
    state.complete()
    state.verification = {
        "successful_writes": 1,
        "test_runs": 1,
        "repair_attempts": 0,
        "last_test_passed": True,
    }
    state.tool_calls = [{
        "tool_name": "run_tests",
        "success": True,
        "duration_ms": 12.5,
    }]
    return state


def test_writer_creates_structured_json_report(tmp_path: Path) -> None:
    state = make_completed_state(tmp_path)
    writer = RunReportWriter(tmp_path)

    report_path = writer.write(
        state,
        git_status=" M demo.py",
        git_diff="diff --git a/demo.py b/demo.py",
    )

    payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert report_path == (
        tmp_path / ".repopilot" / "runs" / f"{state.task_id}.json"
    )
    assert payload["schema_version"] == 2
    assert payload["task"]["goal"] == "修复中文接口"
    assert payload["task"]["status"] == TaskStatus.COMPLETED.value
    assert payload["verification"]["last_test_passed"] is True
    assert payload["git"]["status"] == " M demo.py"
    assert len(payload["events"]) == 3
    assert payload["tool_calls"][0]["tool_name"] == "run_tests"


def test_writer_replaces_existing_report_atomically(tmp_path: Path) -> None:
    state = make_completed_state(tmp_path)
    writer = RunReportWriter(tmp_path)

    first_path = writer.write(state, git_status=" M first.py")
    second_path = writer.write(state, git_status=" M second.py")
    payload = json.loads(second_path.read_text(encoding="utf-8"))

    assert first_path == second_path
    assert payload["git"]["status"] == " M second.py"
    assert not second_path.with_suffix(".json.tmp").exists()


def test_writer_redacts_secrets_from_entire_report(tmp_path: Path) -> None:
    state = make_completed_state(tmp_path)
    secret = "sk-exampleSecret123456"
    state.goal = f"检查 OPENAI_API_KEY={secret}"
    writer = RunReportWriter(tmp_path)

    report_path = writer.write(state, git_diff=f"+TOKEN = '{secret}'")
    raw = report_path.read_text(encoding="utf-8")

    assert secret not in raw
    assert "[REDACTED]" in raw
