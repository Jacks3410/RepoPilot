from types import SimpleNamespace
from typing import Any

import pytest

from repopilot.llm import RetryPolicy, call_llm


class ProviderError(RuntimeError):
    def __init__(
        self,
        message: str,
        status_code: int,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response = SimpleNamespace(headers=headers or {})


class FakeCompletions:
    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    def create(self, **kwargs: Any) -> Any:
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def make_client(outcomes: list[Any]) -> tuple[Any, FakeCompletions]:
    completions = FakeCompletions(outcomes)
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
    )
    return client, completions


def make_response() -> Any:
    message = SimpleNamespace(
        content="完成",
        reasoning_content=None,
        tool_calls=None,
    )
    usage = SimpleNamespace(
        total_tokens=12,
        prompt_tokens=8,
        completion_tokens=4,
    )
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message)],
        usage=usage,
    )


def test_call_llm_honors_retry_after_and_records_metrics() -> None:
    client, completions = make_client([
        ProviderError("rate limited", 429, {"retry-after": "3"}),
        make_response(),
    ])
    waits: list[float] = []

    result = call_llm(
        messages=[{"role": "user", "content": "test"}],
        client=client,
        retry_policy=RetryPolicy(
            max_retries=2,
            base_delay_seconds=1,
            max_delay_seconds=10,
        ),
        sleep_fn=waits.append,
    )

    assert completions.calls == 2
    assert waits == [3.0]
    assert result["retry"] == {"count": 1, "wait_ms": 3000}
    assert result["usage"]["total_tokens"] == 12


def test_call_llm_reads_kimi_retry_delay_from_error_message() -> None:
    client, _ = make_client([
        ProviderError("please try again after 2 seconds", 429),
        make_response(),
    ])
    waits: list[float] = []

    call_llm(
        messages=[],
        client=client,
        retry_policy=RetryPolicy(
            max_retries=1,
            base_delay_seconds=1,
            max_delay_seconds=10,
        ),
        sleep_fn=waits.append,
    )

    assert waits == [2.0]


def test_call_llm_does_not_retry_authentication_failure() -> None:
    client, completions = make_client([
        ProviderError("incorrect api key", 401),
    ])
    waits: list[float] = []

    with pytest.raises(ProviderError, match="incorrect api key"):
        call_llm(
            messages=[],
            client=client,
            retry_policy=RetryPolicy(max_retries=5),
            sleep_fn=waits.append,
        )

    assert completions.calls == 1
    assert waits == []


def test_call_llm_stops_after_retry_budget_is_exhausted() -> None:
    client, completions = make_client([
        ProviderError("unavailable", 503),
        ProviderError("unavailable", 503),
        ProviderError("still unavailable", 503),
    ])
    waits: list[float] = []

    with pytest.raises(ProviderError, match="still unavailable"):
        call_llm(
            messages=[],
            client=client,
            retry_policy=RetryPolicy(
                max_retries=2,
                base_delay_seconds=1,
                max_delay_seconds=10,
            ),
            sleep_fn=waits.append,
        )

    assert completions.calls == 3
    assert waits == [1.0, 2.0]
