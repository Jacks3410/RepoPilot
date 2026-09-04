import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from repopilot.benchmark import (
    BenchmarkCase,
    grade_case,
    load_benchmark_cases,
    prepare_case_workspace,
    run_benchmark,
)
from repopilot.state import TaskState


class FakeLLM:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)

    def __call__(self, **kwargs: Any) -> dict[str, Any]:
        return deepcopy(self.responses.pop(0))


class FailingLLM:
    def __call__(self, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("Error code: 401 - Incorrect API key provided")


def make_read_case() -> BenchmarkCase:
    return BenchmarkCase(
        case_id="read_case",
        goal="读取 README.md",
        files={"README.md": "# Demo\n"},
        allowed_statuses=("completed",),
        required_tools=("read_file",),
        forbidden_tools=("write_file",),
    )


def test_load_committed_benchmark_cases() -> None:
    cases = load_benchmark_cases(Path("evals/benchmark.json"))

    assert len(cases) == 4
    assert {case.case_id for case in cases} == {
        "read_only_understanding",
        "path_escape_defense",
        "bug_fix_with_tests",
        "approval_rejection",
    }


def test_loader_rejects_unsafe_case_id_and_fixture_path(
    tmp_path: Path,
) -> None:
    config = {
        "schema_version": 1,
        "cases": [{
            "id": "../escape",
            "goal": "unsafe",
            "files": {"../secret.txt": "secret"},
        }],
    }
    path = tmp_path / "benchmark.json"
    path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(ValueError, match="任务 ID 无效"):
        load_benchmark_cases(path)


def test_prepare_workspace_and_grade_success(tmp_path: Path) -> None:
    case = make_read_case()
    workspace = prepare_case_workspace(case, tmp_path / "case")
    state = TaskState.create(case.goal, workspace.root)
    state.start()
    state.tool_calls.append({"tool_name": "read_file", "error": None})
    state.complete()

    result = grade_case(case, state)

    assert workspace.read_text("README.md") == "# Demo\n"
    assert result.passed is True
    assert result.valid is True
    assert result.infrastructure_error is None
    assert result.failures == ()


def test_run_benchmark_records_score_and_tokens(tmp_path: Path) -> None:
    case = make_read_case()
    fake_llm = FakeLLM([
        {
            "role": "assistant",
            "content": "",
            "usage": {
                "prompt_tokens": 3,
                "completion_tokens": 2,
                "total_tokens": 5,
            },
            "tool_calls": [{
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "read_file",
                    "arguments": '{"path": "README.md"}',
                },
            }],
        },
        {
            "role": "assistant",
            "content": "项目名称是 Demo。",
            "usage": {
                "prompt_tokens": 4,
                "completion_tokens": 1,
                "total_tokens": 5,
            },
        },
    ])

    summary = run_benchmark(
        cases=[case],
        workspaces_root=tmp_path / "workspaces",
        model_id="fake-model",
        llm_call_factory=lambda selected_case: fake_llm,
    )

    assert summary.total_cases == 1
    assert summary.valid_cases == 1
    assert summary.infrastructure_failures == 0
    assert summary.passed_cases == 1
    assert summary.pass_rate == 1.0
    assert summary.total_tokens == 10
    assert summary.results[0].tool_names == ("read_file",)


def test_authentication_failure_is_not_scored_as_model_failure(
    tmp_path: Path,
) -> None:
    case = make_read_case()
    state = TaskState.create(case.goal, tmp_path)
    state.start()
    state.fail("Error code: 401 - Incorrect API key provided")

    result = grade_case(case, state)

    assert result.valid is False
    assert result.passed is False
    assert result.infrastructure_error == "authentication"


def test_run_benchmark_excludes_infrastructure_failure_from_summary(
    tmp_path: Path,
) -> None:
    summary = run_benchmark(
        cases=[make_read_case()],
        workspaces_root=tmp_path / "workspaces",
        model_id="unavailable-model",
        llm_call_factory=lambda selected_case: FailingLLM(),
    )

    assert summary.benchmark_version == 2
    assert summary.total_cases == 1
    assert summary.valid_cases == 0
    assert summary.infrastructure_failures == 1
    assert summary.passed_cases == 0
    assert summary.pass_rate is None
    assert summary.average_steps is None
    assert summary.total_tokens == 0
    assert summary.average_tokens is None
