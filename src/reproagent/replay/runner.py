"""Explicit deterministic replay runner for caller-supplied local Python code."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

from pydantic import JsonValue

from reproagent.domain import AgentCase, Event, EventType
from reproagent.replay.errors import ReplayContractError
from reproagent.replay.mock import validate_mock_replay_source

T = TypeVar("T")


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


class MockReplayContext:
    """Fail-closed access to recorded interactions for explicit local replay code."""

    def __init__(self, case: AgentCase) -> None:
        self._model_pairs = _interaction_pairs(case, EventType.MODEL_REQUEST, EventType.MODEL_RESPONSE)
        self._tool_pairs = _interaction_pairs(case, EventType.TOOL_CALL, EventType.TOOL_RESULT)
        self._model_index = 0
        self._tool_index = 0

    @property
    def consumed_model_interactions(self) -> int:
        return self._model_index

    @property
    def consumed_tool_interactions(self) -> int:
        return self._tool_index

    def model_response(
        self,
        *,
        provider: str,
        model: str,
        input: JsonValue,
    ) -> JsonValue:
        """Return the next recorded model output only when the request contract matches."""

        if self._model_index >= len(self._model_pairs):
            raise ReplayContractError("mock replay has no recorded model interaction remaining")
        request, response = self._model_pairs[self._model_index]
        expected = request.payload
        if (
            expected.get("provider") != provider
            or expected.get("model") != model
            or expected.get("input") != input
        ):
            raise ReplayContractError(
                "mock replay model request does not match the next recorded interaction"
            )
        self._model_index += 1
        return _copy_json(response.payload.get("output"))

    def tool_result(self, *, name: str, arguments: JsonValue) -> RecordedToolResult:
        """Return the next recorded tool result without executing the recorded tool."""

        if self._tool_index >= len(self._tool_pairs):
            raise ReplayContractError("mock replay has no recorded tool interaction remaining")
        call, result = self._tool_pairs[self._tool_index]
        expected = call.payload
        if expected.get("name") != name or expected.get("arguments") != arguments:
            raise ReplayContractError(
                "mock replay tool call does not match the next recorded interaction"
            )
        status = result.payload.get("status")
        if not isinstance(status, str):
            raise ReplayContractError("recorded tool result is missing a valid status")
        self._tool_index += 1
        return RecordedToolResult(
            status=status,
            result=_copy_json(result.payload.get("result")),
            error=_copy_json(result.payload.get("error")),
        )

    def assert_exhausted(self) -> None:
        """Fail when the replayed code did not consume every captured external interaction."""

        remaining_models = len(self._model_pairs) - self._model_index
        remaining_tools = len(self._tool_pairs) - self._tool_index
        if remaining_models or remaining_tools:
            raise ReplayContractError(
                "mock replay finished with unconsumed recorded interactions: "
                f"model={remaining_models}, tool={remaining_tools}"
            )


def run_mock_replay(
    case: AgentCase,
    entrypoint: Callable[[MockReplayContext], T],
    *,
    allow_incomplete: bool = False,
) -> ReplayRunResult[T]:
    """Execute one explicitly supplied local callable against recorded external interactions.

    ReproAgent never imports or executes an entrypoint from AgentCase data. The caller supplies the
    callable directly. Model providers and recorded tools are not invoked; missing or mismatched
    interactions fail closed with no live fallback. The callable itself is ordinary local Python code
    and is not sandboxed by ReproAgent.
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


def _interaction_pairs(
    case: AgentCase,
    parent_type: EventType,
    child_type: EventType,
) -> list[tuple[Event, Event]]:
    children = {
        event.parent_event_id: event
        for event in case.events
        if event.event_type == child_type and event.parent_event_id is not None
    }
    return [
        (event, children[event.event_id])
        for event in case.events
        if event.event_type == parent_type
    ]


def _copy_json(value: JsonValue | None) -> JsonValue | None:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list):
        return [_copy_json(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _copy_json(item) for key, item in value.items()}
    raise ReplayContractError(f"recorded interaction contains unsupported data: {type(value).__name__}")
