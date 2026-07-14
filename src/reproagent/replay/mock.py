"""Deterministic, data-only mock replay for captured AgentCases.

Mock replay never imports recorded application code, executes tools, or calls a model/provider.
It validates that captured request/call events have exactly one captured terminal response/result,
then produces a new AgentCase whose events are copied from the source artifact and whose replay
metadata makes the substitution explicit.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from reproagent.domain import (
    AgentCase,
    CaptureCompleteness,
    DeterminismGuarantee,
    EventType,
    ReplayMetadata,
    ReplayMode,
    ReplaySubstitution,
)
from reproagent.replay.errors import ReplayContractError, ReplaySafetyError


def _terminal_children(case: AgentCase, parent_type: EventType, child_type: EventType) -> None:
    children_by_parent: dict[UUID, int] = {}
    for event in case.events:
        if event.event_type == child_type and event.parent_event_id is not None:
            current_count = children_by_parent.get(event.parent_event_id, 0)
            children_by_parent[event.parent_event_id] = current_count + 1

    for event in case.events:
        if event.event_type != parent_type:
            continue
        count = children_by_parent.get(event.event_id, 0)
        if count != 1:
            raise ReplayContractError(
                f"mock replay requires exactly one {child_type.value} child for "
                f"{parent_type.value} event {event.event_id}; found {count}"
            )


def validate_mock_replay_source(case: AgentCase, *, allow_incomplete: bool = False) -> None:
    """Validate that ``case`` can be replayed without executing external behavior."""

    if case.replay is not None:
        raise ReplayContractError("replaying an already replayed AgentCase is not supported")

    if not allow_incomplete and case.completeness != CaptureCompleteness.COMPLETE:
        raise ReplayContractError(
            "mock replay requires a complete capture unless allow_incomplete=True is explicit"
        )

    _terminal_children(case, EventType.MODEL_REQUEST, EventType.MODEL_RESPONSE)
    _terminal_children(case, EventType.TOOL_CALL, EventType.TOOL_RESULT)


def mock_replay(case: AgentCase, *, allow_incomplete: bool = False) -> AgentCase:
    """Create a deterministic data-only replay artifact from a captured AgentCase.

    No recorded code is imported and no model, provider, tool, network endpoint, subprocess,
    filesystem mutation, or other side effect is invoked. The source events are copied as data.
    """

    validate_mock_replay_source(case, allow_incomplete=allow_incomplete)

    replay = ReplayMetadata(
        mode=ReplayMode.MOCK,
        source_case_id=case.case_id,
        replayed_at=datetime.now(UTC),
        substitutions=(
            ReplaySubstitution(
                target="model.provider_calls",
                description=(
                    "captured model responses reused as immutable data; no provider call executed"
                ),
            ),
            ReplaySubstitution(
                target="tool.side_effects",
                description=("captured tool results reused as immutable data; no tool executed"),
            ),
        ),
        determinism_guarantee=DeterminismGuarantee.DETERMINISTIC,
        unresolved_external_dependencies=(),
        live_side_effects_approved=False,
    )

    replayed = case.model_copy(
        update={
            "case_id": uuid4(),
            "execution_id": uuid4(),
            "created_at": datetime.now(UTC),
            "replay": replay,
        },
        deep=True,
    )

    if replayed.replay is None or replayed.replay.live_side_effects_approved:
        raise ReplaySafetyError("mock replay must never approve live side effects")
    return replayed
