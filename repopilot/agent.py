from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from core.llm import call_llm
from repopilot.approval import ApprovalGate
from repopilot.execution_tools import build_execution_tools
from repopilot.file_tools import build_workspace_tools
from repopilot.state import TaskState, TaskStatus
from repopilot.verification import VerificationTracker
from repopilot.workspace import Workspace


SYSTEM_PROMPT = """
你是 RepoPilot，一个软件工程 Agent。

规则：
1. 回答仓库相关问题前，必须先使用工具读取真实文件。
2. 所有路径必须相对于仓库根目录。
3. 不能访问仓库之外的文件。
4. 修改文件前，必须先读取相关文件。
5. 需要修改文件时调用 write_file，写入操作由用户审批。
6. 修改代码后必须调用 run_tests 验证。
7. 测试失败时，应分析测试输出、继续修复并重新运行测试。
8. 用户拒绝操作后，不能把该操作描述为成功。
9. 不要声称执行了没有实际执行的操作。
10. 只有修改后的测试通过，才能声称代码任务完成。
""".strip()


LLMCall = Callable[..., dict[str, Any]]


class RepoAgent:
    def __init__(
        self,
        workspace: Workspace,
        max_steps: int = 8,
        llm_call: LLMCall = call_llm,
        approval_gate: ApprovalGate | None = None,
    ) -> None:
        self.workspace = workspace
        self.max_steps = max_steps
        self.llm_call = llm_call

        self.tools = build_workspace_tools(
            workspace,
            approval_gate=approval_gate,
        )

        if approval_gate is not None:
            self.tools.extend(
                build_execution_tools(
                    workspace=workspace,
                    approval_gate=approval_gate,
                )
            )

        self.tool_map = {tool.name: tool for tool in self.tools}

    def run(self, goal: str) -> TaskState:
        state = TaskState.create(
            goal=goal,
            workspace=self.workspace.root,
            max_steps=self.max_steps,
        )
        state.start()

        verification = VerificationTracker()
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

                messages.append(
                    self._assistant_history_message(assistant)
                )

                content = assistant.get("content", "")
                tool_calls = assistant.get("tool_calls") or []

                if not tool_calls:
                    blocker = verification.completion_blocker()

                    if blocker:
                        state.record(f"完成校验被阻止：{blocker}")
                        messages.append({
                            "role": "user",
                            "content": (
                                f"你现在不能结束任务：{blocker}"
                                "请继续使用工具完成验证；"
                                "如果测试失败，请先修复再重新测试。"
                            ),
                        })
                        print(f"\n[Verification Guard] {blocker}\n")
                        continue

                    if content:
                        print(f"\nRepoPilot：{content}\n")

                    state.complete()
                    break

                if content:
                    print(f"\nRepoPilot：{content}\n")

                for tool_call in tool_calls:
                    result = self._execute_tool(tool_call)
                    messages.append(result)

                    tool_name = (
                        tool_call.get("function", {}).get("name", "")
                    )
                    verification.record_tool_result(
                        tool_name,
                        result["content"],
                    )
                    state.record(f"执行工具：{tool_name}")

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