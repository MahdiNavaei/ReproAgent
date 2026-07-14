from pathlib import Path

import pytest

from reproagent.agentcase import AgentCaseFileTooLargeError, load_agentcase, loads_agentcase
from reproagent.domain import RedactionMetadata, RedactionRecord, RedactionStatus

FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_loader_treats_python_like_payload_as_data(tmp_path: Path) -> None:
    marker = tmp_path / "should-not-exist"
    payload = (
        (FIXTURES / "valid_minimal.agentcase")
        .read_text(encoding="utf-8")
        .replace(
            "fictional_agent.run",
            f"__import__('pathlib').Path('{marker}').write_text('executed')",
        )
    )

    case = loads_agentcase(payload)

    assert case.events[0].payload["entrypoint"]
    assert not marker.exists()


def test_pathological_oversized_input_is_rejected_before_json_parse() -> None:
    data = b"[" + (b"0," * 10_000) + b"0]"
    with pytest.raises(AgentCaseFileTooLargeError):
        loads_agentcase(data, max_bytes=128)


def test_redaction_metadata_contains_no_original_secret_field() -> None:
    record = RedactionRecord(
        field_path="/headers/authorization",
        rule_id="test.authorization",
        replacement_marker="[REDACTED:token]",
    )
    metadata = RedactionMetadata(status=RedactionStatus.REDACTED, records=(record,))
    dumped = metadata.model_dump(mode="json")

    assert "original" not in dumped["records"][0]
    assert "secret" not in dumped["records"][0]


def test_file_size_limit_applies_to_file_loading(tmp_path: Path) -> None:
    oversized = tmp_path / "oversized.agentcase"
    oversized.write_bytes(b"x" * 1024)
    with pytest.raises(AgentCaseFileTooLargeError):
        load_agentcase(oversized, max_bytes=16)
