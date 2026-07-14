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
from reproagent.regression import (
    DEFAULT_VOLATILE_KEYS,
    RegressionResult,
    assert_agentcase_regression,
    compare_agentcases,
)

__all__ = [
    "AgentCase",
    "AgentCaseMetadata",
    "CaptureCompleteness",
    "CaptureStatus",
    "DEFAULT_VOLATILE_KEYS",
    "DiffMode",
    "DiffResult",
    "Difference",
    "Event",
    "EventType",
    "ExecutionOutcome",
    "RedactionMetadata",
    "RedactionStatus",
    "RegressionResult",
    "__version__",
    "assert_agentcase_regression",
    "compare",
    "compare_agentcases",
]
