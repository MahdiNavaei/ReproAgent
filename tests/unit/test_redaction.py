import json
from pathlib import Path

import pytest

from reproagent.agentcase import load_agentcase
from reproagent.capture import CaptureRedactionError, capture
from reproagent.domain import CaptureCompleteness, ExecutionOutcome, RedactionStatus
from reproagent.security import Redactor, RegexRedactionRule


class FailOnTriggerRule:
    rule_id = "test.fail-on-trigger"
    replacement_marker = "[REDACTED:test]"

    def apply(self, value: str) -> tuple[str, bool]:
        if "TRIGGER_REDACTION_FAILURE" in value:
            raise RuntimeError("synthetic redaction failure")
        return value, False


def test_recursive_sensitive_key_redaction_does_not_mutate_input() -> None:
    original = {
        "Authorization": "Bearer synthetic-token-123456789",
        "nested": [
            {"api_key": "sk-synthetic123456789012345"},
            {"safe": "visible"},
        ],
    }
    snapshot = json.loads(json.dumps(original))

    result = Redactor().redact(original, base_pointer="/payload")

    assert original == snapshot
    assert result.value != original
    assert isinstance(result.value, dict)
    assert result.value["Authorization"] == "[REDACTED:sensitive-key]"
    assert result.value["nested"][0]["api_key"] == "[REDACTED:sensitive-key]"
    assert {hit.field_path for hit in result.hits} == {
        "/payload/Authorization",
        "/payload/nested/0/api_key",
    }


def test_bearer_and_high_confidence_key_patterns_are_redacted_inside_strings() -> None:
    secret = "sk-proj-abcdefghijklmnopqrstuvwxyz123456"
    value = f"Authorization: Bearer abcdefghijklmnop and key {secret}"
    result = Redactor().redact(value, base_pointer="/message")
    assert secret not in result.value
    assert "abcdefghijklmnop" not in result.value
    assert "[REDACTED:bearer-token]" in result.value
    assert "[REDACTED:api-key]" in result.value


def test_user_defined_rules_are_additive_to_defaults() -> None:
    redactor = Redactor(
        additional_rules=(
            RegexRedactionRule(
                rule_id="user.account-number",
                pattern=r"ACCT-\d{6}",
                replacement_marker="[REDACTED:account]",
            ),
        )
    )
    result = redactor.redact(
        {
            "password": "synthetic-password",
            "note": "Account ACCT-123456",
        }
    )
    assert result.value == {
        "password": "[REDACTED:sensitive-key]",
        "note": "Account [REDACTED:account]",
    }
    assert {hit.rule_id for hit in result.hits} == {
        "default.sensitive-key",
        "user.account-number",
    }


def test_capture_redacts_before_serialized_bytes_and_metadata_never_contains_secret(
    tmp_path: Path,
) -> None:
    output = tmp_path / "redacted.agentcase"
    secret = "sk-proj-syntheticsecret1234567890"

    with capture(
        output=output,
        user_metadata={"api_key": secret},
    ) as session:
        session.message(
            role="user",
            content={"headers": {"authorization": f"Bearer {secret}"}},
        )

    raw = output.read_text(encoding="utf-8")
    assert secret not in raw
    case = load_agentcase(output)
    assert case.redaction.status == RedactionStatus.REDACTED
    assert case.redaction.records
    assert all(secret not in record.model_dump_json() for record in case.redaction.records)
    assert any(record.field_path.startswith("/events/") for record in case.redaction.records)


def test_redaction_failure_drops_unsafe_event_and_marks_capture_partial(tmp_path: Path) -> None:
    output = tmp_path / "partial.agentcase"
    raw_secret = "TRIGGER_REDACTION_FAILURE: never-persist-this"
    redactor = Redactor(additional_rules=(FailOnTriggerRule(),))

    with capture(output=output, redactor=redactor) as session:
        with pytest.raises(CaptureRedactionError):
            session.message(role="user", content=raw_secret)
        session.message(role="user", content="safe follow-up")

    raw = output.read_text(encoding="utf-8")
    assert raw_secret not in raw
    case = load_agentcase(output)
    assert case.completeness == CaptureCompleteness.PARTIAL
    diagnostics = case.extensions["org.reproagent.capture/v1"]
    assert diagnostics["dropped_event_count"] == 1
    assert diagnostics["redaction_failures"]
    assert case.redaction.status == RedactionStatus.PARTIAL


def test_terminal_reason_redaction_failure_falls_back_to_safe_terminal_event(
    tmp_path: Path,
) -> None:
    output = tmp_path / "terminal-fallback.agentcase"
    redactor = Redactor(additional_rules=(FailOnTriggerRule(),))

    with capture(output=output, redactor=redactor) as session:
        session.set_outcome(
            ExecutionOutcome.FAILURE,
            reason="TRIGGER_REDACTION_FAILURE: terminal reason must not persist",
        )

    raw = output.read_text(encoding="utf-8")
    assert "terminal reason must not persist" not in raw
    case = load_agentcase(output)
    assert case.outcome.value == "failure"
    assert case.completeness == CaptureCompleteness.PARTIAL
    assert case.events[-1].payload["outcome"] == "failure"
    assert "reason" not in case.events[-1].payload
