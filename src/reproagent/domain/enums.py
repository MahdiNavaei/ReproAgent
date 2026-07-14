"""Stable enumerations used by the AgentCase v0 domain model."""

from enum import StrEnum


class ExecutionOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


class CaptureCompleteness(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    DEGRADED = "degraded"
    INTERRUPTED = "interrupted"
    UNSUPPORTED = "unsupported"


class EventType(StrEnum):
    EXECUTION_START = "execution.start"
    EXECUTION_END = "execution.end"
    MESSAGE = "message"
    MODEL_REQUEST = "model.request"
    MODEL_RESPONSE = "model.response"
    TOOL_DEFINITION = "tool.definition"
    TOOL_CALL = "tool.call"
    TOOL_RESULT = "tool.result"
    EXCEPTION = "exception"
    RETRY = "retry"
    CUSTOM = "custom"


class CaptureStatus(StrEnum):
    CAPTURED = "captured"
    PARTIAL = "partial"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"


class RedactionStatus(StrEnum):
    NONE = "none"
    REDACTED = "redacted"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class ReplayMode(StrEnum):
    MOCK = "mock"
    LIVE = "live"
    DIFFERENTIAL = "differential"


class DeterminismGuarantee(StrEnum):
    DETERMINISTIC = "deterministic"
    BEST_EFFORT = "best_effort"
    NONE = "none"
    UNKNOWN = "unknown"
