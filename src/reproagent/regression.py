"""Deterministic AgentCase regression comparison and assertion helpers."""

from __future__ import annotations

from dataclasses import dataclass

from reproagent.diff import DiffMode, DiffResult, JsonValue, compare
from reproagent.domain import AgentCase

DEFAULT_VOLATILE_KEYS = frozenset(
    {
        "case_id",
        "execution_id",
        "created_at",
        "event_id",
        "parent_event_id",
        "timestamp",
        "replay",
    }
)


@dataclass(frozen=True, slots=True)
class RegressionResult:
    """Result of comparing an observed AgentCase with a recorded baseline."""

    passed: bool
    diff: DiffResult


def compare_agentcases(
    baseline: AgentCase,
    observed: AgentCase,
    *,
    mode: DiffMode = DiffMode.EXACT,
    ignored_keys: frozenset[str] = DEFAULT_VOLATILE_KEYS,
    float_tolerance: float = 1e-9,
) -> RegressionResult:
    """Compare two validated AgentCases as data, ignoring volatile identity fields by default."""

    baseline_data = baseline.model_dump(mode="json")
    observed_data = observed.model_dump(mode="json")
    diff = compare(
        _json_value(baseline_data),
        _json_value(observed_data),
        mode=mode,
        ignored_keys=ignored_keys,
        float_tolerance=float_tolerance,
    )
    return RegressionResult(passed=diff.equal, diff=diff)


def assert_agentcase_regression(
    baseline: AgentCase,
    observed: AgentCase,
    *,
    mode: DiffMode = DiffMode.EXACT,
    ignored_keys: frozenset[str] = DEFAULT_VOLATILE_KEYS,
    float_tolerance: float = 1e-9,
) -> None:
    """Raise ``AssertionError`` with stable difference paths when a regression is detected."""

    result = compare_agentcases(
        baseline,
        observed,
        mode=mode,
        ignored_keys=ignored_keys,
        float_tolerance=float_tolerance,
    )
    if result.passed:
        return

    details = "; ".join(
        f"{difference.path}: {difference.kind}" for difference in result.diff.differences
    )
    raise AssertionError(f"AgentCase regression detected ({mode.value}): {details}")


def _json_value(value: object) -> JsonValue:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    raise TypeError(f"AgentCase JSON projection contains unsupported value: {type(value).__name__}")


__all__ = [
    "DEFAULT_VOLATILE_KEYS",
    "RegressionResult",
    "assert_agentcase_regression",
    "compare_agentcases",
]
