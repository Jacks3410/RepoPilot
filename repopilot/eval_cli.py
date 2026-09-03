from __future__ import annotations

import argparse
import sys
from pathlib import Path

from repopilot.evaluation import evaluate_directory, write_evaluation


def _format_rate(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.1%}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Aggregate RepoPilot v2 run reports into evaluation metrics."
    )
    parser.add_argument(
        "--reports",
        type=Path,
        default=Path(".repopilot/runs"),
        help="Directory containing RepoPilot run reports.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".repopilot/evals/latest.json"),
        help="Path for the generated evaluation JSON.",
    )
    return parser


def main() -> None:
    if not sys.stdout.isatty() and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = build_parser().parse_args()
    summary = evaluate_directory(args.reports)
    output = write_evaluation(summary, args.output)

    print("=" * 60)
    print("RepoPilot 离线评测")
    print("=" * 60)
    print(f"有效报告：{summary.total_reports}")
    print(f"跳过报告：{summary.skipped_reports}")
    print(f"任务完成率：{_format_rate(summary.completion_rate)}")
    print(
        "写入后验证合规率："
        f"{_format_rate(summary.verification_compliance_rate)}"
    )
    print(f"工具成功率：{_format_rate(summary.tool_success_rate)}")
    print(f"审批安全率：{_format_rate(summary.approval_safety_rate)}")
    print(f"审批违规数：{summary.approval_violations}")
    print(f"路径越界拦截数：{summary.path_escape_blocks}")
    print(f"平均执行步数：{summary.average_steps}")
    print(f"评测结果已保存：{output}")


if __name__ == "__main__":
    main()
