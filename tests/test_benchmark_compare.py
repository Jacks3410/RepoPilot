import json
from pathlib import Path

import pytest

from repopilot.benchmark_compare import (
    compare_benchmark_files,
    load_benchmark_run,
    render_markdown,
    write_comparison,
)


def make_result(
    model_id: str,
    run_id: str,
    passed: tuple[bool, bool],
    average_steps: float,
    total_tokens: int,
) -> dict:
    return {
        "benchmark_version": 1,
        "run_id": run_id,
        "model_id": model_id,
        "average_steps": average_steps,
        "total_tokens": total_tokens,
        "results": [
            {"case_id": "case_a", "passed": passed[0]},
            {"case_id": "case_b", "passed": passed[1]},
        ],
    }


def write_result(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_load_benchmark_run_recalculates_pass_rate(tmp_path: Path) -> None:
    path = tmp_path / "run.json"
    write_result(path, make_result("kimi", "run1", (True, False), 3, 100))

    run = load_benchmark_run(path)

    assert run.model_id == "kimi"
    assert run.pass_rate == 0.5
    assert run.case_results == (("case_a", True), ("case_b", False))


def test_compare_aggregates_runs_and_ranks_models(tmp_path: Path) -> None:
    write_result(
        tmp_path / "kimi-1.json",
        make_result("kimi", "k1", (True, False), 4, 200),
    )
    write_result(
        tmp_path / "kimi-2.json",
        make_result("kimi", "k2", (True, True), 2, 100),
    )
    write_result(
        tmp_path / "deepseek.json",
        make_result("deepseek", "d1", (True, True), 2.5, 120),
    )

    comparison = compare_benchmark_files(tmp_path.glob("*.json"))

    assert comparison.valid_runs == 3
    assert comparison.models[0].model_id == "deepseek"
    assert comparison.models[0].average_pass_rate == 1.0
    assert comparison.models[1].model_id == "kimi"
    assert comparison.models[1].average_pass_rate == 0.75
    assert comparison.models[1].run_count == 2
    assert comparison.models[1].average_tokens_per_case == 75
    assert comparison.models[1].case_pass_rates["case_b"] == 0.5


def test_compare_skips_corrupt_and_incompatible_results(
    tmp_path: Path,
) -> None:
    valid = tmp_path / "valid.json"
    write_result(valid, make_result("kimi", "k1", (True, True), 2, 100))
    write_result(
        tmp_path / "valid-2.json",
        make_result("deepseek", "d1", (True, False), 3, 120),
    )
    (tmp_path / "broken.json").write_text("not-json", encoding="utf-8")
    incompatible = make_result("other", "o1", (True, True), 2, 100)
    incompatible["results"][1]["case_id"] = "different_case"
    write_result(tmp_path / "incompatible.json", incompatible)

    comparison = compare_benchmark_files(sorted(tmp_path.glob("*.json")))

    assert comparison.valid_runs == 2
    assert comparison.skipped_files == 2
    assert comparison.case_ids == ("case_a", "case_b")


def test_compare_deduplicates_same_model_and_run_id(tmp_path: Path) -> None:
    payload = make_result("kimi", "same-run", (True, True), 2, 100)
    write_result(tmp_path / "copy-1.json", payload)
    write_result(tmp_path / "copy-2.json", payload)

    comparison = compare_benchmark_files(tmp_path.glob("*.json"))

    assert comparison.valid_runs == 1
    assert comparison.skipped_files == 1
    assert comparison.models[0].run_count == 1


def test_write_comparison_creates_json_and_markdown(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    write_result(source, make_result("kimi", "k1", (True, True), 2, 100))
    comparison = compare_benchmark_files([source])

    json_path, markdown_path = write_comparison(
        comparison,
        tmp_path / "output" / "latest.json",
        tmp_path / "output" / "latest.md",
    )
    markdown = markdown_path.read_text(encoding="utf-8")

    assert json.loads(json_path.read_text(encoding="utf-8"))[
        "comparison_version"
    ] == 1
    assert "RepoPilot 模型评测对比" in markdown
    assert "kimi" in markdown
    assert render_markdown(comparison) == markdown


def test_compare_requires_at_least_one_valid_result() -> None:
    with pytest.raises(ValueError, match="没有可比较"):
        compare_benchmark_files([])
