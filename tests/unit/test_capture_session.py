from pathlib import Path

import pytest

from reproagent.agentcase import load_agentcase
from reproagent.capture import (
    CaptureLifecycleError,
    CapturePersistenceError,
    CaptureSessionState,
    capture,
    get_current_session,
)
from reproagent.domain import CaptureCompleteness, EventType, ExecutionOutcome


class SyntheticApplicationError(RuntimeError):
    pass


def test_normal_context_capture_persists_success_case(tmp_path: Path) -> None:
    output = tmp_path / "run.agentcase"

    with capture(output=output, name="example-agent") as session:
        session.message(role="user", content="hello")

    case = load_agentcase(output)
    assert case.outcome == ExecutionOutcome.SUCCESS
    assert case.completeness == CaptureCompleteness.COMPLETE
    assert [event.event_type for event in case.events] == [
        EventType.EXECUTION_START,
        EventType.MESSAGE,
        EventType.EXECUTION_END,
    ]
    assert case.events[-1].payload["outcome"] == case.outcome.value


def test_events_cannot_be_recorded_before_activation() -> None:
    session = capture(name="inactive")
    with pytest.raises(CaptureLifecycleError, match="only be recorded while capture is active"):
        session.message(role="user", content="nope")


def test_recording_after_finalization_fails_and_finalize_is_idempotent() -> None:
    session = capture(name="finalize-test")
    with session:
        first = session.finalize()
        second = session.finalize()
        assert first is second
        assert session.state == CaptureSessionState.CLOSED
        with pytest.raises(CaptureLifecycleError, match="state=closed"):
            session.message(role="user", content="too late")


def test_finalize_before_activation_fails() -> None:
    with pytest.raises(CaptureLifecycleError, match="before activation"):
        capture().finalize()


def test_application_exception_is_captured_persisted_and_reraised(tmp_path: Path) -> None:
    output = tmp_path / "failure.agentcase"

    with (
        pytest.raises(SyntheticApplicationError, match="synthetic boom"),
        capture(output=output, name="failure-example"),
    ):
        raise SyntheticApplicationError("synthetic boom")

    case = load_agentcase(output)
    assert case.outcome == ExecutionOutcome.FAILURE
    assert case.completeness == CaptureCompleteness.COMPLETE
    assert [event.event_type for event in case.events].count(EventType.EXCEPTION) == 1
    assert case.events[-1].event_type == EventType.EXECUTION_END
    assert case.events[-1].payload["outcome"] == "failure"


def test_logical_failure_without_python_exception_is_preserved(tmp_path: Path) -> None:
    output = tmp_path / "logical-failure.agentcase"

    with capture(output=output) as session:
        session.set_outcome(
            ExecutionOutcome.FAILURE,
            reason="agent returned an invalid business decision",
        )

    case = load_agentcase(output)
    assert case.outcome == ExecutionOutcome.FAILURE
    assert case.events[-1].payload["reason"] == "agent returned an invalid business decision"


def test_explicit_completeness_is_independent_from_outcome(tmp_path: Path) -> None:
    output = tmp_path / "degraded-success.agentcase"

    with capture(output=output) as session:
        session.set_completeness(
            CaptureCompleteness.DEGRADED,
            reason="optional observation unavailable",
        )

    case = load_agentcase(output)
    assert case.outcome == ExecutionOutcome.SUCCESS
    assert case.completeness == CaptureCompleteness.DEGRADED


def test_existing_output_is_not_overwritten_by_default(tmp_path: Path) -> None:
    output = tmp_path / "existing.agentcase"
    output.write_text("do-not-overwrite", encoding="utf-8")

    with pytest.raises(CapturePersistenceError), capture(output=output):
        pass

    assert output.read_text(encoding="utf-8") == "do-not-overwrite"


def test_overwrite_must_be_explicit(tmp_path: Path) -> None:
    output = tmp_path / "existing.agentcase"
    output.write_text("old", encoding="utf-8")

    with capture(output=output, overwrite=True):
        pass

    assert load_agentcase(output).outcome == ExecutionOutcome.SUCCESS


def test_missing_parent_directories_are_created_for_capture_output(tmp_path: Path) -> None:
    output = tmp_path / "nested" / "runs" / "case.agentcase"
    with capture(output=output):
        pass
    assert output.exists()
    load_agentcase(output)


def test_capture_persistence_failure_does_not_replace_application_exception(
    tmp_path: Path,
) -> None:
    output = tmp_path / "existing.agentcase"
    output.write_text("occupied", encoding="utf-8")

    with pytest.raises(SyntheticApplicationError) as exc_info, capture(output=output):
        raise SyntheticApplicationError("primary failure")

    assert str(exc_info.value) == "primary failure"
    assert any("ReproAgent capture also failed" in note for note in exc_info.value.__notes__)


def test_unexpected_exception_capture_fault_cannot_mask_original_exception() -> None:
    expected = SyntheticApplicationError("primary failure")

    with pytest.raises(SyntheticApplicationError) as raised:
        with capture() as session:
            def broken_exception(*_: object, **__: object) -> None:
                raise KeyboardInterrupt("capture fault")

            session.exception = broken_exception  # type: ignore[method-assign]
            raise expected

    assert raised.value is expected
    assert get_current_session() is None
    assert any("ReproAgent capture also failed" in note for note in expected.__notes__)


def test_unexpected_finalize_fault_cannot_mask_original_exception() -> None:
    expected = SyntheticApplicationError("primary failure")

    with pytest.raises(SyntheticApplicationError) as raised:
        with capture() as session:
            def broken_finalize() -> None:
                raise SystemExit("capture fault")

            session.finalize = broken_finalize  # type: ignore[method-assign]
            raise expected

    assert raised.value is expected
    assert get_current_session() is None
