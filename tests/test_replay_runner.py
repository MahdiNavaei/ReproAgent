from __future__ import annotations

from uuid import uuid4

import pytest

from reproagent.domain import AgentCase, CaptureCompleteness, Event, EventType, ExecutionOutcome
from reproagent.replay import MockReplayContext, ReplayContractError, run_mock_replay


def _case() -> AgentCase:
    start_id = uuid4()
    request_id = uuid4()
    response_id = uuid4()
    call_id = uuid4()
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
                    "output": {"tool": "lookup"},
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
                event_type=EventType.TOOL_RESULT,
                sequence=4,
                parent_event_id=call_id,
                payload={
                    "name": "lookup",
                    "call_id": "call-1",
                    "status": "success",
                    "result": {"value": 42},
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


def test_run_mock_replay_reexecutes_explicit_callable_with_recorded_interactions() -> None:
    calls = 0

    def local_agent(replay: MockReplayContext) -> int:
        nonlocal calls
        calls += 1
        model_output = replay.model_response(
            provider="offline",
            model="fixture",
            input={"prompt": "hello"},
        )
        assert model_output == {"tool": "lookup"}
        tool_output = replay.tool_result(name="lookup", arguments={"id": 1})
        assert tool_output.status == "success"
        assert tool_output.error is None
        assert tool_output.result == {"value": 42}
        return 42

    result = run_mock_replay(_case(), local_agent)

    assert result.value == 42
    assert result.consumed_model_interactions == 1
    assert result.consumed_tool_interactions == 1
    assert calls == 1


def test_run_mock_replay_fails_closed_on_request_mismatch() -> None:
    def changed_agent(replay: MockReplayContext) -> None:
        replay.model_response(
            provider="offline",
            model="fixture",
            input={"prompt": "changed"},
        )

    with pytest.raises(ReplayContractError, match="does not match"):
        run_mock_replay(_case(), changed_agent)


def test_run_mock_replay_enforces_global_model_tool_order() -> None:
    def out_of_order_agent(replay: MockReplayContext) -> None:
        replay.tool_result(name="lookup", arguments={"id": 1})

    with pytest.raises(
        ReplayContractError,
        match="next recorded interaction is model, requested tool",
    ):
        run_mock_replay(_case(), out_of_order_agent)


def test_run_mock_replay_fails_when_recorded_interactions_are_unconsumed() -> None:
    with pytest.raises(ReplayContractError, match="unconsumed recorded interactions"):
        run_mock_replay(_case(), lambda replay: "done")


def test_run_mock_replay_has_no_live_fallback_after_recording_is_exhausted() -> None:
    def too_many_calls(replay: MockReplayContext) -> None:
        replay.model_response(
            provider="offline",
            model="fixture",
            input={"prompt": "hello"},
        )
        replay.tool_result(name="lookup", arguments={"id": 1})
        replay.model_response(
            provider="offline",
            model="fixture",
            input={"prompt": "hello"},
        )

    with pytest.raises(ReplayContractError, match="no recorded interaction remaining"):
        run_mock_replay(_case(), too_many_calls)


def test_run_mock_replay_never_executes_recorded_entrypoint_metadata(tmp_path: object) -> None:
    marker = "RECORDED_ENTRYPOINT_MUST_NOT_EXECUTE"
    source = _case().model_copy(
        update={
            "metadata": _case().metadata.model_copy(
                update={"user_metadata": {"entrypoint": f"raise RuntimeError('{marker}')"}}
            )
        }
    )

    def explicit_agent(replay: MockReplayContext) -> int:
        replay.model_response(
            provider="offline",
            model="fixture",
            input={"prompt": "hello"},
        )
        replay.tool_result(name="lookup", arguments={"id": 1})
        return 1

    assert run_mock_replay(source, explicit_agent).value == 1
