from copy import deepcopy
from pathlib import Path
from typing import Any

from repopilot.agent import RepoAgent
from repopilot.checkpoint import TaskCheckpointStore
from repopilot.state import TaskState, TaskStatus
from repopilot.workspace import Workspace


class FakeLLM:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(deepcopy(kwargs))
        return self.responses.pop(0)


def test_agent_resumes_from_safe_checkpoint(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("RepoPilot", encoding="utf-8")
    store = TaskCheckpointStore(tmp_path)
    interrupted = TaskState.create("读取 README.md", tmp_path, max_steps=5)
    interrupted.start()
    interrupted.begin_step("调用模型")
    interrupted.verification = {
        "successful_writes": 0,
        "test_runs": 0,
        "repair_attempts": 0,
        "max_repair_attempts": 3,
        "last_test_passed": None,
    }
    store.save(interrupted)

    fake_llm = FakeLLM([
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "read_file",
                    "arguments": '{"path": "README.md"}',
                },
            }],
        },
        {
            "role": "assistant",
            "content": "项目名称是 RepoPilot。",
        },
    ])
    agent = RepoAgent(
        workspace=Workspace(tmp_path),
        max_steps=5,
        llm_call=fake_llm,
        checkpoint_store=store,
    )

    state = agent.run(interrupted.goal, resume_state=store.load(
        interrupted.task_id
    ))

    assert state.status == TaskStatus.COMPLETED
    assert state.step_count == 3
    assert any("安全检查点恢复" in event for event in state.events)
    assert store.latest_recoverable() is None
    assert store.load(state.task_id).status == TaskStatus.COMPLETED
