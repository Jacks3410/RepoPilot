from pathlib import Path

import pytest

from repopilot.checkpoint import TaskCheckpointStore
from repopilot.state import TaskState, TaskStatus


def make_running_state(tmp_path: Path) -> TaskState:
    state = TaskState.create("修复接口", tmp_path, max_steps=8)
    state.start()
    state.begin_step("调用模型")
    state.verification = {
        "successful_writes": 1,
        "test_runs": 0,
    }
    return state


def test_checkpoint_round_trip_preserves_running_state(
    tmp_path: Path,
) -> None:
    store = TaskCheckpointStore(tmp_path)
    state = make_running_state(tmp_path)
    state.tool_calls.append({"tool_name": "read_file", "success": True})

    path = store.save(state)
    restored = store.load(state.task_id)

    assert path.exists()
    assert restored.task_id == state.task_id
    assert restored.status == TaskStatus.RUNNING
    assert restored.step_count == 1
    assert restored.verification["successful_writes"] == 1
    assert restored.tool_calls[0]["tool_name"] == "read_file"


def test_checkpoint_redacts_api_key(tmp_path: Path) -> None:
    store = TaskCheckpointStore(tmp_path)
    state = make_running_state(tmp_path)
    state.goal = "检查 OPENAI_API_KEY=sk-exampleSecret123456"

    path = store.save(state)
    raw = path.read_text(encoding="utf-8")
    restored = store.load(state.task_id)

    assert "sk-exampleSecret123456" not in raw
    assert "[REDACTED]" in restored.goal


def test_latest_recoverable_skips_completed_and_corrupt_files(
    tmp_path: Path,
) -> None:
    store = TaskCheckpointStore(tmp_path)
    running = make_running_state(tmp_path)
    store.save(running)

    completed = TaskState.create("已完成任务", tmp_path)
    completed.start()
    completed.complete()
    store.save(completed)

    corrupt = store.checkpoints_dir / "aaaaaaaaaaaa.json"
    corrupt.write_text("not-json", encoding="utf-8")

    restored = store.latest_recoverable()

    assert restored is not None
    assert restored.task_id == running.task_id


def test_checkpoint_rejects_invalid_task_id(tmp_path: Path) -> None:
    store = TaskCheckpointStore(tmp_path)

    with pytest.raises(ValueError, match="任务 ID 格式无效"):
        store.load("../outside")


def test_checkpoint_rejects_mismatched_payload_task_id(
    tmp_path: Path,
) -> None:
    store = TaskCheckpointStore(tmp_path)
    state = make_running_state(tmp_path)
    path = store.save(state)
    content = path.read_text(encoding="utf-8").replace(
        state.task_id,
        "bbbbbbbbbbbb",
        1,
    )
    path.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match="任务 ID 与文件名不一致"):
        store.load(state.task_id)
