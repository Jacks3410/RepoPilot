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
    assert summary.passed_cases == 1
    assert summary.pass_rate == 1.0
    assert summary.total_tokens == 10
    assert summary.results[0].tool_names == ("read_file",)
