from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from core.llm import call_llm
from repopilot.file_tools import build_workspace_tools
from repopilot.state import TaskState, TaskStatus
from repopilot.workspace import Workspace


SYSTEM_PROMPT = """
你是 RepoPilot，一个代码仓库分析 Agent。

规则：
1. 回答仓库相关问题前，必须先使用工具读取真实文件。
2. 所有路径必须相对于仓库根目录。
3. 不能访问仓库之外的文件。
4. 当前阶段只有读取权限，不能修改任何文件。
5. 不要声称执行了没有实际执行的操作。
6. 得到足够证据后，直接给出简洁结论。
""".strip()


LLMCall = Callable[..., dict[str, Any]]


class RepoAgent:
    def __init__(
        self,
        workspace: Workspace,
        max_steps: int = 8,
        llm_call: LLMCall = call_llm,
    ) -> None:
        self.workspace = workspace
        self.max_steps = max_steps
        self.llm_call = llm_call
        self.tools = build_workspace_tools(workspace)
        self.tool_map = {tool.name: tool for tool in self.tools}

    def run(self, goal: str) -> TaskState:
        state = TaskState.create(
            goal=goal,
            workspace=self.workspace.root,
            max_steps=self.max_steps,
        )
        state.start()

        messages: list[dict[str, Any]] = [
            {"role": "user", "content": goal}
        ]

        try:
            while state.status == TaskStatus.RUNNING:
                state.begin_step("调用模型")

                assistant = self.llm_call(
                    messages=messages,
                    tools=[tool.to_llm_format() for tool in self.tools],
                    system_prompt=SYSTEM_PROMPT,
                )

                messages.append(self._assistant_history_message(assistant))

                content = assistant.get("content", "")
                if content:
                    print(f"\nRepoPilot：{content}\n")

                tool_calls = assistant.get("tool_calls") or []

                if not tool_calls:
                    state.complete()
                    break

                for tool_call in tool_calls:
                    result = self._execute_tool(tool_call)
                    messages.append(result)
                    state.record(
                        f"执行工具：{tool_call.get('function', {}).get('name', '')}"
                    )

        except Exception as exc:
            if state.status != TaskStatus.BLOCKED:
                state.fail(exc)
            print(f"\n任务执行失败：{exc}")

        return state

    @staticmethod
    def _assistant_history_message(
        assistant: dict[str, Any],
    ) -> dict[str, Any]:
        message: dict[str, Any] = {
            "role": "assistant",
            "content": assistant.get("content", ""),
        }

        if assistant.get("tool_calls"):
            message["tool_calls"] = assistant["tool_calls"]

        return message

    def _execute_tool(
        self,
        tool_call: dict[str, Any],
    ) -> dict[str, str]:
        function = tool_call.get("function", {})
        name = function.get("name", "")
        raw_arguments = function.get("arguments", "{}")

        try:
            arguments = json.loads(raw_arguments)

            if not isinstance(arguments, dict):
                raise ValueError("工具参数必须是 JSON 对象")

            tool = self.tool_map.get(name)
            if tool is None:
                raise ValueError(f"不存在的工具：{name}")

            print(f"  [Tool] {name}({arguments})")
            content = str(tool.execute(**arguments))

        except Exception as exc:
            content = f"工具执行失败：{exc}"

        return {
            "role": "tool",
            "tool_call_id": tool_call.get("id", ""),
            "content": content,
        }