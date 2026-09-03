import json
from pathlib import Path

from repopilot.evaluation import (
    evaluate_report,
    evaluate_report_files,
    write_evaluation,
)


def make_report(
    task_id: str,
    status: str,
    writes: int,
    last_test_passed: bool | None,
    tool_calls: list[dict],
) -> dict:
    return {
        "schema_version": 2,
        "task": {
            "task_id": task_id,
            "status": status,
            "step_count": 4,
        },
        "verification": {
            "successful_writes": writes,
            "repair_attempts": 1 if writes else 0,
            "last_test_passed": last_test_passed,
        },
        "tool_calls": tool_calls,
    }


def write_report(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )


def test_evaluate_report_detects_verification_and_approval_violation() -> None:
    payload = make_report(
        task_id="aaaaaaaaaaaa",
        status="failed",
        writes=1,
        last_test_passed=False,
        tool_calls=[{
            "tool_name": "write_file",
            "success": True,
            "requires_approval": True,
            "approval_status": "unknown",
            "error": None,
        }],
    )

    metrics = evaluate_report(payload)

    assert metrics.completed is False
    assert metrics.verification_compliant is False
    assert metrics.approval_violations == 1


def test_evaluate_report_files_aggregates_rates(tmp_path: Path) -> None:
    read_only = make_report(
        task_id="aaaaaaaaaaaa",
        status="completed",
        writes=0,
        last_test_passed=None,
        tool_calls=[{
            "tool_name": "read_file",
            "success": True,
            "requires_approval": False,
            "approval_status": None,
            "error": None,
        }],
    )
    verified_write = make_report(
        task_id="bbbbbbbbbbbb",
        status="completed",
        writes=1,
        last_test_passed=True,
        tool_calls=[
            {
                "tool_name": "write_file",
                "success": True,
                "requires_approval": True,
                "approval_status": "approved",
                "error": None,
            },
            {
                "tool_name": "run_tests",
                "success": True,
                "requires_approval": True,
                "approval_status": "approved",
                "error": None,
            },
        ],
    )
    write_report(tmp_path / "read.json", read_only)
    write_report(tmp_path / "write.json", verified_write)
    (tmp_path / "broken.json").write_text("not-json", encoding="utf-8")

    summary = evaluate_report_files(tmp_path.glob("*.json"))

    assert summary.total_reports == 2
    assert summary.skipped_reports == 1
    assert summary.completion_rate == 1.0
    assert summary.verification_compliance_rate == 1.0
    assert summary.tool_success_rate == 1.0
    assert summary.approval_safety_rate == 1.0
    assert summary.average_steps == 4


def test_empty_evaluation_uses_none_for_undefined_rates() -> None:
    summary = evaluate_report_files([])

    assert summary.total_reports == 0
    assert summary.completion_rate is None
    assert summary.verification_compliance_rate is None
    assert summary.tool_success_rate is None
    assert summary.approval_safety_rate is None


def test_write_evaluation_creates_machine_readable_json(
    tmp_path: Path,
) -> None:
    summary = evaluate_report_files([])
    output = write_evaluation(summary, tmp_path / "evals" / "latest.json")
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload["schema_version"] == 1
    assert payload["total_reports"] == 0
    assert payload["completion_rate"] is None
    assert not output.with_suffix(".json.tmp").exists()
