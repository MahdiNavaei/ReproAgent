from pathlib import Path

from reproagent.agentcase import dumps_agentcase, load_agentcase, loads_agentcase
from reproagent.capture import capture
from reproagent.domain import EventType


def test_capture_generated_case_uses_same_agentcase_v0_loader_and_round_trips(
    tmp_path: Path,
) -> None:
    output = tmp_path / "generated.agentcase"
    with capture(output=output) as session:
        request = session.model_request(
            provider="synthetic-provider",
            model="synthetic-model",
            input={"prompt": "hello"},
        )
        session.model_response(
            parent_event_id=request,
            provider="synthetic-provider",
            model="synthetic-model",
            output={"text": "world"},
        )

    case = load_agentcase(output)
    serialized = dumps_agentcase(case)
    assert loads_agentcase(serialized) == case
    assert [event.sequence for event in case.events] == list(range(len(case.events)))
    assert case.events[0].event_type == EventType.EXECUTION_START
    assert case.events[-1].event_type == EventType.EXECUTION_END
