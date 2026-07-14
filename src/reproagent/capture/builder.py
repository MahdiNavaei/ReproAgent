"""Mutable ordered builder that produces the public immutable AgentCase model."""

from __future__ import annotations

from threading import RLock
from uuid import UUID, uuid4

from pydantic import JsonValue

from reproagent.capture.diagnostics import CAPTURE_EXTENSION_NAMESPACE, CaptureDiagnostics
from reproagent.capture.errors import (
    CaptureLifecycleError,
    CaptureNormalizationError,
    CaptureRedactionError,
)
from reproagent.domain import (
    AgentCase,
    AgentCaseMetadata,
    CaptureCompleteness,
    CaptureStatus,
    Event,
    EventType,
    ExecutionOutcome,
    IntegrationInfo,
    RedactionMetadata,
    RedactionRecord,
    RedactionStatus,
)
from reproagent.domain.models import utc_now
from reproagent.security import RedactionError, RedactionHit, Redactor

_COMPLETENESS_RANK = {
    CaptureCompleteness.COMPLETE: 0,
    CaptureCompleteness.DEGRADED: 1,
    CaptureCompleteness.PARTIAL: 2,
    CaptureCompleteness.INTERRUPTED: 3,
    CaptureCompleteness.UNSUPPORTED: 4,
}


class AgentCaseBuilder:
    """Append events efficiently, track capture health, and build one AgentCase."""

    def __init__(
        self,
        *,
        redactor: Redactor,
        user_metadata: dict[str, JsonValue] | None = None,
    ) -> None:
        self._lock = RLock()
        self._redactor = redactor
        self._case_id = uuid4()
        self._execution_id = uuid4()
        self._created_at = utc_now()
        self._events: list[Event] = []
        self._events_by_id: dict[UUID, Event] = {}
        self._outcome = ExecutionOutcome.UNKNOWN
        self._outcome_reason: str | None = None
        self._completeness = CaptureCompleteness.COMPLETE
        self._redaction_hits: list[RedactionHit] = []
        self._diagnostics = CaptureDiagnostics()
        self._built_case: AgentCase | None = None

        try:
            metadata_result = self._redactor.redact(
                user_metadata or {},
                base_pointer="/metadata/user_metadata",
            )
        except RedactionError as exc:
            raise CaptureRedactionError(
                "user metadata redaction failed; unredacted metadata was not retained"
            ) from exc
        self._redaction_hits.extend(metadata_result.hits)
        self._metadata = AgentCaseMetadata(
            integration=IntegrationInfo(
                integration_id="manual-python",
                integration_version="0.1",
            ),
            user_metadata=_require_object(metadata_result.value),
        )

    @property
    def outcome(self) -> ExecutionOutcome:
        return self._outcome

    @property
    def outcome_reason(self) -> str | None:
        return self._outcome_reason

    @property
    def completeness(self) -> CaptureCompleteness:
        return self._completeness

    @property
    def diagnostics(self) -> CaptureDiagnostics:
        return self._diagnostics

    def get_event(self, event_id: UUID) -> Event:
        try:
            return self._events_by_id[event_id]
        except KeyError as exc:
            raise CaptureLifecycleError(f"unknown parent event ID: {event_id}") from exc

    def append_event(
        self,
        *,
        event_type: EventType,
        payload: dict[str, JsonValue],
        parent_event_id: UUID | None = None,
        capture_status: CaptureStatus = CaptureStatus.CAPTURED,
        extensions: dict[str, JsonValue] | None = None,
    ) -> UUID:
        with self._lock:
            if self._built_case is not None:
                raise CaptureLifecycleError("cannot append events after AgentCase construction")
            if parent_event_id is not None and parent_event_id not in self._events_by_id:
                raise CaptureLifecycleError(f"unknown parent event ID: {parent_event_id}")

            sequence = len(self._events)
            try:
                payload_result = self._redactor.redact(
                    payload,
                    base_pointer=f"/events/{sequence}/payload",
                )
                extension_result = self._redactor.redact(
                    extensions or {},
                    base_pointer=f"/events/{sequence}/extensions",
                )
            except RedactionError as exc:
                self._diagnostics.record_redaction_failure(event_type.value, type(exc).__name__)
                self._elevate_completeness(CaptureCompleteness.PARTIAL)
                raise CaptureRedactionError(
                    f"redaction failed for {event_type.value}; raw event data was dropped"
                ) from exc

            self._redaction_hits.extend(payload_result.hits)
            self._redaction_hits.extend(extension_result.hits)
            event_hits = (*payload_result.hits, *extension_result.hits)
            event = Event(
                event_id=uuid4(),
                event_type=event_type,
                sequence=sequence,
                timestamp=utc_now(),
                parent_event_id=parent_event_id,
                payload=_require_object(payload_result.value),
                capture_status=capture_status,
                redaction_status=(RedactionStatus.REDACTED if event_hits else RedactionStatus.NONE),
                extensions=_require_object(extension_result.value),
            )
            self._events.append(event)
            self._events_by_id[event.event_id] = event
            return event.event_id

    def record_normalization_failure(self, event_type: EventType, error: Exception) -> None:
        self._diagnostics.record_normalization_failure(event_type.value, type(error).__name__)
        self._elevate_completeness(CaptureCompleteness.PARTIAL)

    def set_outcome(self, outcome: ExecutionOutcome, reason: str | None = None) -> None:
        with self._lock:
            self._ensure_mutable()
            self._outcome = outcome
            self._outcome_reason = reason

    def set_completeness(
        self,
        completeness: CaptureCompleteness,
        *,
        reason: str | None = None,
    ) -> None:
        with self._lock:
            self._ensure_mutable()
            self._elevate_completeness(completeness)
            if reason:
                self._diagnostics.add_degraded_reason(reason)

    def build(self) -> AgentCase:
        with self._lock:
            if self._built_case is not None:
                return self._built_case

            unique_records: dict[tuple[str, str, str], RedactionRecord] = {}
            for hit in self._redaction_hits:
                key = (hit.field_path, hit.rule_id, hit.replacement_marker)
                unique_records[key] = RedactionRecord(
                    field_path=hit.field_path,
                    rule_id=hit.rule_id,
                    replacement_marker=hit.replacement_marker,
                )

            records = tuple(unique_records.values())
            if self._diagnostics.redaction_failures:
                redaction_status = RedactionStatus.PARTIAL
            elif records:
                redaction_status = RedactionStatus.REDACTED
            else:
                redaction_status = RedactionStatus.NONE

            warning = (
                "Default redaction is best-effort and does not prove that the artifact is free "
                "of secrets, PII, or other sensitive content."
            )
            redaction = RedactionMetadata(
                status=redaction_status,
                records=records,
                warnings=(warning,),
                potentially_sensitive_unredacted=True,
            )
            self._built_case = AgentCase(
                case_id=self._case_id,
                execution_id=self._execution_id,
                created_at=self._created_at,
                metadata=self._metadata,
                events=tuple(self._events),
                outcome=self._outcome,
                completeness=self._completeness,
                redaction=redaction,
                extensions={
                    CAPTURE_EXTENSION_NAMESPACE: self._diagnostics.to_extension(),
                },
            )
            return self._built_case

    def _ensure_mutable(self) -> None:
        if self._built_case is not None:
            raise CaptureLifecycleError("AgentCase has already been finalized")

    def _elevate_completeness(self, completeness: CaptureCompleteness) -> None:
        if _COMPLETENESS_RANK[completeness] > _COMPLETENESS_RANK[self._completeness]:
            self._completeness = completeness


def _require_object(value: JsonValue) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise CaptureNormalizationError("expected a JSON object after normalization")
    return value
