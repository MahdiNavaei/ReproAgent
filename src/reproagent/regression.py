"""Deterministic AgentCase regression comparison and assertion helpers."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from reproagent.diff import DiffMode, DiffResult, JsonValue, compare
from reproagent.domain import AgentCase

# Recursive name-only ignores are intentionally not the default: a business payload
# field named ``timestamp`` or ``event_id`` is real captured data and must still diff.
DEFAULT_VOLATILE_KEYS: frozenset[str] = frozenset()
_ROOT_VOLATILE_FIELDS = frozenset({"case_id", "execution_id", "created_at", "replay"})
_EVENT_VOLATILE_FIELDS = frozenset({"event_id", "parent_event_id", "timestamp"})


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
    """Compare AgentCases after removing only known volatile schema locations."""

    baseline_data = _normalize_agentcase_volatility(baseline.model_dump(mode="json"))
    observed_data = _normalize_agentcase_volatility(observed.model_dump(mode="json"))
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


def _normalize_agentcase_volatility(value: object) -> object:
    if not isinstance(value, dict):
        raise TypeError("AgentCase JSON projection must be an object")

    normalized = deepcopy(value)
    for key in _ROOT_VOLATILE_FIELDS:
        normalized.pop(key, None)

    events = normalized.get("events")
    if isinstance(events, list):
        for event in events:
            if not isinstance(event, dict):
                continue
            for key in _EVENT_VOLATILE_FIELDS:
                event.pop(key, None)

    return normalized


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
