from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any


_SAFE_ARGUMENTS: dict[str, set[str]] = {
    "list_files": {"path"},
    "read_file": {"path"},
    "write_file": {"path"},
    "run_tests": set(),
}
_APPROVAL_TOOLS = {"write_file", "run_tests"}
_SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(
        r"(?i)(OPENAI_API_KEY\s*[=:]\s*[\"']?)([^\s\"']+)"
    ),
)


def redact_sensitive_text(value: str) -> str:
    """遮盖常见 API Key，避免审计报告泄露凭证。"""
    redacted = value
    redacted = _SECRET_PATTERNS[0].sub("[REDACTED]", redacted)
    redacted = _SECRET_PATTERNS[1].sub(r"\1[REDACTED]", redacted)
    return redacted


def redact_sensitive_data(value: Any) -> Any:
    """递归遮盖字符串容器中的常见凭证。"""
    if isinstance(value, str):
        return redact_sensitive_text(value)
    if isinstance(value, list):
        return [redact_sensitive_data(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): redact_sensitive_data(item)
            for key, item in value.items()
        }
    return value


def _safe_arguments(tool_name: str, raw_arguments: str) -> dict[str, Any]:
    allowed = _SAFE_ARGUMENTS.get(tool_name, set())

    try:
        arguments = json.loads(raw_arguments)
    except (TypeError, json.JSONDecodeError):
        return {}

    if not isinstance(arguments, dict):
        return {}

    return {
        key: redact_sensitive_text(str(arguments[key]))
        for key in allowed
        if key in arguments
    }


def build_tool_audit_record(
    tool_call: dict[str, Any],
    result_content: str,
    duration_ms: float,
) -> dict[str, Any]:
    """生成不包含文件正文和模型输入的工具审计记录。"""
    function = tool_call.get("function", {})
    tool_name = str(function.get("name", ""))
    raw_arguments = function.get("arguments", "{}")
    success = not result_content.startswith("工具执行失败：")
    requires_approval = tool_name in _APPROVAL_TOOLS

    approval_status: str | None = None
    if requires_approval:
        if "用户拒绝操作" in result_content:
            approval_status = "rejected"
        elif success:
            approval_status = "approved"
        else:
            approval_status = "unknown"

    error: str | None = None
    if not success:
        error = redact_sensitive_text(result_content)[:500]

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tool_call_id": str(tool_call.get("id", "")),
        "tool_name": tool_name,
        "arguments": _safe_arguments(tool_name, str(raw_arguments)),
        "success": success,
        "requires_approval": requires_approval,
        "approval_status": approval_status,
        "duration_ms": round(max(duration_ms, 0.0), 3),
        "error": error,
    }
