from repopilot.audit import build_tool_audit_record


def make_tool_call(name: str, arguments: str) -> dict:
    return {
        "id": "call_1",
        "type": "function",
        "function": {
            "name": name,
            "arguments": arguments,
        },
    }


def test_write_audit_excludes_file_content() -> None:
    tool_call = make_tool_call(
        "write_file",
        '{"path": "demo.py", "content": "secret source code"}',
    )

    record = build_tool_audit_record(
        tool_call,
        result_content="已写入文件：demo.py",
        duration_ms=12.3456,
    )

    assert record["arguments"] == {"path": "demo.py"}
    assert record["success"] is True
    assert record["approval_status"] == "approved"
    assert record["duration_ms"] == 12.346
    assert "secret source code" not in str(record)


def test_rejected_operation_is_recorded_and_secret_is_redacted() -> None:
    tool_call = make_tool_call("run_tests", "{}")

    record = build_tool_audit_record(
        tool_call,
        result_content=(
            "工具执行失败：用户拒绝操作，OPENAI_API_KEY="
            "sk-exampleSecret123456"
        ),
        duration_ms=1,
    )

    assert record["success"] is False
    assert record["approval_status"] == "rejected"
    assert "sk-exampleSecret123456" not in str(record)
    assert "[REDACTED]" in record["error"]


def test_read_audit_does_not_store_file_result() -> None:
    tool_call = make_tool_call(
        "read_file",
        '{"path": "README.md"}',
    )

    record = build_tool_audit_record(
        tool_call,
        result_content="private file contents",
        duration_ms=2,
    )

    assert record["arguments"] == {"path": "README.md"}
    assert record["success"] is True
    assert record["requires_approval"] is False
    assert record["error"] is None
    assert "private file contents" not in str(record)
