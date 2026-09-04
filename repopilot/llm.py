from __future__ import annotations

import os
from typing import Any

from openai import OpenAI


def call_llm(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    system_prompt: str | None = None,
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

    client = OpenAI(
        api_key=os.environ.get("OPENAI_API_KEY"),
        base_url=os.environ.get("OPENAI_BASE_URL"),
    )
    response = client.chat.completions.create(**request)
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
    }

    reasoning_content = getattr(message, "reasoning_content", None)
    if reasoning_content:
        result["reasoning_content"] = reasoning_content
    if message.tool_calls:
        result["tool_calls"] = [
            tool_call.model_dump() for tool_call in message.tool_calls
        ]
    return result
