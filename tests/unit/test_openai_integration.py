from types import SimpleNamespace

import pytest

from reproagent.capture import capture
from reproagent.domain import EventType
from reproagent.integrations.openai import capture_openai


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def model_dump(self, *, mode: str) -> dict[str, object]:
        assert mode == "json"
        return self.payload


class FakeResource:
    def __init__(self, result: object = None, error: BaseException | None = None) -> None:
        self.result = result
        self.error = error
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.result


class FakeClient:
    def __init__(self, *, responses: FakeResource, completions: FakeResource) -> None:
        self.responses = responses
        self.chat = SimpleNamespace(completions=completions)
        self.marker = "original-client"


def test_responses_create_is_captured_without_changing_return_value() -> None:
    response = FakeResponse({"id": "resp_1", "output": [{"type": "message"}]})
    resource = FakeResource(result=response)
    client = FakeClient(responses=resource, completions=FakeResource())

    with capture() as session:
        wrapped = capture_openai(client)
        actual = wrapped.responses.create(model="gpt-test", input="hello", temperature=0)

    assert actual is response
    assert resource.calls == [{"model": "gpt-test", "input": "hello", "temperature": 0}]
    assert session.case is not None
    model_events = [
        event
        for event in session.case.events
        if event.event_type in {EventType.MODEL_REQUEST, EventType.MODEL_RESPONSE}
    ]
    assert [event.event_type for event in model_events] == [
        EventType.MODEL_REQUEST,
        EventType.MODEL_RESPONSE,
    ]
    assert model_events[0].payload["provider"] == "openai"
    assert model_events[0].payload["input"] == "hello"
    assert model_events[1].payload["output"] == response.payload


def test_chat_completions_extracts_messages_finish_reason_and_usage() -> None:
    response = FakeResponse(
        {
            "choices": [{"finish_reason": "stop", "message": {"content": "hi"}}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 1},
        }
    )
    client = FakeClient(responses=FakeResource(), completions=FakeResource(result=response))

    with capture() as session:
        capture_openai(client).chat.completions.create(
            model="gpt-test",
            messages=[{"role": "user", "content": "hello"}],
        )

    assert session.case is not None
    request = next(
        event for event in session.case.events if event.event_type == EventType.MODEL_REQUEST
    )
    response_event = next(
        event for event in session.case.events if event.event_type == EventType.MODEL_RESPONSE
    )
    assert request.payload["input"] == [{"role": "user", "content": "hello"}]
    assert response_event.payload["finish_reason"] == "stop"
    assert response_event.payload["usage"] == {"prompt_tokens": 2, "completion_tokens": 1}


def test_provider_exception_is_re_raised_unchanged_and_captured() -> None:
    provider_error = RuntimeError("synthetic provider failure")
    client = FakeClient(
        responses=FakeResource(error=provider_error),
        completions=FakeResource(),
    )

    with (
        pytest.raises(RuntimeError, match="synthetic provider failure") as raised,
        capture() as session,
    ):
        capture_openai(client).responses.create(model="gpt-test", input="hello")

    assert raised.value is provider_error
    assert session.case is not None
    assert any(event.event_type == EventType.EXCEPTION for event in session.case.events)


def test_wrapper_is_opt_in_and_forwards_unselected_client_attributes() -> None:
    resource = FakeResource(result=FakeResponse({"output": []}))
    client = FakeClient(responses=resource, completions=FakeResource())
    wrapped = capture_openai(client)

    assert wrapped.marker == "original-client"
    client.responses.create(model="gpt-test", input="outside")

    with capture() as session:
        assert session.case is None

    assert resource.calls == [{"model": "gpt-test", "input": "outside"}]
