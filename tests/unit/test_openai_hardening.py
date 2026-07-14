from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from reproagent.capture import capture
from reproagent.domain import CaptureCompleteness, EventType
from reproagent.integrations.openai import capture_openai


class FakeResource:
    def __init__(self, *, result: object = None, error: BaseException | None = None) -> None:
        self.result = result
        self.error = error
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def create(self, *args: object, **kwargs: object) -> object:
        self.calls.append((args, kwargs))
        if self.error is not None:
            raise self.error
        return self.result


class FakeClient:
    def __init__(self, resource: FakeResource) -> None:
        self.responses = resource
        self.chat = SimpleNamespace(completions=resource)


class UnsafeObject:
    def __init__(self, marker: str) -> None:
        self.marker = marker
        self.repr_calls = 0

    def __repr__(self) -> str:
        self.repr_calls += 1
        return self.marker


class UnconsumedStream:
    def __init__(self) -> None:
        self.iterations = 0

    def __iter__(self) -> UnconsumedStream:
        self.iterations += 1
        raise AssertionError("stream must not be eagerly consumed")

    def __next__(self) -> object:
        raise AssertionError("stream must not be eagerly consumed")


def test_unsupported_request_object_is_omitted_without_repr_or_provider_duplication() -> None:
    marker = "sk-proj-UNSAFEOBJECTSECRET123456789"
    unsafe = UnsafeObject(marker)
    resource = FakeResource(result={"output": []})

    with capture() as session:
        response = capture_openai(FakeClient(resource)).responses.create(
            model="gpt-test",
            input="hello",
            transport=unsafe,
        )

    assert response == {"output": []}
    assert len(resource.calls) == 1
    assert unsafe.repr_calls == 0
    assert session.case is not None
    assert session.case.completeness == CaptureCompleteness.DEGRADED
    assert all(event.event_type != EventType.MODEL_REQUEST for event in session.case.events)
    assert marker not in session.case.model_dump_json()


def test_unsupported_response_object_is_omitted_without_repr() -> None:
    marker = "Bearer UNSAFERESPONSESECRET123456789"
    unsafe = UnsafeObject(marker)
    resource = FakeResource(result=unsafe)

    with capture() as session:
        actual = capture_openai(FakeClient(resource)).responses.create(
            model="gpt-test",
            input="hello",
        )

    assert actual is unsafe
    assert unsafe.repr_calls == 0
    assert len(resource.calls) == 1
    assert session.case is not None
    assert session.case.completeness == CaptureCompleteness.DEGRADED
    assert [
        event.event_type for event in session.case.events if event.event_type == EventType.MODEL_RESPONSE
    ] == []
    assert marker not in session.case.model_dump_json()


def test_streaming_response_passes_through_unconsumed_and_marks_degraded() -> None:
    stream = UnconsumedStream()
    resource = FakeResource(result=stream)

    with capture() as session:
        actual = capture_openai(FakeClient(resource)).responses.create(
            model="gpt-test",
            input="hello",
            stream=True,
        )

    assert actual is stream
    assert stream.iterations == 0
    assert len(resource.calls) == 1
    assert session.case is not None
    assert session.case.completeness == CaptureCompleteness.DEGRADED
    assert any(event.event_type == EventType.MODEL_REQUEST for event in session.case.events)
    assert all(event.event_type != EventType.MODEL_RESPONSE for event in session.case.events)


def test_custom_headers_are_redacted_in_captured_request(tmp_path: Path) -> None:
    output = tmp_path / "openai-headers.agentcase"
    bearer = "Bearer abcdefghijklmnopqrstuvwxyz123456"
    api_key = "sk-proj-abcdefghijklmnopqrstuvwxyz123456"
    resource = FakeResource(result={"output": []})

    with capture(output=output):
        capture_openai(FakeClient(resource)).responses.create(
            model="gpt-test",
            input="hello",
            extra_headers={"Authorization": bearer, "apiKey": api_key},
        )

    raw = output.read_text(encoding="utf-8")
    assert bearer not in raw
    assert api_key not in raw
    assert len(resource.calls) == 1


def test_provider_exception_identity_survives_capture_and_secret_is_redacted(
    tmp_path: Path,
) -> None:
    output = tmp_path / "provider-error.agentcase"
    secret = "sk-proj-providerexceptionsecret123456789"
    error = RuntimeError(f"provider failed with {secret}")
    resource = FakeResource(error=error)

    with pytest.raises(RuntimeError) as raised:
        with capture(output=output):
            capture_openai(FakeClient(resource)).responses.create(
                model="gpt-test",
                input="hello",
            )

    assert raised.value is error
    assert len(resource.calls) == 1
    assert secret not in output.read_text(encoding="utf-8")


def test_unexpected_capture_failure_does_not_prevent_provider_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = {"output": []}
    resource = FakeResource(result=result)

    with capture() as session:
        monkeypatch.setattr(
            session,
            "model_request",
            lambda *args, **kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
        )
        actual = capture_openai(FakeClient(resource)).responses.create(
            model="gpt-test",
            input="hello",
        )

    assert actual is result
    assert len(resource.calls) == 1
