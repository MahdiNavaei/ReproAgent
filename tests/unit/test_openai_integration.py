from types import SimpleNamespace

import pytest

from reproagent.agentcase import dump_agentcase_bytes
from reproagent.capture import capture
from reproagent.domain import CaptureCompleteness, EventType
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


def test_streaming_passes_through_without_eager_consumption_or_fake_response() -> None:
    class StreamMarker:
        def __iter__(self) -> object:
            raise AssertionError("capture must not consume stream")

    stream = StreamMarker()
    resource = FakeResource(result=stream)
    client = FakeClient(responses=resource, completions=FakeResource())

    with capture() as session:
        actual = capture_openai(client).responses.create(
            model="gpt-test", input="hello", stream=True
        )

    assert actual is stream
    assert len(resource.calls) == 1
    assert session.case is not None
    assert session.case.completeness == CaptureCompleteness.UNSUPPORTED
    assert not any(
        event.event_type == EventType.MODEL_RESPONSE for event in session.case.events
    )


def test_unsupported_values_are_omitted_without_repr_or_provider_call_duplication() -> None:
    secret = "secret-from-dangerous-repr"

    class DangerousObject:
        def __repr__(self) -> str:
            return secret

    response = FakeResponse({"output": []})
    resource = FakeResource(result=response)
    client = FakeClient(responses=resource, completions=FakeResource())

    with capture() as session:
        actual = capture_openai(client).responses.create(
            model="gpt-test", input="hello", transport=DangerousObject()
        )

    assert actual is response
    assert len(resource.calls) == 1
    assert session.case is not None
    assert session.case.completeness == CaptureCompleteness.DEGRADED
    assert secret.encode() not in dump_agentcase_bytes(session.case)


def test_sensitive_headers_and_provider_exception_secret_do_not_leak() -> None:
    api_key = "sk-proj-abcdefghijklmnop123456"
    bearer = "Bearer abcdefghijklmnopqrstuvwxyz"
    provider_error = RuntimeError(f"provider failed with {api_key}")
    resource = FakeResource(error=provider_error)
    client = FakeClient(responses=resource, completions=FakeResource())

    with capture() as session:
        with pytest.raises(RuntimeError) as raised:
            capture_openai(client).responses.create(
                model="gpt-test",
                input="hello",
                extra_headers={"Authorization": bearer, "X-Api-Key": api_key},
            )
        assert raised.value is provider_error

    assert len(resource.calls) == 1
    assert session.case is not None
    encoded = dump_agentcase_bytes(session.case)
    assert api_key.encode() not in encoded
    assert bearer.encode() not in encoded


def test_wrapper_is_opt_in_and_forwards_unselected_client_attributes() -> None:
    resource = FakeResource(result=FakeResponse({"output": []}))
    client = FakeClient(responses=resource, completions=FakeResource())
    wrapped = capture_openai(client)

    assert wrapped.marker == "original-client"
    client.responses.create(model="gpt-test", input="outside")

    with capture() as session:
        assert session.case is None

    assert resource.calls == [{"model": "gpt-test", "input": "outside"}]
