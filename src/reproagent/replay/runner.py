"""Explicit deterministic replay runner for caller-supplied local Python code."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, Literal, TypeVar

from pydantic import JsonValue

from reproagent.domain import AgentCase, Event, EventType
from reproagent.replay.errors import ReplayContractError
from reproagent.replay.mock import validate_mock_replay_source

T = TypeVar("T")
InteractionKind = Literal["model", "tool"]


@dataclass(frozen=True, slots=True)
class RecordedToolResult:
    """Data-only recorded terminal result returned to explicitly replayed user code."""

    status: str
    result: JsonValue | None
    error: JsonValue | None


@dataclass(frozen=True, slots=True)
class ReplayRunResult(Generic[T]):
    """Successful explicit local replay result and interaction-consumption counts."""

    value: T
    consumed_model_interactions: int
    consumed_tool_interactions: int


@dataclass(frozen=True, slots=True)
class _RecordedInteraction:
    kind: InteractionKind
    request: Event
    terminal: Event


class MockReplayContext:
    """Fail-closed access to recorded interactions for explicit local replay code."""

    def __init__(self, case: AgentCase) -> None:
        self._interactions = _interaction_tape(case)
        self._index = 0
        self._consumed_models = 0
        self._consumed_tools = 0

    @property
    def consumed_model_interactions(self) -> int:
        return self._consumed_models

    @property
    def consumed_tool_interactions(self) -> int:
        return self._consumed_tools

    def model_response(
        self,
        *,
        provider: str,
        model: str,
        input: JsonValue,
    ) -> JsonValue:
        """Return the next recorded model output only when the global interaction matches."""

        interaction = self._next("model")
        expected = interaction.request.payload
        if (
            expected.get("provider") != provider
            or expected.get("model") != model
            or expected.get("input") != input
        ):
            raise ReplayContractError(
                "mock replay model request does not match the next recorded interaction"
            )
        self._index += 1
        self._consumed_models += 1
        return _copy_json(interaction.terminal.payload.get("output"))

    def tool_result(self, *, name: str, arguments: JsonValue) -> RecordedToolResult:
        """Return the next recorded tool result without executing the recorded tool."""

        interaction = self._next("tool")
        expected = interaction.request.payload
        if expected.get("name") != name or expected.get("arguments") != arguments:
            raise ReplayContractError(
                "mock replay tool call does not match the next recorded interaction"
            )
        status = interaction.terminal.payload.get("status")
        if not isinstance(status, str):
            raise ReplayContractError("recorded tool result is missing a valid status")
        self._index += 1
        self._consumed_tools += 1
        return RecordedToolResult(
            status=status,
            result=_copy_json(interaction.terminal.payload.get("result")),
            error=_copy_json(interaction.terminal.payload.get("error")),
        )

    def assert_exhausted(self) -> None:
        """Fail when replayed code did not consume every captured external interaction."""

        remaining = self._interactions[self._index :]
        if remaining:
            remaining_models = sum(item.kind == "model" for item in remaining)
            remaining_tools = sum(item.kind == "tool" for item in remaining)
            raise ReplayContractError(
                "mock replay finished with unconsumed recorded interactions: "
                f"model={remaining_models}, tool={remaining_tools}"
            )

    def _next(self, requested_kind: InteractionKind) -> _RecordedInteraction:
        if self._index >= len(self._interactions):
            raise ReplayContractError("mock replay has no recorded interaction remaining")
        interaction = self._interactions[self._index]
        if interaction.kind != requested_kind:
            raise ReplayContractError(
                "mock replay interaction order mismatch: "
                f"next recorded interaction is {interaction.kind}, requested {requested_kind}"
            )
        return interaction


def run_mock_replay(
    case: AgentCase,
    entrypoint: Callable[[MockReplayContext], T],
    *,
    allow_incomplete: bool = False,
) -> ReplayRunResult[T]:
    """Execute an explicitly supplied local callable against recorded interactions.

    ReproAgent never imports or executes an entrypoint from AgentCase data. The caller supplies the
    callable directly. Providers and recorded tools are not invoked. Missing, out-of-order, or
    mismatched interactions fail closed with no live fallback. Caller code remains ordinary
    unsandboxed Python.
    """

    validate_mock_replay_source(case, allow_incomplete=allow_incomplete)
    context = MockReplayContext(case)
    value = entrypoint(context)
    context.assert_exhausted()
    return ReplayRunResult(
        value=value,
        consumed_model_interactions=context.consumed_model_interactions,
        consumed_tool_interactions=context.consumed_tool_interactions,
    )


def _interaction_tape(case: AgentCase) -> list[_RecordedInteraction]:
    terminal_by_parent = {
        event.parent_event_id: event
        for event in case.events
        if event.event_type in {EventType.MODEL_RESPONSE, EventType.TOOL_RESULT}
        and event.parent_event_id is not None
    }
    interactions: list[_RecordedInteraction] = []
    for event in case.events:
        if event.event_type == EventType.MODEL_REQUEST:
            interactions.append(
                _RecordedInteraction("model", event, terminal_by_parent[event.event_id])
            )
        elif event.event_type == EventType.TOOL_CALL:
            interactions.append(_RecordedInteraction("tool", event, terminal_by_parent[event.event_id]))
    return interactions


def _copy_json(value: JsonValue | None) -> JsonValue | None:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list):
        return [_copy_json(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _copy_json(item) for key, item in value.items()}
    value_type = type(value).__name__
    raise ReplayContractError(f"recorded interaction contains unsupported data: {value_type}")
