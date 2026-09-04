from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import streamlit as st

from repopilot.dashboard_data import DashboardSnapshot, load_dashboard_snapshot


def _rate(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.1%}"


def _status_label(status: str) -> str:
    return {
        "completed": "已完成",
        "failed": "失败",
        "blocked": "已阻断",
        "running": "运行中",
    }.get(status, status or "未知")


def _render_header() -> None:
    st.markdown(
        """
        <div class="rp-header">
          <div class="rp-eyebrow">REPOPILOT CONTROL PLANE</div>
          <h1>让 Coding Agent 的每一步都有证据</h1>
          <p>执行、验证、安全审计与模型评测，一套闭环完成。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_overview(snapshot: DashboardSnapshot) -> None:
    summary = snapshot.evaluation
    columns = st.columns(4)
    metrics = (
        ("任务完成率", _rate(summary.completion_rate), f"{summary.total_reports} 个有效报告"),
        ("验证合规率", _rate(summary.verification_compliance_rate), f"{summary.verified_write_runs}/{summary.write_runs} 个写入任务"),
        ("工具成功率", _rate(summary.tool_success_rate), f"{summary.successful_tool_calls}/{summary.tool_calls} 次调用"),
        ("审批安全率", _rate(summary.approval_safety_rate), f"{summary.approval_violations} 次违规"),
    )
    for column, (label, value, help_text) in zip(columns, metrics):
        column.metric(label, value, help=help_text)

    left, right = st.columns([1.55, 1])
    with left:
        st.subheader("运行质量")
        quality_rows = [
            {"指标": "平均执行步数", "数值": summary.average_steps},
            {"指标": "平均修复次数", "数值": summary.average_repair_attempts},
            {"指标": "路径越界拦截", "数值": summary.path_escape_blocks},
            {"指标": "无进展循环阻断", "数值": summary.loop_blocks},
            {"指标": "主动拒绝操作", "数值": summary.rejected_operations},
        ]
        st.dataframe(quality_rows, width="stretch", hide_index=True)
    with right:
        st.subheader("质量门禁")
        st.markdown(
            """
            - 写入操作必须获得人工审批
            - 修改代码后必须通过测试
            - 最多执行 3 轮自动修复
            - 相同工具结果重复 3 次即阻断
            - 运行轨迹与 Git Diff 自动脱敏
            """
        )

    if summary.total_reports == 0:
        st.info("暂无 v2 运行报告。先运行 `python -m repopilot.main` 生成数据。")


def _render_comparison(snapshot: DashboardSnapshot) -> None:
    comparison = snapshot.comparison
    if comparison is None:
        st.info(
            "暂无多模型对比结果。分别运行 Benchmark 后，再执行 "
            "`python -m repopilot.benchmark_compare_cli`。"
        )
        return

    models = comparison.get("models", [])
    if not models:
        st.info("对比结果中没有可展示的模型。")
        return

    rows = [{
        "排名": model.get("rank"),
        "模型": model.get("model_id"),
        "运行次数": model.get("run_count"),
        "平均通过率": model.get("average_pass_rate"),
        "平均步骤": model.get("average_steps"),
        "单任务 Token": model.get("average_tokens_per_case"),
    } for model in models]
    st.dataframe(
        rows,
        width="stretch",
        hide_index=True,
        column_config={
            "平均通过率": st.column_config.ProgressColumn(
                min_value=0.0,
                max_value=1.0,
                format="percent",
            ),
        },
    )
    st.subheader("模型通过率")
    chart_data = {
        str(model.get("model_id")): float(model.get("average_pass_rate", 0))
        for model in models
    }
    st.bar_chart(chart_data, horizontal=True)

    st.subheader("分任务表现")
    case_rows: list[dict[str, Any]] = []
    for model in models:
        row: dict[str, Any] = {"模型": model.get("model_id")}
        row.update(model.get("case_pass_rates", {}))
        case_rows.append(row)
    st.dataframe(case_rows, width="stretch", hide_index=True)


def _report_label(report: dict[str, Any]) -> str:
    task = report.get("task", {})
    task_id = task.get("task_id", "unknown")
    status = _status_label(str(task.get("status", "")))
    goal = str(task.get("goal", ""))[:36]
    return f"{task_id} · {status} · {goal}"


def _render_audit(snapshot: DashboardSnapshot) -> None:
    if not snapshot.reports:
        st.info("暂无可审计的 v2 运行报告。")
        return

    labels = [_report_label(report) for report in snapshot.reports]
    selected_label = st.selectbox("选择运行记录", labels)
    report = snapshot.reports[labels.index(selected_label)]
    task = report.get("task", {})
    verification = report.get("verification", {})
    usage = report.get("model_usage", {})

    columns = st.columns(4)
    columns[0].metric("状态", _status_label(str(task.get("status", ""))))
    columns[1].metric("执行步数", f"{task.get('step_count', 0)}/{task.get('max_steps', 0)}")
    columns[2].metric("测试次数", verification.get("test_runs", 0))
    columns[3].metric("总 Token", usage.get("total_tokens", 0))

    st.subheader("工具调用轨迹")
    calls = report.get("tool_calls", [])
    call_rows = [{
        "工具": call.get("tool_name"),
        "成功": call.get("success"),
        "审批": call.get("approval_status") or "无需审批",
        "耗时(ms)": call.get("duration_ms"),
        "安全参数": call.get("arguments"),
    } for call in calls]
    if call_rows:
        st.dataframe(call_rows, width="stretch", hide_index=True)
    else:
        st.caption("本次任务没有调用工具。")

    with st.expander("任务事件时间线"):
        for event in report.get("events", []):
            st.code(str(event), language=None)
    with st.expander("脱敏 Git Diff"):
        st.code(report.get("git", {}).get("diff") or "没有代码差异", language="diff")


def _render_architecture() -> None:
    st.markdown(
        """
        <div class="rp-flow">
          <div><b>01 · PERCEIVE</b><span>读取仓库与任务上下文</span></div>
          <div><b>02 · ACT</b><span>最小权限工具 + 人工审批</span></div>
          <div><b>03 · VERIFY</b><span>测试门禁 + 自动修复预算</span></div>
          <div><b>04 · AUDIT</b><span>脱敏轨迹 + Git Diff + 检查点</span></div>
          <div><b>05 · EVALUATE</b><span>固定任务集 + 多模型横评</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.subheader("防护矩阵")
    st.dataframe(
        [
            {"风险": "目录越界", "机制": "根目录路径沙箱", "结果": "执行前拦截"},
            {"风险": "未授权修改", "机制": "Human-in-the-loop", "结果": "显式审批"},
            {"风险": "虚假完成", "机制": "测试验证状态机", "结果": "未通过禁止完成"},
            {"风险": "无限循环", "机制": "步骤/修复/重复调用预算", "结果": "自动阻断"},
            {"风险": "凭证泄露", "机制": "递归脱敏与内容最小化", "结果": "报告不落原文"},
        ],
        width="stretch",
        hide_index=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="RepoPilot Control Plane",
        page_icon="◈",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """
        <style>
          .stApp { background: #08111f; }
          [data-testid="stSidebar"] { background: #0c1727; }
          .rp-header { padding: 1.2rem 0 1.7rem; border-bottom: 1px solid #22324a; margin-bottom: 1.2rem; }
          .rp-eyebrow { color: #5eead4; font-size: .76rem; font-weight: 700; letter-spacing: .18em; }
          .rp-header h1 { color: #f4f7fb; font-size: 2.3rem; margin: .45rem 0 .35rem; letter-spacing: -.03em; }
          .rp-header p { color: #93a4ba; margin: 0; font-size: 1.05rem; }
          [data-testid="stMetric"] { background: #101c2f; border: 1px solid #22324a; border-radius: 10px; padding: 1rem; }
          .rp-flow { display: grid; grid-template-columns: repeat(5, 1fr); gap: .75rem; margin: 1rem 0 2rem; }
          .rp-flow div { min-height: 110px; background: #101c2f; border-top: 3px solid #5eead4; padding: 1rem; border-radius: 8px; }
          .rp-flow b { display: block; color: #5eead4; font-size: .78rem; margin-bottom: .8rem; }
          .rp-flow span { color: #dce5f1; font-size: .92rem; line-height: 1.5; }
          @media (max-width: 900px) { .rp-flow { grid-template-columns: 1fr; } }
        </style>
        """,
        unsafe_allow_html=True,
    )

    project_root = Path.cwd()
    snapshot = load_dashboard_snapshot(project_root)
    _render_header()

    with st.sidebar:
        st.markdown("### RepoPilot")
        st.caption("Auditable · Recoverable · Evaluated")
        st.divider()
        st.text(f"Model  {os.environ.get('OPENAI_MODEL_ID', '未配置')}")
        st.text(f"Runs   {snapshot.evaluation.total_reports}")
        st.text(f"Skipped {snapshot.evaluation.skipped_reports}")
        if st.button("刷新数据", width="stretch"):
            st.rerun()

    overview, comparison, audit, architecture = st.tabs([
        "运行总览",
        "模型对比",
        "任务审计",
        "安全架构",
    ])
    with overview:
        _render_overview(snapshot)
    with comparison:
        _render_comparison(snapshot)
    with audit:
        _render_audit(snapshot)
    with architecture:
        _render_architecture()


if __name__ == "__main__":
    main()
