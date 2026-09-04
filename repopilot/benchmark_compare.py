from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Iterable


@dataclass(frozen=True)
class LoadedBenchmarkRun:
    model_id: str
    run_id: str
    case_results: tuple[tuple[str, bool], ...]
    pass_rate: float
    average_steps: float
    total_tokens: int


@dataclass(frozen=True)
class ModelComparison:
    rank: int
    model_id: str
    run_count: int
    average_pass_rate: float
    average_steps: float
    total_tokens: int
    average_tokens_per_case: float
    case_pass_rates: dict[str, float]


@dataclass(frozen=True)
class BenchmarkComparison:
    comparison_version: int
    benchmark_version: int
    generated_at: str
    case_ids: tuple[str, ...]
    valid_runs: int
    skipped_files: int
    models: tuple[ModelComparison, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["models"] = [asdict(model) for model in self.models]
        return payload


def load_benchmark_run(path: Path) -> LoadedBenchmarkRun:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("benchmark_version") != 1:
        raise ValueError("不支持的 Benchmark 结果版本")

    results = payload.get("results")
    if not isinstance(results, list) or not results:
        raise ValueError("Benchmark 结果缺少任务明细")

    case_results: list[tuple[str, bool]] = []
    seen_cases: set[str] = set()
    for result in results:
        if not isinstance(result, dict):
            raise ValueError("Benchmark 任务结果必须是对象")
        case_id = str(result.get("case_id", ""))
        passed = result.get("passed")
        if not case_id or case_id in seen_cases or not isinstance(passed, bool):
            raise ValueError("Benchmark 任务结果无效或重复")
        seen_cases.add(case_id)
        case_results.append((case_id, passed))

    model_id = str(payload.get("model_id", "")).strip()
    run_id = str(payload.get("run_id", "")).strip()
    if not model_id or not run_id:
        raise ValueError("Benchmark 结果缺少模型或运行 ID")

    return LoadedBenchmarkRun(
        model_id=model_id,
        run_id=run_id,
        case_results=tuple(sorted(case_results)),
        pass_rate=round(
            sum(passed for _, passed in case_results) / len(case_results),
            4,
        ),
        average_steps=float(payload.get("average_steps", 0)),
        total_tokens=int(payload.get("total_tokens", 0)),
    )


def compare_benchmark_files(
    paths: Iterable[Path],
) -> BenchmarkComparison:
    candidates: list[LoadedBenchmarkRun] = []
    skipped = 0

    for path in paths:
        try:
            run = load_benchmark_run(path)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            skipped += 1
            continue

        candidates.append(run)

    if not candidates:
        raise ValueError("没有可比较的 Benchmark 结果")

    cohorts: dict[tuple[str, ...], list[LoadedBenchmarkRun]] = {}
    for run in candidates:
        signature = tuple(case_id for case_id, _ in run.case_results)
        cohorts.setdefault(signature, []).append(run)

    expected_cases, runs = max(
        cohorts.items(),
        key=lambda item: len(item[1]),
    )
    skipped += len(candidates) - len(runs)

    unique_runs: list[LoadedBenchmarkRun] = []
    seen_runs: set[tuple[str, str]] = set()
    for run in runs:
        identity = run.model_id, run.run_id
        if identity in seen_runs:
            skipped += 1
            continue
        seen_runs.add(identity)
        unique_runs.append(run)
    runs = unique_runs

    grouped: dict[str, list[LoadedBenchmarkRun]] = {}
    for run in runs:
        grouped.setdefault(run.model_id, []).append(run)

    unranked: list[ModelComparison] = []
    for model_id, model_runs in grouped.items():
        case_pass_rates = {
            case_id: round(
                sum(
                    dict(run.case_results)[case_id]
                    for run in model_runs
                ) / len(model_runs),
                4,
            )
            for case_id in expected_cases
        }
        total_tokens = sum(run.total_tokens for run in model_runs)
        total_case_executions = len(model_runs) * len(expected_cases)
        unranked.append(ModelComparison(
            rank=0,
            model_id=model_id,
            run_count=len(model_runs),
            average_pass_rate=round(
                mean(run.pass_rate for run in model_runs),
                4,
            ),
            average_steps=round(
                mean(run.average_steps for run in model_runs),
                3,
            ),
            total_tokens=total_tokens,
            average_tokens_per_case=round(
                total_tokens / total_case_executions,
                3,
            ),
            case_pass_rates=case_pass_rates,
        ))

    ordered = sorted(
        unranked,
        key=lambda item: (
            -item.average_pass_rate,
            item.average_steps,
            item.average_tokens_per_case,
            item.model_id,
        ),
    )
    ranked = tuple(
        ModelComparison(
            rank=index,
            model_id=item.model_id,
            run_count=item.run_count,
            average_pass_rate=item.average_pass_rate,
            average_steps=item.average_steps,
            total_tokens=item.total_tokens,
            average_tokens_per_case=item.average_tokens_per_case,
            case_pass_rates=item.case_pass_rates,
        )
        for index, item in enumerate(ordered, start=1)
    )

    return BenchmarkComparison(
        comparison_version=1,
        benchmark_version=1,
        generated_at=datetime.now(timezone.utc).isoformat(),
        case_ids=expected_cases,
        valid_runs=len(runs),
        skipped_files=skipped,
        models=ranked,
    )


def render_markdown(comparison: BenchmarkComparison) -> str:
    lines = [
        "# RepoPilot 模型评测对比",
        "",
        "| 排名 | 模型 | 运行次数 | 平均通过率 | 平均步骤 | 单任务平均 Token |",
        "| ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    for model in comparison.models:
        safe_model = (
            model.model_id.replace("|", "\\|").replace("\n", " ")
        )
        lines.append(
            f"| {model.rank} | {safe_model} | {model.run_count} | "
            f"{model.average_pass_rate:.1%} | {model.average_steps:.2f} | "
            f"{model.average_tokens_per_case:.1f} |"
        )

    lines.extend(["", "## 分任务通过率", ""])
    header = "| 模型 | " + " | ".join(comparison.case_ids) + " |"
    separator = "| --- | " + " | ".join(
        "---:" for _ in comparison.case_ids
    ) + " |"
    lines.extend([header, separator])
    for model in comparison.models:
        safe_model = (
            model.model_id.replace("|", "\\|").replace("\n", " ")
        )
        rates = " | ".join(
            f"{model.case_pass_rates[case_id]:.1%}"
            for case_id in comparison.case_ids
        )
        lines.append(f"| {safe_model} | {rates} |")
    return "\n".join(lines) + "\n"


def write_comparison(
    comparison: BenchmarkComparison,
    json_output: Path,
    markdown_output: Path,
) -> tuple[Path, Path]:
    json_output = Path(json_output)
    markdown_output = Path(markdown_output)
    json_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)

    json_temporary = json_output.with_suffix(json_output.suffix + ".tmp")
    markdown_temporary = markdown_output.with_suffix(
        markdown_output.suffix + ".tmp"
    )
    json_temporary.write_text(
        json.dumps(comparison.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    markdown_temporary.write_text(
        render_markdown(comparison),
        encoding="utf-8",
    )
    json_temporary.replace(json_output)
    markdown_temporary.replace(markdown_output)
    return json_output, markdown_output
