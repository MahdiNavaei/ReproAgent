from __future__ import annotations

from uuid import uuid4

import pytest

from reproagent.domain import (
    AgentCase,
    CaptureCompleteness,
    Event,
    EventType,
    ExecutionOutcome,
)
from reproagent.replay import (
    ReplayContractError,
    mock_replay,
    validate_mock_replay_source,
)


def _complete_case() -> AgentCase:
    start_id = uuid4()
    request_id = uuid4()
    response_id = uuid4()
    call_id = uuid4()
    result_id = uuid4()
    return AgentCase(
        events=(
            Event(event_id=start_id, event_type=EventType.EXECUTION_START, sequence=0),
            Event(
                event_id=request_id,
                event_type=EventType.MODEL_REQUEST,
                sequence=1,
                parent_event_id=start_id,
                payload={
                    "provider": "offline",
                    "model": "fixture",
                    "input": {"prompt": "hello"},
                },
            ),
            Event(
                event_id=response_id,
                event_type=EventType.MODEL_RESPONSE,
                sequence=2,
                parent_event_id=request_id,
                payload={
                    "provider": "offline",
                    "model": "fixture",
                    "output": {"text": "hi"},
                },
            ),
            Event(
                event_id=call_id,
                event_type=EventType.TOOL_CALL,
                sequence=3,
                parent_event_id=response_id,
                payload={"name": "lookup", "call_id": "call-1", "arguments": {"id": 1}},
            ),
            Event(
                event_id=result_id,
                event_type=EventType.TOOL_RESULT,
                sequence=4,
                parent_event_id=call_id,
                payload={
                    "name": "lookup",
                    "call_id": "call-1",
                    "status": "success",
                    "result": {"ok": True},
                },
            ),
            Event(
                event_type=EventType.EXECUTION_END,
                sequence=5,
                parent_event_id=start_id,
                payload={"outcome": "success"},
            ),
        ),
        outcome=ExecutionOutcome.SUCCESS,
        completeness=CaptureCompleteness.COMPLETE,
    )


def _case_with_unanswered_model_request() -> AgentCase:
    start_id = uuid4()
    request_id = uuid4()
    return AgentCase(
        events=(
            Event(event_id=start_id, event_type=EventType.EXECUTION_START, sequence=0),
            Event(
                event_id=request_id,
                event_type=EventType.MODEL_REQUEST,
                sequence=1,
                parent_event_id=start_id,
                payload={
                    "provider": "offline",
                    "model": "fixture",
                    "input": {"prompt": "hello"},
                },
            ),
            Event(
                event_type=EventType.EXECUTION_END,
                sequence=2,
                parent_event_id=start_id,
                payload={"outcome": "failure"},
            ),
        ),
        outcome=ExecutionOutcome.FAILURE,
        completeness=CaptureCompleteness.COMPLETE,
    )


def test_mock_replay_copies_events_as_data_and_records_provenance() -> None:
    source = _complete_case()

    replayed = mock_replay(source)

    assert replayed.case_id != source.case_id
    assert replayed.execution_id != source.execution_id
    assert replayed.events == source.events
    assert replayed.replay is not None
    assert replayed.replay.source_case_id == source.case_id
    assert replayed.replay.mode.value == "mock"
    assert replayed.replay.determinism_guarantee.value == "deterministic"
    assert replayed.replay.live_side_effects_approved is False
    assert {item.target for item in replayed.replay.substitutions} == {
        "model.provider_calls",
        "tool.side_effects",
    }


def test_mock_replay_rejects_incomplete_capture_by_default() -> None:
    source = _complete_case().model_copy(update={"completeness": CaptureCompleteness.PARTIAL})

    with pytest.raises(ReplayContractError, match="complete capture"):
        mock_replay(source)

    replayed = mock_replay(source, allow_incomplete=True)
    assert replayed.completeness == CaptureCompleteness.PARTIAL


def test_mock_replay_rejects_missing_model_response() -> None:
    with pytest.raises(ReplayContractError, match=r"exactly one model.response"):
        validate_mock_replay_source(_case_with_unanswered_model_request())


def test_mock_replay_rejects_already_replayed_case() -> None:
    replayed = mock_replay(_complete_case())

    with pytest.raises(ReplayContractError, match="already replayed"):
        mock_replay(replayed)
