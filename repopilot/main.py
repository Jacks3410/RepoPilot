from __future__ import annotations

import os
from pathlib import Path

from repopilot.agent import RepoAgent
from repopilot.approval import ApprovalGate, terminal_approval
from repopilot.checkpoint import TaskCheckpointStore
from repopilot.git_repo import GitCommandError, GitRepository
from repopilot.run_report import RunReportWriter
from repopilot.state import TaskStatus
from repopilot.workspace import Workspace


def main() -> None:
    print("=" * 60)
    print("RepoPilot - 可审计的软件工程 Agent")
    print("=" * 60)

    if not os.environ.get("OPENAI_API_KEY"):
        print("错误：尚未配置 OPENAI_API_KEY")
        return

    try:
        workspace = Workspace(Path.cwd())
        repository = GitRepository(workspace.root)
    except (OSError, GitCommandError) as exc:
        print(f"工作目录初始化失败：{exc}")
        return

    checkpoint_store = TaskCheckpointStore(workspace.root)
    resume_state = checkpoint_store.latest_recoverable()

    if resume_state is not None:
        print("\n检测到未完成任务：")
        print(f"任务 ID：{resume_state.task_id}")
        print(f"任务目标：{resume_state.goal}")
        answer = input("是否从检查点恢复？输入 y 确认：").strip().lower()
        if answer not in {"y", "yes"}:
            resume_state.status = TaskStatus.BLOCKED
            resume_state.record("用户放弃从检查点恢复")
            checkpoint_store.save(resume_state)
            resume_state = None

    if resume_state is None:
        goal = input("请输入仓库开发任务：").strip()
        if not goal:
            print("错误：任务不能为空")
            return
    else:
        goal = resume_state.goal

    approval_gate = ApprovalGate(handler=terminal_approval)

    agent = RepoAgent(
        workspace=workspace,
        max_steps=8,
        approval_gate=approval_gate,
        checkpoint_store=checkpoint_store,
    )
    state = agent.run(goal, resume_state=resume_state)

    print("\n" + "=" * 60)
    print("任务执行摘要")
    print("=" * 60)
    print(f"任务 ID：{state.task_id}")
    print(f"最终状态：{state.status.value}")
    print(f"执行步数：{state.step_count}/{state.max_steps}")

    print("\n" + "=" * 60)
    print("Git 审计报告")
    print("=" * 60)

    git_status = ""
    git_diff = ""

    try:
        git_status = repository.status_short()
        git_diff = repository.diff()
        print(repository.report())
    except GitCommandError as exc:
        print(f"无法生成 Git 审计报告：{exc}")

    try:
        report_path = RunReportWriter(workspace.root).write(
            state=state,
            git_status=git_status,
            git_diff=git_diff,
        )
        relative_report = report_path.relative_to(workspace.root)
        print(f"\n运行报告已保存：{relative_report}")
    except OSError as exc:
        print(f"无法保存运行报告：{exc}")


if __name__ == "__main__":
    main()
