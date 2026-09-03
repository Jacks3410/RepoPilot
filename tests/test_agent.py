from copy import deepcopy
from pathlib import Path
from typing import Any

from repopilot.agent import RepoAgent
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
    arguments: str,
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


def test_agent_executes_tool_then_finishes(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "RepoPilot demo",
        encoding="utf-8",
    )

    fake_llm = FakeLLM([
        make_tool_call("read_file", '{"path": "README.md"}'),
        {
            "role": "assistant",
            "content": "README 内容是 RepoPilot demo。",
        },
    ])

    agent = RepoAgent(
        workspace=Workspace(tmp_path),
        llm_call=fake_llm,
    )
    state = agent.run("读取 README.md")

    assert state.status == TaskStatus.COMPLETED
    assert state.step_count == 2
    assert len(fake_llm.calls) == 2
    assert len(state.tool_calls) == 1
    assert state.tool_calls[0]["tool_name"] == "read_file"
    assert state.tool_calls[0]["success"] is True

    second_messages = fake_llm.calls[1]["messages"]
    assert second_messages[-1]["role"] == "tool"
    assert "RepoPilot demo" in second_messages[-1]["content"]


def test_agent_reports_path_escape_to_model(tmp_path: Path) -> None:
    fake_llm = FakeLLM([
        make_tool_call("read_file", '{"path": "../secret.txt"}'),
        {
            "role": "assistant",
            "content": "该路径位于工作目录之外，无法访问。",
        },
    ])

    agent = RepoAgent(
        workspace=Workspace(tmp_path),
        llm_call=fake_llm,
    )
    state = agent.run("读取工作目录外的文件")

    assert state.status == TaskStatus.COMPLETED

    tool_result = fake_llm.calls[1]["messages"][-1]
    assert tool_result["role"] == "tool"
    assert "拒绝访问" in tool_result["content"]


def test_agent_stops_at_max_steps(tmp_path: Path) -> None:
    fake_llm = FakeLLM([
        make_tool_call("list_files", '{"path": "."}'),
    ])

    agent = RepoAgent(
        workspace=Workspace(tmp_path),
        max_steps=1,
        llm_call=fake_llm,
    )
    state = agent.run("不断查看目录")

    assert state.status == TaskStatus.BLOCKED
    assert state.step_count == 1
    assert len(fake_llm.calls) == 1
