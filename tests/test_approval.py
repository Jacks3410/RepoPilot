import pytest

from repopilot.approval import (
    ApprovalGate,
    ApprovalRejected,
    ApprovalRequest,
    terminal_approval,
)


def test_approval_gate_allows_approved_request() -> None:
    gate = ApprovalGate(handler=lambda request: True)
    request = ApprovalRequest(
        action="write_file",
        target="demo.txt",
    )

    gate.require(request)


def test_approval_gate_rejects_request() -> None:
    gate = ApprovalGate(handler=lambda request: False)
    request = ApprovalRequest(
        action="write_file",
        target="demo.txt",
    )

    with pytest.raises(ApprovalRejected):
        gate.require(request)


def test_terminal_approval_accepts_y(monkeypatch) -> None:
    monkeypatch.setattr("builtins.input", lambda prompt: "y")
    request = ApprovalRequest(
        action="write_file",
        target="demo.txt",
        details="写入测试内容",
    )

    assert terminal_approval(request) is True


def test_terminal_approval_rejects_other_input(monkeypatch) -> None:
    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    request = ApprovalRequest(
        action="write_file",
        target="demo.txt",
    )

    assert terminal_approval(request) is False