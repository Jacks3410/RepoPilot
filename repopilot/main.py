from __future__ import annotations

import os
from pathlib import Path

from repopilot.agent import RepoAgent
from repopilot.workspace import Workspace
from repopilot.approval import ApprovalGate, terminal_approval

def main() -> None:
    print("=" * 60)
    print("RepoPilot - 可审计的软件工程 Agent")
    print("=" * 60)

    if not os.environ.get("OPENAI_API_KEY"):
        print("错误：尚未配置 OPENAI_API_KEY")
        return

    goal = input("请输入仓库分析任务：").strip()
    if not goal:
        print("错误：任务不能为空")
        return

    workspace = Workspace(Path.cwd())
    approval_gate = ApprovalGate(handler=terminal_approval)

    agent = RepoAgent(
        workspace=workspace,
        max_steps=8,
        approval_gate=approval_gate,
    )
    state = agent.run(goal)

    print("\n" + "=" * 60)
    print(f"任务 ID：{state.task_id}")
    print(f"最终状态：{state.status.value}")
    print(f"执行步数：{state.step_count}/{state.max_steps}")


if __name__ == "__main__":
    main()