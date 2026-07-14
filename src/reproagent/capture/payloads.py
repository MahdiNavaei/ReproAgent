"""Normalized provider-neutral payload contracts emitted by manual capture."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


class StrictPayloadModel(BaseModel):
    """Strict immutable payload model used before redaction and event creation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    def as_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json", exclude_none=True)


class ToolResultStatus(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"


class ExecutionStartPayload(StrictPayloadModel):
    name: str | None = None
    entrypoint: str | None = None
    working_directory: str | None = None
    process_id: int = Field(ge=0)


class ExecutionEndPayload(StrictPayloadModel):
    outcome: str = Field(min_length=1)
    duration_ms: float = Field(ge=0)
    reason: str | None = None


class MessagePayload(StrictPayloadModel):
    role: str = Field(min_length=1)
    content: JsonValue
    name: str | None = None
    message_id: str | None = None


class ModelRequestPayload(StrictPayloadModel):
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    input: JsonValue
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    tools: tuple[JsonValue, ...] = ()


class ModelResponsePayload(StrictPayloadModel):
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    output: JsonValue
    finish_reason: str | None = None
    usage: dict[str, JsonValue] | None = None
    latency_ms: float | None = Field(default=None, ge=0)


class ToolDefinitionPayload(StrictPayloadModel):
    name: str = Field(min_length=1)
    description: str | None = None
    input_schema: JsonValue | None = None


class ToolCallPayload(StrictPayloadModel):
    name: str = Field(min_length=1)
    call_id: str = Field(min_length=1)
    arguments: JsonValue


class ToolResultPayload(StrictPayloadModel):
    name: str = Field(min_length=1)
    call_id: str = Field(min_length=1)
    status: ToolResultStatus
    result: JsonValue | None = None
    error: JsonValue | None = None
    latency_ms: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def require_failure_evidence(self) -> ToolResultPayload:
        if self.status == ToolResultStatus.FAILURE and self.error is None:
            raise ValueError("failed tool results require explicit error data")
        return self


class ExceptionPayload(StrictPayloadModel):
    exception_type: str = Field(min_length=1)
    message: str
    traceback: str | None = None
    handled: bool


class RetryPayload(StrictPayloadModel):
    attempt: int = Field(ge=1)
    reason: str | None = None
    delay_ms: float | None = Field(default=None, ge=0)
    target: str | None = None
