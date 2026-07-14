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
    DEFAULT_VOLATILE_PATHS,
    RegressionResult,
    assert_agentcase_regression,
    compare_agentcases,
)

__all__ = [
    "DEFAULT_VOLATILE_KEYS",
    "DEFAULT_VOLATILE_PATHS",
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
    "RegressionResult",
    "__version__",
    "assert_agentcase_regression",
    "compare",
    "compare_agentcases",
]
