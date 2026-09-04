from __future__ import annotations

import argparse
import sys
from pathlib import Path

from repopilot.benchmark_compare import (
    compare_benchmark_files,
    write_comparison,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare RepoPilot benchmark results across models."
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path(".repopilot/benchmark_results"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".repopilot/comparisons"),
    )
    return parser


def main() -> None:
    if not sys.stdout.isatty() and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = build_parser().parse_args()
    try:
        comparison = compare_benchmark_files(
            sorted(args.results_dir.glob("*.json"))
        )
    except ValueError as exc:
        raise SystemExit(f"无法生成模型对比：{exc}") from exc

    json_path, markdown_path = write_comparison(
        comparison,
        args.output_dir / "latest.json",
        args.output_dir / "latest.md",
    )

    print("=" * 60)
    print("RepoPilot 多模型 Benchmark 对比")
    print("=" * 60)
    for model in comparison.models:
        print(
            f"#{model.rank} {model.model_id}: "
            f"通过率 {model.average_pass_rate:.1%}, "
            f"平均步骤 {model.average_steps:.2f}, "
            f"单任务 Token {model.average_tokens_per_case:.1f}"
        )
    print(f"有效运行：{comparison.valid_runs}")
    print(f"跳过文件：{comparison.skipped_files}")
    print(f"JSON：{json_path}")
    print(f"Markdown：{markdown_path}")


if __name__ == "__main__":
    main()
