"""Pytest integration for AgentCase regression assertions."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from reproagent.diff import DiffMode
from reproagent.domain import AgentCase
from reproagent.regression import assert_agentcase_regression

RegressionAssertion = Callable[[AgentCase, AgentCase], None]


@pytest.fixture
def agentcase_regression() -> RegressionAssertion:
    """Return an exact AgentCase regression assertion helper."""

    def assert_regression(baseline: AgentCase, observed: AgentCase) -> None:
        assert_agentcase_regression(baseline, observed, mode=DiffMode.EXACT)

    return assert_regression


__all__ = ["RegressionAssertion", "agentcase_regression"]
