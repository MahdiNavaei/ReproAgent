from pathlib import Path

import pytest

from reproagent.agentcase import AgentCaseError, dumps_agentcase, load_agentcase

FIXTURES = Path(__file__).parents[1] / "fixtures"
EXAMPLE = Path(__file__).parents[2] / "examples" / "cases" / "minimal_failure.agentcase"


def test_known_valid_fixture_and_example_are_semantically_identical() -> None:
    fixture = load_agentcase(FIXTURES / "valid_minimal.agentcase")
    example = load_agentcase(EXAMPLE)
    assert fixture == example
    assert dumps_agentcase(fixture) == EXAMPLE.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "filename",
    [
        "invalid_duplicate_event_id.agentcase",
        "invalid_parent_reference.agentcase",
        "invalid_sequence.agentcase",
        "invalid_malformed.agentcase",
        "invalid_unsupported_version.agentcase",
    ],
)
def test_known_invalid_fixtures_are_rejected(filename: str) -> None:
    with pytest.raises(AgentCaseError):
        load_agentcase(FIXTURES / filename)
