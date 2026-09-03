from copy import deepcopy
from pathlib import Path
from typing import Any

from repopilot.agent import RepoAgent
from repopilot.approval import ApprovalGate
from repopilot.state import TaskStatus
from repopilot.workspace import Workspace


class FakeLLM:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(deepcopy(kwargs))
        return self.responses.pop(0)


def make_tool_call(
    name: str,
    arguments: str = "{}",
    call_id: str = "call_1",
) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": arguments,
                },
            }
        ],
    }


def fake_tool_execution(
    tool_call: dict[str, Any],
) -> dict[str, str]:
    name = tool_call["function"]["name"]

    if name == "write_file":
        content = "已写入文件：demo.py"
    elif name == "run_tests":
        content = "测试状态：PASSED\n退出码：0"
    else:
        content = "工具执行成功"

    return {
        "role": "tool",
        "tool_call_id": tool_call["id"],
        "content": content,
    }


def test_agent_requires_tests_after_write(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_llm = FakeLLM([
        make_tool_call(
            "write_file",
            '{"path": "demo.py", "content": "x = 1"}',
        ),
        {
            "role": "assistant",
            "content": "代码已经完成。",
        },
        make_tool_call("run_tests", call_id="call_2"),
        {
            "role": "assistant",
            "content": "代码修改完成并且测试通过。",
        },
    ])

    agent = RepoAgent(
        workspace=Workspace(tmp_path),
        max_steps=6,
        llm_call=fake_llm,
        approval_gate=ApprovalGate(
            handler=lambda request: True
        ),
    )
    monkeypatch.setattr(
        agent,
        "_execute_tool",
        fake_tool_execution,
    )

    state = agent.run("修改 demo.py")

    assert state.status == TaskStatus.COMPLETED
    assert len(fake_llm.calls) == 4

    guard_message = fake_llm.calls[2]["messages"][-1]
    assert guard_message["role"] == "user"
    assert "不能结束任务" in guard_message["content"]


def test_agent_blocks_when_verification_never_finishes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_llm = FakeLLM([
        make_tool_call(
            "write_file",
            '{"path": "demo.py", "content": "x = 1"}',
        ),
        {
            "role": "assistant",
            "content": "代码已经完成。",
        },
    ])

    agent = RepoAgent(
        workspace=Workspace(tmp_path),
        max_steps=2,
        llm_call=fake_llm,
        approval_gate=ApprovalGate(
            handler=lambda request: True
        ),
    )
    monkeypatch.setattr(
        agent,
        "_execute_tool",
        fake_tool_execution,
    )

    state = agent.run("修改 demo.py")

    assert state.status == TaskStatus.BLOCKED
    assert state.step_count == 2
    assert len(fake_llm.calls) == 2