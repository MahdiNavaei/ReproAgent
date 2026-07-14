from pathlib import Path

import pytest

from reproagent.agentcase import load_agentcase
from reproagent.capture import CaptureLifecycleError, ToolResultStatus, capture
from reproagent.domain import EventType


def test_full_manual_event_flow_has_contiguous_sequences_and_valid_parents(tmp_path: Path) -> None:
    output = tmp_path / "full.agentcase"

    with capture(output=output, name="manual-agent") as session:
        message_id = session.message(role="user", content={"text": "Find order 123"})
        request_id = session.model_request(
            parent_event_id=message_id,
            provider="example-provider",
            model="example-model-a",
            input={"messages": [{"role": "user", "content": "Find order 123"}]},
            parameters={"temperature": 0},
        )
        response_id = session.model_response(
            parent_event_id=request_id,
            provider="example-provider",
            model="example-model-b",
            output={"message": {"role": "assistant", "content": "Looking it up"}},
            finish_reason="tool_call",
            usage={"input_tokens": 10, "output_tokens": 12},
            latency_ms=120.5,
        )
        definition_id = session.tool_definition(
            name="lookup_order",
            description="Look up a synthetic order",
            input_schema={"type": "object"},
            parent_event_id=response_id,
        )
        tool_call_id = session.tool_call(
            parent_event_id=definition_id,
            name="lookup_order",
            arguments={"order_id": "123"},
        )
        session.tool_result(
            parent_event_id=tool_call_id,
            name="lookup_order",
            status=ToolResultStatus.SUCCESS,
            result={"status": "shipped"},
            latency_ms=8.2,
        )
        session.retry(
            attempt=2,
            reason="synthetic retry evidence",
            delay_ms=10,
            target="model.request",
            parent_event_id=request_id,
        )

    case = load_agentcase(output)
    assert [event.sequence for event in case.events] == list(range(len(case.events)))
    assert len({event.event_id for event in case.events}) == len(case.events)
    index = {event.event_id: event.sequence for event in case.events}
    for event in case.events:
        if event.parent_event_id is not None:
            assert index[event.parent_event_id] < event.sequence

    event_types = [event.event_type for event in case.events]
    assert event_types[0] == EventType.EXECUTION_START
    assert EventType.MODEL_REQUEST in event_types
    assert EventType.MODEL_RESPONSE in event_types
    assert EventType.TOOL_CALL in event_types
    assert EventType.TOOL_RESULT in event_types
    assert EventType.RETRY in event_types
    assert event_types[-1] == EventType.EXECUTION_END


def test_model_response_requires_model_request_parent() -> None:
    with capture() as session:
        message_id = session.message(role="user", content="hello")
        with pytest.raises(
            CaptureLifecycleError, match=r"expected parent event type model\.request"
        ):
            session.model_response(
                parent_event_id=message_id,
                provider="example",
                model="model",
                output="response",
            )


def test_tool_result_requires_matching_tool_call_name_and_call_id() -> None:
    with capture() as session:
        call_id = session.tool_call(name="alpha", arguments={})
        with pytest.raises(CaptureLifecycleError, match="name must match"):
            session.tool_result(
                parent_event_id=call_id,
                name="beta",
                status="success",
                result={},
            )
        with pytest.raises(CaptureLifecycleError, match="call_id must match"):
            session.tool_result(
                parent_event_id=call_id,
                name="alpha",
                call_id="different",
                status="success",
                result={},
            )


def test_multi_model_run_keeps_event_level_models_as_source_of_truth(tmp_path: Path) -> None:
    output = tmp_path / "multi-model.agentcase"
    with capture(output=output) as session:
        first = session.model_request(provider="provider-a", model="model-a", input={})
        session.model_response(
            parent_event_id=first,
            provider="provider-a",
            model="model-a",
            output={},
        )
        second = session.model_request(provider="provider-b", model="model-b", input={})
        session.model_response(
            parent_event_id=second,
            provider="provider-b",
            model="model-b",
            output={},
        )

    case = load_agentcase(output)
    assert case.metadata.provider is None
    assert case.metadata.model is None
    request_models = [
        event.payload["model"]
        for event in case.events
        if event.event_type == EventType.MODEL_REQUEST
    ]
    assert request_models == ["model-a", "model-b"]
