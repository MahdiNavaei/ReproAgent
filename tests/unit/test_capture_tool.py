from pathlib import Path

import pytest

from reproagent.agentcase import load_agentcase
from reproagent.capture import capture, capture_tool
from reproagent.domain import EventType, ExecutionOutcome


@capture_tool(name="add")
def add(left: int, right: int) -> int:
    return left + right


@capture_tool(name="explode")
def explode() -> None:
    raise ValueError("synthetic tool failure")


def test_tool_helper_without_active_session_preserves_normal_behavior() -> None:
    assert add(2, 3) == 5


def test_tool_helper_records_success_and_latency(tmp_path: Path) -> None:
    output = tmp_path / "tool.agentcase"
    with capture(output=output):
        assert add(2, 3) == 5

    case = load_agentcase(output)
    call = next(event for event in case.events if event.event_type == EventType.TOOL_CALL)
    result = next(event for event in case.events if event.event_type == EventType.TOOL_RESULT)
    assert result.parent_event_id == call.event_id
    assert call.payload["arguments"] == {"args": [2, 3], "kwargs": {}}
    assert result.payload["status"] == "success"
    assert result.payload["result"] == 5
    assert result.payload["latency_ms"] >= 0


def test_tool_helper_records_exception_and_preserves_caught_application_behavior(
    tmp_path: Path,
) -> None:
    output = tmp_path / "tool-failure.agentcase"
    with capture(output=output), pytest.raises(ValueError, match="synthetic tool failure"):
        explode()

    case = load_agentcase(output)
    assert case.outcome == ExecutionOutcome.SUCCESS
    assert [event.event_type for event in case.events].count(EventType.EXCEPTION) == 1
    failed_result = next(
        event for event in case.events if event.event_type == EventType.TOOL_RESULT
    )
    assert failed_result.payload["status"] == "failure"


def test_uncaught_tool_exception_is_not_duplicated_by_context_exit(tmp_path: Path) -> None:
    output = tmp_path / "uncaught-tool-failure.agentcase"
    with pytest.raises(ValueError), capture(output=output):
        explode()

    case = load_agentcase(output)
    assert case.outcome == ExecutionOutcome.FAILURE
    assert [event.event_type for event in case.events].count(EventType.EXCEPTION) == 1


def test_python_remains_authority_for_invalid_invocation_semantics() -> None:
    calls = 0

    @capture_tool()
    def target(left: int, right: int = 2) -> int:
        nonlocal calls
        calls += 1
        return left + right

    with capture():
        with pytest.raises(TypeError):
            target()  # type: ignore[call-arg]
        with pytest.raises(TypeError):
            target(1, left=2)  # type: ignore[misc]

    assert calls == 0


def test_positional_keyword_defaults_varargs_and_kwargs_execute_once() -> None:
    calls = 0

    @capture_tool()
    def target(first: int, second: int = 3, *rest: int, **named: int) -> int:
        nonlocal calls
        calls += 1
        return first + second + sum(rest) + sum(named.values())

    with capture() as session:
        assert target(1, 4, 5, 6, bonus=7) == 23

    assert calls == 1
    assert session.case is not None
    call = next(event for event in session.case.events if event.event_type == EventType.TOOL_CALL)
    assert call.payload["arguments"] == {
        "args": [1, 4, 5, 6],
        "kwargs": {"bonus": 7},
    }


def test_application_exception_identity_is_preserved() -> None:
    class ToolFailure(Exception):
        pass

    expected = ToolFailure("boom")

    @capture_tool()
    def target() -> None:
        raise expected

    with capture(), pytest.raises(ToolFailure) as raised:
        target()

    assert raised.value is expected


@pytest.mark.parametrize("expected", [KeyboardInterrupt(), SystemExit(17)])
def test_base_exception_identity_is_preserved(expected: BaseException) -> None:
    @capture_tool()
    def target() -> None:
        raise expected

    with capture(), pytest.raises(type(expected)) as raised:
        target()

    assert raised.value is expected


def test_unexpected_capture_failure_cannot_mask_function_exception() -> None:
    expected = RuntimeError("application failure")

    @capture_tool()
    def target() -> None:
        raise expected

    with capture() as session:
        def broken_tool_result(**_: object) -> None:
            raise KeyboardInterrupt("capture fault")

        session.tool_result = broken_tool_result  # type: ignore[method-assign]
        with pytest.raises(RuntimeError) as raised:
            target()

    assert raised.value is expected


def test_unexpected_capture_failure_cannot_change_success_return_value() -> None:
    @capture_tool()
    def target(value: object) -> object:
        return value

    marker = object()
    with capture() as session:
        def broken_tool_call(**_: object) -> None:
            raise SystemExit("capture fault")

        session.tool_call = broken_tool_call  # type: ignore[method-assign]
        assert target(marker) is marker


def test_async_tool_decoration_is_explicitly_unsupported() -> None:
    async def async_tool() -> None:
        return None

    with pytest.raises(TypeError, match="synchronous functions only"):
        capture_tool()(async_tool)
