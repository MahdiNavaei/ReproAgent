"""Validated, provider-neutral domain models for AgentCase v0."""

from __future__ import annotations

import platform as platform_module
import sys
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

from reproagent._version import __version__
from reproagent.domain.enums import (
    CaptureCompleteness,
    CaptureStatus,
    DeterminismGuarantee,
    EventType,
    ExecutionOutcome,
    RedactionStatus,
    ReplayMode,
)

AGENTCASE_FORMAT_NAME = "agentcase"
AGENTCASE_FORMAT_VERSION = "0.1"
SUPPORTED_AGENTCASE_FORMAT_VERSIONS = frozenset({AGENTCASE_FORMAT_VERSION})


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(UTC)


class StrictModel(BaseModel):
    """Base model that rejects unknown schema fields instead of guessing semantics."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class RuntimeInfo(StrictModel):
    implementation: str = Field(min_length=1)
    python_version: str = Field(min_length=1)

    @classmethod
    def current(cls) -> RuntimeInfo:
        return cls(
            implementation=platform_module.python_implementation(),
            python_version=platform_module.python_version(),
        )


class PlatformInfo(StrictModel):
    system: str = Field(min_length=1)
    release: str = Field(min_length=1)
    machine: str = Field(min_length=1)

    @classmethod
    def current(cls) -> PlatformInfo:
        return cls(
            system=platform_module.system() or sys.platform,
            release=platform_module.release() or "unknown",
            machine=platform_module.machine() or "unknown",
        )


class ProviderInfo(StrictModel):
    provider_id: str = Field(min_length=1)
    provider_version: str | None = None


class ModelInfo(StrictModel):
    model_id: str = Field(min_length=1)
    configuration: dict[str, JsonValue] = Field(default_factory=dict)


class IntegrationInfo(StrictModel):
    integration_id: str = Field(min_length=1)
    integration_version: str | None = None


class AgentCaseMetadata(StrictModel):
    reproagent_version: str = Field(default=__version__, min_length=1)
    runtime: RuntimeInfo = Field(default_factory=RuntimeInfo.current)
    platform: PlatformInfo = Field(default_factory=PlatformInfo.current)
    provider: ProviderInfo | None = None
    model: ModelInfo | None = None
    integration: IntegrationInfo | None = None
    user_metadata: dict[str, JsonValue] = Field(default_factory=dict)
    extensions: dict[str, JsonValue] = Field(default_factory=dict)


class RedactionRecord(StrictModel):
    field_path: str = Field(min_length=1)
    rule_id: str = Field(min_length=1)
    replacement_marker: str = Field(min_length=1)
    irreversible: bool = True

    @model_validator(mode="after")
    def require_irreversible_marker(self) -> RedactionRecord:
        if not self.irreversible:
            raise ValueError("AgentCase v0 redaction records must be irreversible")
        return self


class RedactionMetadata(StrictModel):
    status: RedactionStatus = RedactionStatus.NONE
    records: tuple[RedactionRecord, ...] = ()
    warnings: tuple[str, ...] = ()
    potentially_sensitive_unredacted: bool = False
    extensions: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def status_matches_records(self) -> RedactionMetadata:
        if self.status == RedactionStatus.NONE and self.records:
            raise ValueError("redaction status 'none' cannot include redaction records")
        if self.status == RedactionStatus.REDACTED and not self.records:
            raise ValueError("redaction status 'redacted' requires at least one redaction record")
        return self


class Event(StrictModel):
    event_id: UUID = Field(default_factory=uuid4)
    event_type: EventType
    sequence: int = Field(ge=0)
    timestamp: datetime = Field(default_factory=utc_now)
    parent_event_id: UUID | None = None
    payload: dict[str, JsonValue] = Field(default_factory=dict)
    capture_status: CaptureStatus = CaptureStatus.CAPTURED
    redaction_status: RedactionStatus = RedactionStatus.NONE
    extensions: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return value


class ReplaySubstitution(StrictModel):
    target: str = Field(min_length=1)
    description: str = Field(min_length=1)


class ReplayMetadata(StrictModel):
    mode: ReplayMode
    source_case_id: UUID
    replayed_at: datetime
    substitutions: tuple[ReplaySubstitution, ...] = ()
    changed_provider: str | None = None
    changed_model: str | None = None
    changed_configuration: dict[str, JsonValue] = Field(default_factory=dict)
    determinism_guarantee: DeterminismGuarantee = DeterminismGuarantee.UNKNOWN
    unresolved_external_dependencies: tuple[str, ...] = ()
    live_side_effects_approved: bool = False
    extensions: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("replayed_at")
    @classmethod
    def replayed_at_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("replayed_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def mock_replay_cannot_approve_live_side_effects(self) -> ReplayMetadata:
        if self.mode == ReplayMode.MOCK and self.live_side_effects_approved:
            raise ValueError("mock replay cannot approve live side effects")
        return self


class AgentCase(StrictModel):
    format_name: str = AGENTCASE_FORMAT_NAME
    format_version: str = AGENTCASE_FORMAT_VERSION
    case_id: UUID = Field(default_factory=uuid4)
    execution_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=utc_now)
    metadata: AgentCaseMetadata = Field(default_factory=AgentCaseMetadata)
    events: tuple[Event, ...]
    outcome: ExecutionOutcome
    completeness: CaptureCompleteness
    redaction: RedactionMetadata = Field(default_factory=RedactionMetadata)
    replay: ReplayMetadata | None = None
    extensions: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("created_at")
    @classmethod
    def created_at_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_format_and_event_integrity(self) -> AgentCase:
        if self.format_name != AGENTCASE_FORMAT_NAME:
            raise ValueError(f"unsupported format_name: {self.format_name!r}")
        if self.format_version not in SUPPORTED_AGENTCASE_FORMAT_VERSIONS:
            raise ValueError(f"unsupported AgentCase format version: {self.format_version!r}")

        event_ids = [event.event_id for event in self.events]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("event IDs must be unique")

        expected_sequences = list(range(len(self.events)))
        actual_sequences = [event.sequence for event in self.events]
        if actual_sequences != expected_sequences:
            raise ValueError(
                "event sequence numbers must be contiguous, unique, ordered, and start at 0"
            )

        sequence_by_id = {event.event_id: event.sequence for event in self.events}
        for event in self.events:
            if event.parent_event_id is None:
                continue
            parent_sequence = sequence_by_id.get(event.parent_event_id)
            if parent_sequence is None:
                raise ValueError(
                    f"parent event {event.parent_event_id} does not reference an event in this case"
                )
            if parent_sequence >= event.sequence:
                raise ValueError("parent events must appear before their children")

        return self
