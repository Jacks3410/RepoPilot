from __future__ import annotations

import os
from pathlib import Path

from repopilot.state import TaskState


def main() -> None:
    print("=" * 60)
    print("RepoPilot - 可审计的软件工程 Agent")
    print("=" * 60)

    if not os.environ.get("OPENAI_API_KEY"):
        print("错误：尚未配置 OPENAI_API_KEY")
        kahus
        return

    goal = input("请输入开发任务：").strip()

    try:
        task = TaskState.create(
            goal=goal,
            workspace=Path.cwd(),
            max_steps=12,
        )
        task.start()
        task.begin_step("初始化任务")

        print(f"\n任务 ID：{task.task_id}")
        print(f"任务状态：{task.status.value}")
        print(f"工作目录：{task.workspace}")
        print(f"任务目标：{task.goal}")
        print(f"最大步数：{task.max_steps}")

    except Exception as exc:
        print(f"任务创建失败：{exc}")


if __name__ == "__main__":
    main()