from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from reproagent.domain import (
    AgentCase,
    AgentCaseMetadata,
    CaptureCompleteness,
    Event,
    EventType,
    ExecutionOutcome,
    RedactionMetadata,
    RedactionRecord,
    RedactionStatus,
)

NOW = datetime(2026, 7, 14, tzinfo=UTC)


def _event(index: int, *, parent: UUID | None = None) -> Event:
    return Event(
        event_id=UUID(f"00000000-0000-4000-8000-{index + 1:012d}"),
        event_type=EventType.CUSTOM,
        sequence=index,
        timestamp=NOW,
        parent_event_id=parent,
        payload={"index": index},
    )


def _case(events: tuple[Event, ...]) -> AgentCase:
    return AgentCase(
        case_id=UUID("11111111-1111-4111-8111-111111111111"),
        execution_id=UUID("22222222-2222-4222-8222-222222222222"),
        created_at=NOW,
        metadata=AgentCaseMetadata(),
        events=events,
        outcome=ExecutionOutcome.UNKNOWN,
        completeness=CaptureCompleteness.COMPLETE,
    )


def test_minimal_agentcase_can_be_constructed() -> None:
    case = _case(())
    assert case.format_name == "agentcase"
    assert case.format_version == "0.1"


def test_duplicate_event_ids_are_rejected() -> None:
    first = _event(0)
    duplicate = first.model_copy(update={"sequence": 1})
    with pytest.raises(ValidationError, match="event IDs must be unique"):
        _case((first, duplicate))


def test_sequences_must_be_contiguous_and_ordered() -> None:
    first = _event(0)
    third = _event(2)
    with pytest.raises(ValidationError, match="sequence numbers must be contiguous"):
        _case((first, third))


def test_parent_must_reference_existing_earlier_event() -> None:
    missing = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    child = _event(0, parent=missing)
    with pytest.raises(ValidationError, match="does not reference an event"):
        _case((child,))


def test_parent_cannot_point_forward() -> None:
    child = _event(0, parent=UUID("00000000-0000-4000-8000-000000000002"))
    parent = _event(1)
    with pytest.raises(ValidationError, match="parent events must appear before"):
        _case((child, parent))


def test_naive_timestamps_are_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        Event(event_type=EventType.CUSTOM, sequence=0, timestamp=datetime(2026, 7, 14))


def test_redacted_status_requires_a_record() -> None:
    with pytest.raises(ValidationError, match="requires at least one"):
        RedactionMetadata(status=RedactionStatus.REDACTED)


def test_redaction_records_must_be_irreversible() -> None:
    with pytest.raises(ValidationError, match="must be irreversible"):
        RedactionRecord(
            field_path="/payload/token",
            rule_id="test",
            replacement_marker="[REDACTED]",
            irreversible=False,
        )
