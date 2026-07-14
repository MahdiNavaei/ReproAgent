"""Explicit local callable replay using recorded model and tool interactions."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Generic, TypeVar

from pydantic import JsonValue

from reproagent.capture import CaptureSession, capture
from reproagent.domain import (
    AgentCase,
    DeterminismGuarantee,
    Event,
    EventType,
    ReplayMetadata,
    ReplayMode,
    ReplaySubstitution,
)
from reproagent.replay.errors import ReplayContractError, ReplaySafetyError
from reproagent.replay.mock import validate_mock_replay_source

R = TypeVar("R")


@dataclass(frozen=True, slots=True)
class RecordedToolOutcome:
    """Recorded terminal tool outcome returned to explicitly supplied replay code."""

    status: str
    result: JsonValue | None
    error: JsonValue | None


@dataclass(frozen=True, slots=True)
class MockReplayRun(Generic[R]):
    """Return value and newly captured AgentCase from one explicit replay execution."""

    value: R
    case: AgentCase


@dataclass(frozen=True, slots=True)
class _Interaction:
    request: Event
    terminal: Event


class MockReplayContext:
    """Fail-closed sequence of recorded interactions for trusted caller-supplied code."""

    def __init__(self, interactions: tuple[_Interaction, ...], session: CaptureSession) -> None:
        self._interactions = interactions
        self._session = session
        self._index = 0

    @property
    def remaining(self) -> int:
        return len(self._interactions) - self._index

    def model_response(
        self,
        *,
        provider: str | None = None,
        model: str | None = None,
    ) -> JsonValue:
        interaction = self._next(EventType.MODEL_REQUEST)
        request = interaction.request.payload
        recorded_provider = _require_string(request, "provider")
        recorded_model = _require_string(request, "model")
        if provider is not None and provider != recorded_provider:
            raise ReplayContractError(
                f"recorded provider is {recorded_provider!r}, replay requested {provider!r}"
            )
        if model is not None and model != recorded_model:
            raise ReplayContractError(
                f"recorded model is {recorded_model!r}, replay requested {model!r}"
            )

        request_id = self._session.model_request(
            provider=recorded_provider,
            model=recorded_model,
            input=deepcopy(request.get("input")),
            parameters=_require_object(request.get("parameters", {}), "parameters"),
            tools=tuple(_require_list(request.get("tools", []), "tools")),
            extensions={"reproagent.replay.substitution": "recorded-model-response"},
        )
        terminal = interaction.terminal.payload
        output = deepcopy(terminal.get("output"))
        self._session.model_response(
            parent_event_id=request_id,
            provider=_require_string(terminal, "provider"),
            model=_require_string(terminal, "model"),
            output=output,
            finish_reason=_optional_string(terminal.get("finish_reason"), "finish_reason"),
            usage=_optional_object(terminal.get("usage"), "usage"),
            latency_ms=_optional_float(terminal.get("latency_ms"), "latency_ms"),
            extensions={"reproagent.replay.substitution": "recorded-model-response"},
        )
        return output

    def tool_result(self, *, name: str) -> RecordedToolOutcome:
        interaction = self._next(EventType.TOOL_CALL)
        request = interaction.request.payload
        recorded_name = _require_string(request, "name")
        if name != recorded_name:
            raise ReplayContractError(
                f"recorded tool is {recorded_name!r}, replay requested {name!r}"
            )

        call_id = _require_string(request, "call_id")
        call_event_id = self._session.tool_call(
            name=recorded_name,
            arguments=deepcopy(request.get("arguments")),
            call_id=call_id,
            extensions={"reproagent.replay.substitution": "recorded-tool-result"},
        )
        terminal = interaction.terminal.payload
        status = _require_string(terminal, "status")
        result = deepcopy(terminal.get("result"))
        error = deepcopy(terminal.get("error"))
        self._session.tool_result(
            parent_event_id=call_event_id,
            name=recorded_name,
            status=status,
            result=result,
            error=error,
            latency_ms=_optional_float(terminal.get("latency_ms"), "latency_ms"),
            call_id=call_id,
            extensions={"reproagent.replay.substitution": "recorded-tool-result"},
        )
        return RecordedToolOutcome(status=status, result=result, error=error)

    def require_consumed(self) -> None:
        if self.remaining:
            next_type = self._interactions[self._index].request.event_type.value
            raise ReplayContractError(
                f"mock replay finished with {self.remaining} unconsumed interaction(s); "
                f"next recorded interaction is {next_type}"
            )

    def _next(self, expected_type: EventType) -> _Interaction:
        if self._index >= len(self._interactions):
            raise ReplayContractError(
                f"mock replay requested {expected_type.value} after recorded interactions ended"
            )
        interaction = self._interactions[self._index]
        if interaction.request.event_type != expected_type:
            raise ReplayContractError(
                f"next recorded interaction is {interaction.request.event_type.value}, "
                f"not {expected_type.value}"
            )
        self._index += 1
        return interaction


def run_mock_replay(
    case: AgentCase,
    runner: object,
    *,
    allow_incomplete: bool = False,
    require_all_interactions: bool = True,
) -> MockReplayRun[object]:
    """Execute an explicitly supplied local callable against recorded interactions only.

    ReproAgent never imports or executes code referenced by the AgentCase. ``runner`` must be a
    callable supplied directly by the caller and must accept one ``MockReplayContext`` argument.
    The context has no live fallback: order, provider/model constraints, tool names, and exhaustion
    fail closed with ``ReplayContractError``.
    """

    if not callable(runner):
        raise ReplayContractError("mock replay runner must be an explicitly supplied callable")
    validate_mock_replay_source(case, allow_incomplete=allow_incomplete)
    interactions = _build_interactions(case)

    with capture(name="mock-replay", entrypoint=getattr(runner, "__qualname__", None)) as session:
        context = MockReplayContext(interactions, session)
        value = runner(context)
        if require_all_interactions:
            context.require_consumed()

    if session.case is None:
        raise ReplaySafetyError("mock replay completed without a captured execution")
    replay = ReplayMetadata(
        mode=ReplayMode.MOCK,
        source_case_id=case.case_id,
        replayed_at=datetime.now(UTC),
        substitutions=(
            ReplaySubstitution(
                target="model.provider_calls",
                description="recorded model responses substituted through MockReplayContext",
            ),
            ReplaySubstitution(
                target="tool.side_effects",
                description="recorded tool outcomes substituted through MockReplayContext",
            ),
        ),
        determinism_guarantee=DeterminismGuarantee.DETERMINISTIC,
        unresolved_external_dependencies=(),
        live_side_effects_approved=False,
        extensions={"reproagent.replay.runner": "explicit-local-callable"},
    )
    replayed_case = session.case.model_copy(update={"replay": replay})
    if replayed_case.replay is None or replayed_case.replay.live_side_effects_approved:
        raise ReplaySafetyError("mock replay must never approve live side effects")
    return MockReplayRun(value=value, case=replayed_case)


def _build_interactions(case: AgentCase) -> tuple[_Interaction, ...]:
    terminal_by_parent = {
        event.parent_event_id: event
        for event in case.events
        if event.event_type in {EventType.MODEL_RESPONSE, EventType.TOOL_RESULT}
        and event.parent_event_id is not None
    }
    return tuple(
        _Interaction(request=event, terminal=terminal_by_parent[event.event_id])
        for event in case.events
        if event.event_type in {EventType.MODEL_REQUEST, EventType.TOOL_CALL}
    )


def _require_string(payload: dict[str, JsonValue], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise ReplayContractError(f"recorded {key} must be a string")
    return value


def _require_object(value: JsonValue, name: str) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise ReplayContractError(f"recorded {name} must be an object")
    return deepcopy(value)


def _optional_object(value: JsonValue | None, name: str) -> dict[str, JsonValue] | None:
    if value is None:
        return None
    return _require_object(value, name)


def _require_list(value: JsonValue, name: str) -> list[JsonValue]:
    if not isinstance(value, list):
        raise ReplayContractError(f"recorded {name} must be an array")
    return deepcopy(value)


def _optional_string(value: JsonValue | None, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ReplayContractError(f"recorded {name} must be a string or null")
    return value


def _optional_float(value: JsonValue | None, name: str) -> float | None:
    if value is None:
        return None
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ReplayContractError(f"recorded {name} must be numeric or null")
    return float(value)
