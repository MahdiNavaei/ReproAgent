from pathlib import Path

import pytest

from reproagent.agentcase import (
    AgentCaseFileTooLargeError,
    AgentCaseSerializationError,
    UnsupportedAgentCaseVersionError,
    dumps_agentcase,
    load_agentcase,
    loads_agentcase,
)

FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_round_trip_is_deterministic() -> None:
    original = load_agentcase(FIXTURES / "valid_minimal.agentcase")
    first = dumps_agentcase(original)
    loaded = loads_agentcase(first)
    second = dumps_agentcase(loaded)

    assert loaded == original
    assert first == second


def test_unsupported_version_fails_clearly() -> None:
    with pytest.raises(UnsupportedAgentCaseVersionError, match="unsupported AgentCase format"):
        load_agentcase(FIXTURES / "invalid_unsupported_version.agentcase")


def test_malformed_json_fails_safely() -> None:
    with pytest.raises(AgentCaseSerializationError, match="malformed AgentCase JSON"):
        load_agentcase(FIXTURES / "invalid_malformed.agentcase")


def test_root_must_be_object() -> None:
    with pytest.raises(AgentCaseSerializationError, match="root value must be a JSON object"):
        loads_agentcase("[]")


def test_size_limit_is_checked_before_parsing() -> None:
    with pytest.raises(AgentCaseFileTooLargeError):
        loads_agentcase(b"{}" * 20, max_bytes=8)
