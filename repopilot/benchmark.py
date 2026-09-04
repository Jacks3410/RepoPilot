from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from statistics import mean
from typing import Any, Callable
from uuid import uuid4

from core.llm import call_llm
from repopilot.agent import LLMCall, RepoAgent
from repopilot.approval import ApprovalGate, ApprovalRequest
from repopilot.run_report import RunReportWriter
from repopilot.state import TaskState
from repopilot.test_runner import TestRunner
from repopilot.workspace import Workspace


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    goal: str
    files: dict[str, str]
    allowed_statuses: tuple[str, ...]
    required_tools: tuple[str, ...] = ()
    forbidden_tools: tuple[str, ...] = ()
    require_test_passed: bool | None = None
    minimum_rejections: int = 0
    required_error_substrings: tuple[str, ...] = ()
    approval_policy: str = "approve_all"


@dataclass(frozen=True)
class BenchmarkCaseResult:
    case_id: str
    valid: bool
    passed: bool
    failures: tuple[str, ...]
    infrastructure_error: str | None
    status: str
    step_count: int
    total_tokens: int
    tool_names: tuple[str, ...]
    task_id: str


@dataclass(frozen=True)
class BenchmarkSummary:
    benchmark_version: int
    run_id: str
    model_id: str
    generated_at: str
    total_cases: int
    valid_cases: int
    infrastructure_failures: int
    passed_cases: int
    pass_rate: float | None
    average_steps: float | None
    total_tokens: int
    average_tokens: float | None
    results: tuple[BenchmarkCaseResult, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["results"] = [asdict(result) for result in self.results]
        return payload


LLMCallFactory = Callable[[BenchmarkCase], LLMCall]

_INFRASTRUCTURE_ERRORS = (
    ("401", "authentication"),
    ("incorrect api key", "authentication"),
    ("authentication", "authentication"),
    ("429", "rate_limit"),
    ("rate limit", "rate_limit"),
    ("connection error", "connection"),
    ("apiconnectionerror", "connection"),
    ("timed out", "timeout"),
    ("timeout", "timeout"),
)


def _validate_fixture_path(path: str) -> None:
    candidate = PurePosixPath(path)
    if candidate.is_absolute() or ".." in candidate.parts or not path:
        raise ValueError(f"Benchmark 文件路径不安全：{path}")


def load_benchmark_cases(path: Path) -> list[BenchmarkCase]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("不支持的 Benchmark 配置版本")

    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("Benchmark 至少需要一个任务")

    cases: list[BenchmarkCase] = []
    seen_ids: set[str] = set()
    for raw in raw_cases:
        if not isinstance(raw, dict):
            raise ValueError("Benchmark 任务必须是对象")

        case_id = str(raw.get("id", ""))
        if (
            not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", case_id)
            or case_id in seen_ids
        ):
            raise ValueError(f"Benchmark 任务 ID 无效或重复：{case_id}")
        seen_ids.add(case_id)

        files = raw.get("files", {})
        if not isinstance(files, dict):
            raise ValueError(f"Benchmark files 必须是对象：{case_id}")
        for fixture_path in files:
            _validate_fixture_path(str(fixture_path))

        policy = str(raw.get("approval_policy", "approve_all"))
        if policy not in {"approve_all", "reject_writes"}:
            raise ValueError(f"未知审批策略：{policy}")

        cases.append(BenchmarkCase(
            case_id=case_id,
            goal=str(raw.get("goal", "")),
            files={str(key): str(value) for key, value in files.items()},
            allowed_statuses=tuple(raw.get("allowed_statuses", ["completed"])),
            required_tools=tuple(raw.get("required_tools", [])),
            forbidden_tools=tuple(raw.get("forbidden_tools", [])),
            require_test_passed=raw.get("require_test_passed"),
            minimum_rejections=int(raw.get("minimum_rejections", 0)),
            required_error_substrings=tuple(
                raw.get("required_error_substrings", [])
            ),
            approval_policy=policy,
        ))
    return cases


def prepare_case_workspace(case: BenchmarkCase, root: Path) -> Workspace:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    workspace = Workspace(root)
    for path, content in case.files.items():
        workspace.write_text(path, content)
    return workspace


def grade_case(case: BenchmarkCase, state: TaskState) -> BenchmarkCaseResult:
    failures: list[str] = []
    tool_names = tuple(
        str(record.get("tool_name", "")) for record in state.tool_calls
    )
    errors = "\n".join(
        str(record.get("error") or "") for record in state.tool_calls
    )
    last_error = str(state.last_error or "")
    normalized_error = last_error.lower()
    infrastructure_error = next(
        (
            category
            for marker, category in _INFRASTRUCTURE_ERRORS
            if marker in normalized_error
        ),
        None,
    )

    if infrastructure_error is not None:
        return BenchmarkCaseResult(
            case_id=case.case_id,
            valid=False,
            passed=False,
            failures=(f"基础设施错误：{infrastructure_error}",),
            infrastructure_error=infrastructure_error,
            status=state.status.value,
            step_count=state.step_count,
            total_tokens=int(state.model_usage.get("total_tokens", 0)),
            tool_names=tool_names,
            task_id=state.task_id,
        )

    if state.status.value not in case.allowed_statuses:
        failures.append(f"状态不符合预期：{state.status.value}")
    for tool_name in case.required_tools:
        if tool_name not in tool_names:
            failures.append(f"缺少必要工具：{tool_name}")
    for tool_name in case.forbidden_tools:
        if tool_name in tool_names:
            failures.append(f"调用了禁止工具：{tool_name}")
    if (
        case.require_test_passed is not None
        and state.verification.get("last_test_passed")
        is not case.require_test_passed
    ):
        failures.append("测试验证状态不符合预期")

    rejection_count = sum(
        record.get("approval_status") == "rejected"
        for record in state.tool_calls
    )
    if rejection_count < case.minimum_rejections:
        failures.append("审批拒绝次数不足")
    for expected_error in case.required_error_substrings:
        if expected_error not in errors:
            failures.append(f"缺少预期错误：{expected_error}")

    return BenchmarkCaseResult(
        case_id=case.case_id,
        valid=True,
        passed=not failures,
        failures=tuple(failures),
        infrastructure_error=None,
        status=state.status.value,
        step_count=state.step_count,
        total_tokens=int(state.model_usage.get("total_tokens", 0)),
        tool_names=tool_names,
        task_id=state.task_id,
    )


def _approval_handler(case: BenchmarkCase) -> Callable[[ApprovalRequest], bool]:
    def handler(request: ApprovalRequest) -> bool:
        if case.approval_policy == "reject_writes":
            return request.action != "write_file"
        return True
    return handler


def run_benchmark(
    cases: list[BenchmarkCase],
    workspaces_root: Path,
    model_id: str,
    llm_call_factory: LLMCallFactory | None = None,
) -> BenchmarkSummary:
    run_id = uuid4().hex[:12]
    results: list[BenchmarkCaseResult] = []
    factory = llm_call_factory or (lambda case: call_llm)

    for case in cases:
        case_root = Path(workspaces_root) / run_id / case.case_id
        workspace = prepare_case_workspace(case, case_root)
        runner = TestRunner(
            workspace=workspace,
            command=(sys.executable, "-m", "pytest", "-q"),
            timeout_seconds=30,
        )
        agent = RepoAgent(
            workspace=workspace,
            max_steps=10,
            llm_call=factory(case),
            approval_gate=ApprovalGate(handler=_approval_handler(case)),
            test_runner=runner,
        )
        state = agent.run(case.goal)
        RunReportWriter(workspace.root).write(state)
        results.append(grade_case(case, state))

    valid_results = [result for result in results if result.valid]
    passed = sum(result.passed for result in valid_results)
    total_tokens = sum(result.total_tokens for result in valid_results)
    return BenchmarkSummary(
        benchmark_version=2,
        run_id=run_id,
        model_id=model_id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        total_cases=len(results),
        valid_cases=len(valid_results),
        infrastructure_failures=len(results) - len(valid_results),
        passed_cases=passed,
        pass_rate=(
            round(passed / len(valid_results), 4)
            if valid_results else None
        ),
        average_steps=(
            round(mean(result.step_count for result in valid_results), 3)
            if valid_results else None
        ),
        total_tokens=total_tokens,
        average_tokens=(
            round(total_tokens / len(valid_results), 3)
            if valid_results else None
        ),
        results=tuple(results),
    )


def write_benchmark_summary(
    summary: BenchmarkSummary,
    output: Path,
) -> Path:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(summary.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(output)
    return output
