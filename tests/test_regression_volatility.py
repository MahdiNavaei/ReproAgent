from pathlib import Path

from reproagent.agentcase import load_agentcase
from reproagent.regression import compare_agentcases

FIXTURE = Path(__file__).parent / "fixtures" / "valid_minimal.agentcase"


def test_payload_timestamp_is_not_hidden_by_agentcase_volatility_normalization() -> None:
    baseline = load_agentcase(FIXTURE)
    event = baseline.events[4]
    changed = event.model_copy(update={"payload": {**event.payload, "timestamp": "changed"}})
    observed = baseline.model_copy(
        update={"events": (*baseline.events[:4], changed, *baseline.events[5:])}
    )

    result = compare_agentcases(baseline, observed)

    assert not result.passed
    assert [difference.path for difference in result.diff.differences] == [
        "$.events[4].payload.timestamp"
    ]


def test_payload_event_id_and_replay_keys_remain_business_data() -> None:
    baseline = load_agentcase(FIXTURE)
    event = baseline.events[4]
    changed = event.model_copy(
        update={
            "payload": {
                **event.payload,
                "event_id": "business-id",
                "replay": {"decision": "changed"},
            }
        }
    )
    observed = baseline.model_copy(
        update={"events": (*baseline.events[:4], changed, *baseline.events[5:])}
    )

    result = compare_agentcases(baseline, observed)

    assert not result.passed
    assert {difference.path for difference in result.diff.differences} == {
        "$.events[4].payload.event_id",
        "$.events[4].payload.replay",
    }
