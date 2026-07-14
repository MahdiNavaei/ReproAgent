"""ReproAgent public package surface."""

from reproagent._version import __version__
from reproagent.diff import Difference, DiffMode, DiffResult, compare
from reproagent.domain import (
    AgentCase,
    AgentCaseMetadata,
    CaptureCompleteness,
    CaptureStatus,
    Event,
    EventType,
    ExecutionOutcome,
    RedactionMetadata,
    RedactionStatus,
)

__all__ = [
    "AgentCase",
    "AgentCaseMetadata",
    "CaptureCompleteness",
    "CaptureStatus",
    "DiffMode",
    "DiffResult",
    "Difference",
    "Event",
    "EventType",
    "ExecutionOutcome",
    "RedactionMetadata",
    "RedactionStatus",
    "__version__",
    "compare",
]
