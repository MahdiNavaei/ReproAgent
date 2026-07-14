"""Contract tests for deterministic AgentCase regression checks."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest

from reproagent.agentcase import load_agentcase
from reproagent.diff import DiffMode
from reproagent.domain import AgentCase, ExecutionOutcome
from reproagent.pytest_plugin import RegressionAssertion
from reproagent.regression import assert_agentcase_regression, compare_agentcases

FIXTURE = Path(__file__).parent / "fixtures" / "valid_minimal.agentcase"


def _baseline() -> AgentCase:
    return load_agentcase(FIXTURE)


def test_regression_ignores_volatile_identity_fields() -> None:
    baseline = _baseline()
    observed = baseline.model_copy(
        update={
            "case_id": UUID("33333333-3333-4333-8333-333333333333"),
            "execution_id": UUID("44444444-4444-4444-8444-444444444444"),
        }
    )

    result = compare_agentcases(baseline, observed)

    assert result.passed
    assert result.diff.equal


def test_regression_reports_stable_payload_path() -> None:
    baseline = _baseline()
    changed_event = baseline.events[4].model_copy(
        update={"payload": {**baseline.events[4].payload, "status": "success"}}
    )
    observed = baseline.model_copy(
        update={"events": (*baseline.events[:4], changed_event, *baseline.events[5:])}
    )

    result = compare_agentcases(baseline, observed)

    assert not result.passed
    assert result.diff.differences[0].path == "$.events[4].payload.status"


def test_regression_can_use_structural_mode() -> None:
    baseline = _baseline()
    observed = baseline.model_copy(update={"outcome": ExecutionOutcome.SUCCESS})

    result = compare_agentcases(baseline, observed, mode=DiffMode.STRUCTURAL)

    assert result.passed


def test_regression_assertion_has_actionable_difference_path() -> None:
    baseline = _baseline()
    observed = baseline.model_copy(update={"outcome": ExecutionOutcome.SUCCESS})

    with pytest.raises(AssertionError, match=r"\$\.outcome: value_mismatch"):
        assert_agentcase_regression(baseline, observed)


def test_pytest_fixture_asserts_regression(agentcase_regression: RegressionAssertion) -> None:
    baseline = _baseline()
    agentcase_regression(baseline, baseline)
