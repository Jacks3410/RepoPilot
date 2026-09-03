from __future__ import annotations

import json
from collections.abc import Callable
from time import perf_counter
from typing import Any

from core.llm import call_llm
from repopilot.approval import ApprovalGate
from repopilot.audit import build_tool_audit_record
from repopilot.checkpoint import TaskCheckpointStore
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
11. 系统会限制最大修复次数；达到上限后必须停止。
""".strip()


LLMCall = Callable[..., dict[str, Any]]


class RepoAgent:
    def __init__(
        self,
        workspace: Workspace,
        max_steps: int = 8,
        llm_call: LLMCall = call_llm,
        approval_gate: ApprovalGate | None = None,
        max_repair_attempts: int = 3,
        checkpoint_store: TaskCheckpointStore | None = None,
    ) -> None:
        if max_repair_attempts < 0:
            raise ValueError("最大修复次数不能小于 0")

        self.workspace = workspace
        self.max_steps = max_steps
        self.llm_call = llm_call
        self.max_repair_attempts = max_repair_attempts
        self.checkpoint_store = checkpoint_store

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

    def run(
        self,
        goal: str,
        resume_state: TaskState | None = None,
    ) -> TaskState:
        if resume_state is None:
            state = TaskState.create(
                goal=goal,
                workspace=self.workspace.root,
                max_steps=self.max_steps,
            )
            state.start()
            verification = VerificationTracker(
                max_repair_attempts=self.max_repair_attempts
            )
            messages: list[dict[str, Any]] = [
                {"role": "user", "content": goal}
            ]
        else:
            state = self._prepare_resume_state(resume_state)
            verification = VerificationTracker.from_summary(
                state.verification,
                default_max_repair_attempts=self.max_repair_attempts,
            )
            state.record("任务从安全检查点恢复")
            messages = [
                {"role": "user", "content": state.goal},
                {
                    "role": "user",
                    "content": (
                        "这是一次中断恢复。历史模型对话和文件正文没有"
                        "被保存。请重新检查仓库当前状态，再继续任务；"
                        "不要假设中断前的操作已经成功。"
                    ),
                },
            ]

        try:
            self._save_checkpoint(state, verification)

            while state.status == TaskStatus.RUNNING:
                state.begin_step("调用模型")
                self._save_checkpoint(state, verification)

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
                        self._save_checkpoint(state, verification)
                        continue

                    if content:
                        print(f"\nRepoPilot：{content}\n")

                    state.complete()
                    self._save_checkpoint(state, verification)
                    break

                if content:
                    print(f"\nRepoPilot：{content}\n")

                for tool_call in tool_calls:
                    started_at = perf_counter()
                    result = self._execute_tool(tool_call)
                    duration_ms = (perf_counter() - started_at) * 1000
                    messages.append(result)

                    state.tool_calls.append(
                        build_tool_audit_record(
                            tool_call=tool_call,
                            result_content=result["content"],
                            duration_ms=duration_ms,
                        )
                    )

                    tool_name = (
                        tool_call.get("function", {}).get("name", "")
                    )
                    verification.record_tool_result(
                        tool_name,
                        result["content"],
                    )
                    state.record(f"执行工具：{tool_name}")

                    if verification.repair_budget_exhausted():
                        reason = verification.completion_blocker()
                        assert reason is not None
                        state.fail(reason)
                        print(f"\n[Repair Budget] {reason}\n")

                    self._save_checkpoint(state, verification)

                    if state.status != TaskStatus.RUNNING:
                        break

        except Exception as exc:
            if state.status != TaskStatus.BLOCKED:
                state.fail(exc)
            print(f"\n任务执行失败：{exc}")

        state.verification = verification.summary()
        self._save_checkpoint(state, verification)
        return state

    def _prepare_resume_state(self, state: TaskState) -> TaskState:
        if state.workspace.resolve() != self.workspace.root:
            raise ValueError("恢复任务的工作目录与当前工作目录不一致")
        if state.status != TaskStatus.RUNNING:
            raise ValueError("只能恢复处于运行状态的任务")
        return state

    def _save_checkpoint(
        self,
        state: TaskState,
        verification: VerificationTracker,
    ) -> None:
        state.verification = verification.summary()
        if self.checkpoint_store is not None:
            self.checkpoint_store.save(state)

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
