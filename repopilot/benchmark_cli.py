from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

from repopilot.benchmark import (
    load_benchmark_cases,
    run_benchmark,
    write_benchmark_summary,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the RepoPilot benchmark.")
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("evals/benchmark.json"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".repopilot/benchmark_results"),
    )
    parser.add_argument("--yes", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    api_key = os.environ.get("OPENAI_API_KEY")
    model_id = os.environ.get("OPENAI_MODEL_ID", "unknown-model")
    if not api_key:
        raise SystemExit("错误：尚未配置 OPENAI_API_KEY")

    cases = load_benchmark_cases(args.cases)
    print(f"即将使用 {model_id} 运行 {len(cases)} 个固定评测任务。")
    print("评测会调用模型并消耗 API 额度，但只操作隔离工作区。")
    if not args.yes:
        answer = input("是否继续？输入 y 确认：").strip().lower()
        if answer not in {"y", "yes"}:
            print("已取消评测。")
            return

    summary = run_benchmark(
        cases=cases,
        workspaces_root=Path(".repopilot/benchmark_workspaces"),
        model_id=model_id,
    )
    safe_model_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", model_id)
    output = args.output_dir / f"{safe_model_id}-{summary.run_id}.json"
    write_benchmark_summary(summary, output)

    print("\n" + "=" * 60)
    print(f"模型：{summary.model_id}")
    print(f"有效任务：{summary.valid_cases}/{summary.total_cases}")
    print(f"基础设施失败：{summary.infrastructure_failures}")
    print(f"通过任务：{summary.passed_cases}/{summary.valid_cases}")
    print(
        "通过率："
        f"{summary.pass_rate:.1%}" if summary.pass_rate is not None else "通过率：N/A"
    )
    print(f"平均步骤：{summary.average_steps}")
    print(f"总 Token：{summary.total_tokens}")
    print(f"限流/瞬时故障重试：{summary.total_retries}")
    print(f"累计重试等待：{summary.total_retry_wait_ms / 1000:.1f} 秒")
    print(f"结果已保存：{output}")

    if summary.infrastructure_failures:
        raise SystemExit("评测包含基础设施错误，结果不会进入模型排行。")


if __name__ == "__main__":
    main()
