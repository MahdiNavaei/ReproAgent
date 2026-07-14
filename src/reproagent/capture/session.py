"""Framework-neutral manual Capture Session lifecycle and event API."""

from __future__ import annotations

import os
import traceback as traceback_module
from contextvars import Token
from enum import StrEnum
from pathlib import Path
from threading import RLock
from time import perf_counter
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import JsonValue, ValidationError

from reproagent.agentcase import atomic_dump_agentcase
from reproagent.capture.builder import AgentCaseBuilder
from reproagent.capture.context import reset_current_session, set_current_session
from reproagent.capture.errors import (
    CaptureLifecycleError,
    CaptureNormalizationError,
    CapturePersistenceError,
    CaptureRedactionError,
    NestedCaptureSessionError,
)
from reproagent.capture.payloads import (
    ExceptionPayload,
    ExecutionEndPayload,
    ExecutionStartPayload,
    MessagePayload,
    ModelRequestPayload,
    ModelResponsePayload,
    RetryPayload,
    StrictPayloadModel,
    ToolCallPayload,
    ToolDefinitionPayload,
    ToolResultPayload,
    ToolResultStatus,
)
from reproagent.domain import (
    AgentCase,
    CaptureCompleteness,
    Event,
    EventType,
    ExecutionOutcome,
)
from reproagent.security import Redactor


class CaptureSessionState(StrEnum):
    CREATED = "created"
    ACTIVE = "active"
    FINALIZING = "finalizing"
    CLOSED = "closed"


class CaptureSession:
    """One explicit local execution capture with ordered normalized events."""

    def __init__(
        self,
        *,
        output: str | Path | None = None,
        name: str | None = None,
        entrypoint: str | None = None,
        user_metadata: dict[str, JsonValue] | None = None,
        overwrite: bool = False,
        redactor: Redactor | None = None,
    ) -> None:
        self._lock = RLock()
        self._state = CaptureSessionState.CREATED
        self._output = Path(output) if output is not None else None
        self._name = name
        self._entrypoint = entrypoint
        self._overwrite = overwrite
        self._builder = AgentCaseBuilder(
            redactor=redactor or Redactor(),
            user_metadata=user_metadata,
        )
        self._started_perf: float | None = None
        self._start_event_id: UUID | None = None
        self._final_case: AgentCase | None = None
        self._context_token: Token[CaptureSession | None] | None = None
        self._captured_exception_ids: set[int] = set()

    @property
    def state(self) -> CaptureSessionState:
        return self._state

    @property
    def output(self) -> Path | None:
        return self._output

    @property
    def case(self) -> AgentCase | None:
        return self._final_case

    def __enter__(self) -> CaptureSession:
        from reproagent.capture.context import get_current_session

        with self._lock:
            if self._state != CaptureSessionState.CREATED:
                raise CaptureLifecycleError(
                    f"cannot enter capture session from state {self._state.value!r}"
                )
            if get_current_session() is not None:
                raise NestedCaptureSessionError(
                    "nested top-level capture sessions are not supported in the MVP"
                )
            token = set_current_session(self)
            self._context_token = token
            self._state = CaptureSessionState.ACTIVE
            self._started_perf = perf_counter()
            try:
                payload = self._payload(
                    EventType.EXECUTION_START,
                    ExecutionStartPayload,
                    name=self._name,
                    entrypoint=self._entrypoint,
                    working_directory=str(Path.cwd()),
                    process_id=os.getpid(),
                )
                self._start_event_id = self._builder.append_event(
                    event_type=EventType.EXECUTION_START,
                    payload=payload,
                )
            except Exception:
                self._state = CaptureSessionState.CREATED
                self._context_token = None
                reset_current_session(token)
                raise
            return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: Any,
    ) -> Literal[False]:
        capture_failures: list[BaseException] = []

        def remember_capture_failure(failure: BaseException) -> None:
            capture_failures.append(failure)
            try:
                self._builder.set_completeness(
                    CaptureCompleteness.PARTIAL,
                    reason=(
                        "capture instrumentation failed while preserving an application exception"
                    ),
                )
            except BaseException:
                pass

        try:
            if exc is not None and self._state == CaptureSessionState.ACTIVE:
                if id(exc) not in self._captured_exception_ids:
                    try:
                        self.exception(exc, handled=False)
                    except BaseException as capture_exc:
                        remember_capture_failure(capture_exc)
                try:
                    if self._builder.outcome in {
                        ExecutionOutcome.UNKNOWN,
                        ExecutionOutcome.SUCCESS,
                    }:
                        self._builder.set_outcome(ExecutionOutcome.FAILURE)
                except BaseException as capture_exc:
                    remember_capture_failure(capture_exc)

            if self._state == CaptureSessionState.ACTIVE:
                try:
                    self.finalize()
                except BaseException as finalize_exc:
                    remember_capture_failure(finalize_exc)
        finally:
            if self._context_token is not None:
                token = self._context_token
                self._context_token = None
                try:
                    reset_current_session(token)
                except BaseException as reset_exc:
                    remember_capture_failure(reset_exc)

        if exc is not None:
            for failure in capture_failures:
                try:
                    exc.add_note(
                        "ReproAgent capture also failed while preserving the original application "
                        f"exception ({type(failure).__name__})."
                    )
                except BaseException:
                    pass
            return False

        if capture_failures:
            raise capture_failures[0]
        return False

    def message(
        self,
        *,
        role: str,
        content: JsonValue,
        name: str | None = None,
        message_id: str | None = None,
        parent_event_id: UUID | None = None,
        extensions: dict[str, JsonValue] | None = None,
    ) -> UUID:
        payload = self._payload(
            EventType.MESSAGE,
            MessagePayload,
            role=role,
            content=content,
            name=name,
            message_id=message_id,
        )
        return self._record(
            EventType.MESSAGE,
            payload,
            parent_event_id=parent_event_id,
            extensions=extensions,
        )

    def model_request(
        self,
        *,
        provider: str,
        model: str,
        input: JsonValue,
        parameters: dict[str, JsonValue] | None = None,
        tools: tuple[JsonValue, ...] = (),
        parent_event_id: UUID | None = None,
        extensions: dict[str, JsonValue] | None = None,
    ) -> UUID:
        payload = self._payload(
            EventType.MODEL_REQUEST,
            ModelRequestPayload,
            provider=provider,
            model=model,
            input=input,
            parameters=parameters or {},
            tools=tools,
        )
        return self._record(
            EventType.MODEL_REQUEST,
            payload,
            parent_event_id=parent_event_id,
            extensions=extensions,
        )

    def model_response(
        self,
        *,
        parent_event_id: UUID,
        provider: str,
        model: str,
        output: JsonValue,
        finish_reason: str | None = None,
        usage: dict[str, JsonValue] | None = None,
        latency_ms: float | None = None,
        extensions: dict[str, JsonValue] | None = None,
    ) -> UUID:
        self._require_parent_type(parent_event_id, EventType.MODEL_REQUEST)
        payload = self._payload(
            EventType.MODEL_RESPONSE,
            ModelResponsePayload,
            provider=provider,
            model=model,
            output=output,
            finish_reason=finish_reason,
            usage=usage,
            latency_ms=latency_ms,
        )
        return self._record(
            EventType.MODEL_RESPONSE,
            payload,
            parent_event_id=parent_event_id,
            extensions=extensions,
        )

    def tool_definition(
        self,
        *,
        name: str,
        description: str | None = None,
        input_schema: JsonValue | None = None,
        parent_event_id: UUID | None = None,
        extensions: dict[str, JsonValue] | None = None,
    ) -> UUID:
        payload = self._payload(
            EventType.TOOL_DEFINITION,
            ToolDefinitionPayload,
            name=name,
            description=description,
            input_schema=input_schema,
        )
        return self._record(
            EventType.TOOL_DEFINITION,
            payload,
            parent_event_id=parent_event_id,
            extensions=extensions,
        )

    def tool_call(
        self,
        *,
        name: str,
        arguments: JsonValue,
        parent_event_id: UUID | None = None,
        call_id: str | None = None,
        extensions: dict[str, JsonValue] | None = None,
    ) -> UUID:
        payload = self._payload(
            EventType.TOOL_CALL,
            ToolCallPayload,
            name=name,
            call_id=call_id or str(uuid4()),
            arguments=arguments,
        )
        return self._record(
            EventType.TOOL_CALL,
            payload,
            parent_event_id=parent_event_id,
            extensions=extensions,
        )

    def tool_result(
        self,
        *,
        parent_event_id: UUID,
        name: str,
        status: ToolResultStatus | str,
        result: JsonValue | None = None,
        error: JsonValue | None = None,
        latency_ms: float | None = None,
        call_id: str | None = None,
        extensions: dict[str, JsonValue] | None = None,
    ) -> UUID:
        parent = self._require_parent_type(parent_event_id, EventType.TOOL_CALL)
        parent_call_id = parent.payload.get("call_id")
        parent_name = parent.payload.get("name")
        if parent_name != name:
            raise CaptureLifecycleError("tool result name must match its parent tool call")
        resolved_call_id = call_id or parent_call_id
        if not isinstance(resolved_call_id, str):
            raise CaptureLifecycleError("parent tool call does not contain a valid call_id")
        if call_id is not None and call_id != parent_call_id:
            raise CaptureLifecycleError("tool result call_id must match its parent tool call")

        payload = self._payload(
            EventType.TOOL_RESULT,
            ToolResultPayload,
            name=name,
            call_id=resolved_call_id,
            status=status,
            result=result,
            error=error,
            latency_ms=latency_ms,
        )
        return self._record(
            EventType.TOOL_RESULT,
            payload,
            parent_event_id=parent_event_id,
            extensions=extensions,
        )

    def exception(
        self,
        exc: BaseException,
        *,
        parent_event_id: UUID | None = None,
        handled: bool,
        include_traceback: bool = True,
        extensions: dict[str, JsonValue] | None = None,
    ) -> UUID:
        traceback_text = None
        if include_traceback and exc.__traceback__ is not None:
            traceback_text = "".join(
                traceback_module.format_exception(type(exc), exc, exc.__traceback__)
            )
        payload = self._payload(
            EventType.EXCEPTION,
            ExceptionPayload,
            exception_type=type(exc).__name__,
            message=str(exc),
            traceback=traceback_text,
            handled=handled,
        )
        event_id = self._record(
            EventType.EXCEPTION,
            payload,
            parent_event_id=parent_event_id,
            extensions=extensions,
        )
        self._captured_exception_ids.add(id(exc))
        return event_id

    def retry(
        self,
        *,
        attempt: int,
        reason: str | None = None,
        delay_ms: float | None = None,
        target: str | None = None,
        parent_event_id: UUID | None = None,
        extensions: dict[str, JsonValue] | None = None,
    ) -> UUID:
        payload = self._payload(
            EventType.RETRY,
            RetryPayload,
            attempt=attempt,
            reason=reason,
            delay_ms=delay_ms,
            target=target,
        )
        return self._record(
            EventType.RETRY,
            payload,
            parent_event_id=parent_event_id,
            extensions=extensions,
        )

    def custom(
        self,
        *,
        payload: dict[str, JsonValue],
        parent_event_id: UUID | None = None,
        extensions: dict[str, JsonValue] | None = None,
    ) -> UUID:
        self._require_active()
        return self._builder.append_event(
            event_type=EventType.CUSTOM,
            payload=dict(payload),
            parent_event_id=parent_event_id,
            extensions=extensions,
        )

    def set_outcome(
        self,
        outcome: ExecutionOutcome | str,
        *,
        reason: str | None = None,
    ) -> None:
        self._require_active()
        try:
            normalized_outcome = ExecutionOutcome(outcome)
        except ValueError as exc:
            raise CaptureNormalizationError("invalid execution outcome") from exc
        self._builder.set_outcome(normalized_outcome, reason)

    def set_completeness(
        self,
        completeness: CaptureCompleteness | str,
        *,
        reason: str | None = None,
    ) -> None:
        self._require_active()
        try:
            normalized_completeness = CaptureCompleteness(completeness)
        except ValueError as exc:
            raise CaptureNormalizationError("invalid capture completeness") from exc
        self._builder.set_completeness(normalized_completeness, reason=reason)

    def finalize(self) -> AgentCase:
        with self._lock:
            if self._state == CaptureSessionState.CLOSED:
                if self._final_case is None:
                    raise CaptureLifecycleError(
                        "capture session closed without a finalized AgentCase"
                    )
                return self._final_case
            if self._state == CaptureSessionState.CREATED:
                raise CaptureLifecycleError("cannot finalize a capture session before activation")
            if self._state == CaptureSessionState.FINALIZING:
                raise CaptureLifecycleError("capture session is already finalizing")

            self._state = CaptureSessionState.FINALIZING
            try:
                if self._builder.outcome == ExecutionOutcome.UNKNOWN:
                    self._builder.set_outcome(ExecutionOutcome.SUCCESS)
                duration_ms = self._duration_ms()
                end_payload = self._payload(
                    EventType.EXECUTION_END,
                    ExecutionEndPayload,
                    outcome=self._builder.outcome.value,
                    duration_ms=duration_ms,
                    reason=self._builder.outcome_reason,
                )
                assert self._start_event_id is not None
                try:
                    self._builder.append_event(
                        event_type=EventType.EXECUTION_END,
                        payload=end_payload,
                        parent_event_id=self._start_event_id,
                    )
                except CaptureRedactionError:
                    fallback_payload = self._payload(
                        EventType.EXECUTION_END,
                        ExecutionEndPayload,
                        outcome=self._builder.outcome.value,
                        duration_ms=duration_ms,
                        reason=None,
                    )
                    self._builder.append_event(
                        event_type=EventType.EXECUTION_END,
                        payload=fallback_payload,
                        parent_event_id=self._start_event_id,
                    )
                case = self._builder.build()
                self._final_case = case
                self._state = CaptureSessionState.CLOSED
            except Exception:
                self._state = CaptureSessionState.CLOSED
                raise

        if self._output is not None:
            try:
                atomic_dump_agentcase(
                    case,
                    self._output,
                    overwrite=self._overwrite,
                    create_parents=True,
                )
            except Exception as exc:
                raise CapturePersistenceError(
                    f"unable to persist AgentCase to {self._output}"
                ) from exc
        return case

    def _record(
        self,
        event_type: EventType,
        payload: dict[str, JsonValue],
        *,
        parent_event_id: UUID | None,
        extensions: dict[str, JsonValue] | None,
    ) -> UUID:
        self._require_active()
        return self._builder.append_event(
            event_type=event_type,
            payload=payload,
            parent_event_id=parent_event_id,
            extensions=extensions,
        )

    def _payload(
        self,
        event_type: EventType,
        model_type: type[StrictPayloadModel],
        **values: object,
    ) -> dict[str, JsonValue]:
        try:
            model = model_type.model_validate(values)
        except ValidationError as exc:
            self._builder.record_normalization_failure(event_type, exc)
            raise CaptureNormalizationError(
                f"invalid normalized payload for {event_type.value}; raw data was not retained"
            ) from exc
        return model.as_payload()

    def _require_parent_type(self, event_id: UUID, expected: EventType) -> Event:
        self._require_active()
        event = self._builder.get_event(event_id)
        if event.event_type != expected:
            raise CaptureLifecycleError(
                f"expected parent event type {expected.value}, got {event.event_type.value}"
            )
        return event

    def _require_active(self) -> None:
        if self._state != CaptureSessionState.ACTIVE:
            raise CaptureLifecycleError(
                f"events can only be recorded while capture is active; state={self._state.value}"
            )

    def _duration_ms(self) -> float:
        if self._started_perf is None:
            return 0.0
        return max(0.0, (perf_counter() - self._started_perf) * 1000.0)


def capture(
    *,
    output: str | Path | None = None,
    name: str | None = None,
    entrypoint: str | None = None,
    user_metadata: dict[str, JsonValue] | None = None,
    overwrite: bool = False,
    redactor: Redactor | None = None,
) -> CaptureSession:
    """Create an inactive Capture Session for use as an explicit context manager."""

    return CaptureSession(
        output=output,
        name=name,
        entrypoint=entrypoint,
        user_metadata=user_metadata,
        overwrite=overwrite,
        redactor=redactor,
    )
