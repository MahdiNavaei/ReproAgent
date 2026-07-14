from __future__ import annotations

import pytest

from reproagent.capture import capture, capture_tool
from reproagent.domain import EventType


class ToolError(RuntimeError):
    pass


def test_capture_tool_preserves_argument_shapes_and_defaults() -> None:
    calls = 0

    @capture_tool(name="shapes")
    def shaped(
        first: int,
        second: int = 2,
        *items: int,
        flag: bool = False,
        **extras: int,
    ) -> tuple[object, ...]:
        nonlocal calls
        calls += 1
        return first, second, items, flag, extras

    with capture() as session:
        actual = shaped(1, 3, 4, 5, flag=True, other=6)

    assert actual == (1, 3, (4, 5), True, {"other": 6})
    assert calls == 1
    assert session.case is not None
    call = next(event for event in session.case.events if event.event_type == EventType.TOOL_CALL)
    assert call.payload["arguments"] == {
        "first": 1,
        "second": 3,
        "items": [4, 5],
        "flag": True,
        "extras": {"other": 6},
    }


def test_capture_tool_applies_omitted_defaults_to_observed_arguments() -> None:
    @capture_tool(name="defaults")
    def defaulted(value: int, scale: int = 7) -> int:
        return value * scale

    with capture() as session:
        assert defaulted(value=3) == 21

    assert session.case is not None
    call = next(event for event in session.case.events if event.event_type == EventType.TOOL_CALL)
    assert call.payload["arguments"] == {"value": 3, "scale": 7}


def test_missing_argument_typeerror_comes_from_wrapped_function() -> None:
    body_calls = 0

    def plain(required: int) -> int:
        nonlocal body_calls
        body_calls += 1
        return required

    decorated = capture_tool()(plain)
    with pytest.raises(TypeError) as expected:
        plain()  # type: ignore[call-arg]
    with capture(), pytest.raises(TypeError) as actual:
        decorated()  # type: ignore[call-arg]

    assert type(actual.value) is type(expected.value)
    assert str(actual.value) == str(expected.value)
    assert body_calls == 0


def test_duplicate_argument_typeerror_comes_from_wrapped_function() -> None:
    body_calls = 0

    def plain(value: int) -> int:
        nonlocal body_calls
        body_calls += 1
        return value

    decorated = capture_tool()(plain)
    with pytest.raises(TypeError) as expected:
        plain(1, value=2)
    with capture(), pytest.raises(TypeError) as actual:
        decorated(1, value=2)

    assert type(actual.value) is type(expected.value)
    assert str(actual.value) == str(expected.value)
    assert body_calls == 0


def test_function_typeerror_identity_is_preserved() -> None:
    error = TypeError("function body type error")

    @capture_tool()
    def fail() -> None:
        raise error

    with capture(), pytest.raises(TypeError) as raised:
        fail()

    assert raised.value is error


def test_custom_exception_identity_survives_unexpected_capture_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = ToolError("tool failed")

    @capture_tool()
    def fail() -> None:
        raise error

    with pytest.raises(ToolError) as raised, capture() as session:
        monkeypatch.setattr(
            session,
            "tool_result",
            lambda *args, **kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
        )
        monkeypatch.setattr(
            session,
            "exception",
            lambda *args, **kwargs: (_ for _ in ()).throw(SystemExit()),
        )
        fail()

    assert raised.value is error


@pytest.mark.parametrize("error", [KeyboardInterrupt("stop"), SystemExit("exit")])
def test_baseexception_identity_is_preserved(error: BaseException) -> None:
    @capture_tool()
    def fail() -> None:
        raise error

    with capture(), pytest.raises(type(error)) as raised:
        fail()

    assert raised.value is error


def test_capture_side_call_failure_does_not_skip_or_repeat_function(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    @capture_tool()
    def once(value: int) -> int:
        nonlocal calls
        calls += 1
        return value + 1

    with capture() as session:
        monkeypatch.setattr(
            session,
            "tool_call",
            lambda *args, **kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
        )
        assert once(4) == 5

    assert calls == 1


def test_capture_side_result_failure_does_not_replace_return_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = object()
    calls = 0

    @capture_tool()
    def once() -> object:
        nonlocal calls
        calls += 1
        return result

    with capture() as session:
        monkeypatch.setattr(
            session,
            "tool_result",
            lambda *args, **kwargs: (_ for _ in ()).throw(SystemExit()),
        )
        actual = once()

    assert actual is result
    assert calls == 1
