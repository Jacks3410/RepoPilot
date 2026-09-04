from __future__ import annotations

import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

from openai import OpenAI


@dataclass(frozen=True)
class RetryPolicy:
    """Retry policy for transient model-provider failures."""

    max_retries: int = 5
    base_delay_seconds: float = 2.0
    max_delay_seconds: float = 30.0

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError("max_retries must not be negative")
        if self.base_delay_seconds < 0:
            raise ValueError("base_delay_seconds must not be negative")
        if self.max_delay_seconds < self.base_delay_seconds:
            raise ValueError(
                "max_delay_seconds must be at least base_delay_seconds"
            )

    @classmethod
    def from_env(cls) -> "RetryPolicy":
        return cls(
            max_retries=_env_int("OPENAI_MAX_RETRIES", 5),
            base_delay_seconds=_env_float(
                "OPENAI_RETRY_BASE_SECONDS",
                2.0,
            ),
            max_delay_seconds=_env_float(
                "OPENAI_RETRY_MAX_SECONDS",
                30.0,
            ),
        )


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _is_retryable(error: Exception) -> bool:
    status_code = getattr(error, "status_code", None)
    if isinstance(status_code, int):
        return status_code in {408, 409, 429} or status_code >= 500

    error_name = type(error).__name__.lower()
    return "connection" in error_name or "timeout" in error_name


def _retry_after_seconds(error: Exception) -> float | None:
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", {}) or {}
    value = headers.get("retry-after") or headers.get("Retry-After")
    if value is not None:
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            try:
                retry_at = parsedate_to_datetime(str(value))
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                return max(
                    0.0,
                    (retry_at - datetime.now(timezone.utc)).total_seconds(),
                )
            except (TypeError, ValueError, OverflowError):
                pass

    match = re.search(
        r"(?:try again|retry).*?after\s+(\d+(?:\.\d+)?)\s*seconds?",
        str(error),
        flags=re.IGNORECASE,
    )
    return float(match.group(1)) if match else None


def _retry_delay(
    error: Exception,
    retry_index: int,
    policy: RetryPolicy,
) -> float:
    exponential = policy.base_delay_seconds * (2 ** retry_index)
    requested = _retry_after_seconds(error) or 0.0
    return min(policy.max_delay_seconds, max(exponential, requested))


def call_llm(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    system_prompt: str | None = None,
    *,
    client: Any | None = None,
    retry_policy: RetryPolicy | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Call an OpenAI-compatible chat completion endpoint."""
    request_messages = list(messages)
    if system_prompt:
        request_messages.insert(0, {
            "role": "system",
            "content": system_prompt,
        })

    request: dict[str, Any] = {
        "model": os.environ.get("OPENAI_MODEL_ID", "kimi-k2.6"),
        "messages": request_messages,
    }
    if tools:
        request["tools"] = tools
        request["tool_choice"] = "auto"

    selected_policy = retry_policy or RetryPolicy.from_env()
    selected_client = client or OpenAI(
        api_key=os.environ.get("OPENAI_API_KEY"),
        base_url=os.environ.get("OPENAI_BASE_URL"),
        max_retries=0,
    )

    retry_count = 0
    retry_wait_seconds = 0.0
    while True:
        try:
            response = selected_client.chat.completions.create(**request)
            break
        except Exception as error:
            if (
                not _is_retryable(error)
                or retry_count >= selected_policy.max_retries
            ):
                raise

            delay = _retry_delay(error, retry_count, selected_policy)
            retry_count += 1
            retry_wait_seconds += delay
            status_code = getattr(error, "status_code", "network")
            print(
                "[LLM Retry] "
                f"status={status_code}, attempt={retry_count}/"
                f"{selected_policy.max_retries}, wait={delay:.1f}s"
            )
            sleep_fn(delay)
    message = response.choices[0].message
    usage = response.usage

    result: dict[str, Any] = {
        "role": "assistant",
        "content": message.content or "",
        "usage": {
            "total_tokens": usage.total_tokens if usage else 0,
            "prompt_tokens": usage.prompt_tokens if usage else 0,
            "completion_tokens": usage.completion_tokens if usage else 0,
        },
        "retry": {
            "count": retry_count,
            "wait_ms": round(retry_wait_seconds * 1000),
        },
    }

    reasoning_content = getattr(message, "reasoning_content", None)
    if reasoning_content:
        result["reasoning_content"] = reasoning_content
    if message.tool_calls:
        result["tool_calls"] = [
            tool_call.model_dump() for tool_call in message.tool_calls
        ]
    return result
