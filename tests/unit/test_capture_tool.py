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


def test_async_tool_decoration_is_explicitly_unsupported() -> None:
    async def async_tool() -> None:
        return None

    with pytest.raises(TypeError, match="synchronous functions only"):
        capture_tool()(async_tool)
