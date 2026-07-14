from __future__ import annotations

import pytest

from reproagent.capture import capture
from reproagent.domain import EventType, ReplayMode
from reproagent.replay import MockReplayContext, ReplayContractError, run_mock_replay


def _source_case() -> object:
    with capture(name="source") as session:
        request_id = session.model_request(
            provider="example",
            model="model-v1",
            input="question",
            parameters={"temperature": 0},
        )
        session.model_response(
            parent_event_id=request_id,
            provider="example",
            model="model-v1",
            output={"tool": "lookup"},
            finish_reason="tool_call",
        )
        call_id = session.tool_call(name="lookup", arguments={"id": 7}, call_id="call-7")
        session.tool_result(
            parent_event_id=call_id,
            name="lookup",
            status="success",
            result={"value": 11},
            call_id="call-7",
        )

    assert session.case is not None
    return session.case


def test_explicit_runner_reexecutes_local_code_with_recorded_substitutions() -> None:
    source = _source_case()
    calls = 0

    def agent(replay: MockReplayContext) -> int:
        nonlocal calls
        calls += 1
        plan = replay.model_response(provider="example", model="model-v1")
        assert plan == {"tool": "lookup"}
        outcome = replay.tool_result(name="lookup")
        assert outcome.status == "success"
        assert isinstance(outcome.result, dict)
        return int(outcome.result["value"])

    run = run_mock_replay(source, agent)  # type: ignore[arg-type]

    assert calls == 1
    assert run.value == 11
    assert run.case.replay is not None
    assert run.case.replay.mode == ReplayMode.MOCK
    assert run.case.replay.source_case_id == source.case_id  # type: ignore[union-attr]
    assert not run.case.replay.live_side_effects_approved
    assert sum(event.event_type == EventType.MODEL_RESPONSE for event in run.case.events) == 1
    assert sum(event.event_type == EventType.TOOL_RESULT for event in run.case.events) == 1


def test_runner_fails_closed_on_wrong_interaction_order() -> None:
    source = _source_case()

    def agent(replay: MockReplayContext) -> None:
        replay.tool_result(name="lookup")

    with pytest.raises(ReplayContractError, match="next recorded interaction is model.request"):
        run_mock_replay(source, agent)  # type: ignore[arg-type]


def test_runner_fails_closed_when_recorded_interactions_are_left_unconsumed() -> None:
    source = _source_case()

    def agent(replay: MockReplayContext) -> None:
        replay.model_response()

    with pytest.raises(ReplayContractError, match="unconsumed interaction"):
        run_mock_replay(source, agent)  # type: ignore[arg-type]


def test_runner_requires_explicit_callable() -> None:
    source = _source_case()

    with pytest.raises(ReplayContractError, match="explicitly supplied callable"):
        run_mock_replay(source, "module:function")  # type: ignore[arg-type]
