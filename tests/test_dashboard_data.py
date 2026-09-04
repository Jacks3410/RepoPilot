import json
from pathlib import Path

from repopilot.dashboard_data import load_dashboard_snapshot
from repopilot.run_report import RunReportWriter
from repopilot.state import TaskState


def test_empty_dashboard_has_safe_defaults(tmp_path: Path) -> None:
    snapshot = load_dashboard_snapshot(tmp_path)

    assert snapshot.evaluation.total_reports == 0
    assert snapshot.reports == ()
    assert snapshot.comparison is None


def test_dashboard_loads_v2_reports_and_comparison(tmp_path: Path) -> None:
    state = TaskState.create("读取 README", tmp_path)
    state.start()
    state.complete()
    RunReportWriter(tmp_path).write(state)

    comparison_path = (
        tmp_path / ".repopilot" / "comparisons" / "latest.json"
    )
    comparison_path.parent.mkdir(parents=True)
    comparison_path.write_text(
        json.dumps({
            "comparison_version": 1,
            "models": [{"model_id": "kimi"}],
        }),
        encoding="utf-8",
    )

    snapshot = load_dashboard_snapshot(tmp_path)

    assert snapshot.evaluation.total_reports == 1
    assert len(snapshot.reports) == 1
    assert snapshot.comparison is not None
    assert snapshot.comparison["models"][0]["model_id"] == "kimi"


def test_dashboard_ignores_broken_display_data_but_counts_it(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / ".repopilot" / "runs"
    reports_dir.mkdir(parents=True)
    (reports_dir / "broken.json").write_text("not-json", encoding="utf-8")
    comparison_path = (
        tmp_path / ".repopilot" / "comparisons" / "latest.json"
    )
    comparison_path.parent.mkdir(parents=True)
    comparison_path.write_text("[]", encoding="utf-8")

    snapshot = load_dashboard_snapshot(tmp_path)

    assert snapshot.reports == ()
    assert snapshot.evaluation.skipped_reports == 1
    assert snapshot.comparison is None
