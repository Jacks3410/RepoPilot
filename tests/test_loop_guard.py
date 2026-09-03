from repopilot.loop_guard import ToolLoopGuard


def make_record(
    tool_name: str = "read_file",
    call_fingerprint: str = "call-a",
    result_fingerprint: str = "result-a",
) -> dict:
    return {
        "tool_name": tool_name,
        "call_fingerprint": call_fingerprint,
        "result_fingerprint": result_fingerprint,
    }


def test_guard_blocks_third_identical_observation() -> None:
    guard = ToolLoopGuard(max_repeats=3)
    record = make_record()

    assert guard.observe(record) is None
    assert guard.observe(record) is None
    assert "read_file 已重复 3 次" in str(guard.observe(record))


def test_changed_result_is_treated_as_progress() -> None:
    guard = ToolLoopGuard(max_repeats=3)

    assert guard.observe(make_record(result_fingerprint="result-a")) is None
    assert guard.observe(make_record(result_fingerprint="result-b")) is None
    assert guard.observe(make_record(result_fingerprint="result-c")) is None


def test_new_write_clears_previous_read_history() -> None:
    guard = ToolLoopGuard(max_repeats=3)
    read = make_record()

    guard.observe(read)
    guard.observe(read)
    guard.observe(make_record("write_file", "write-a", "written-a"))

    assert guard.observe(read) is None


def test_guard_restores_recent_history_from_audit() -> None:
    record = make_record()
    guard = ToolLoopGuard.from_audit_records(
        [record, record],
        max_repeats=3,
    )

    assert "read_file 已重复 3 次" in str(guard.observe(record))
