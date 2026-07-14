from pathlib import Path

import pytest

from reproagent.agentcase import (
    AgentCaseFileExistsError,
    atomic_dump_agentcase,
    load_agentcase,
)
from reproagent.domain import AgentCase, CaptureCompleteness, ExecutionOutcome


def _minimal_case() -> AgentCase:
    return AgentCase(
        events=(),
        outcome=ExecutionOutcome.SUCCESS,
        completeness=CaptureCompleteness.COMPLETE,
    )


def test_atomic_dump_writes_valid_final_output(tmp_path: Path) -> None:
    output = tmp_path / "case.agentcase"
    atomic_dump_agentcase(_minimal_case(), output)
    assert load_agentcase(output).outcome == ExecutionOutcome.SUCCESS
    assert not list(tmp_path.glob("*.tmp"))


def test_atomic_dump_refuses_existing_target_without_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "case.agentcase"
    output.write_text("existing", encoding="utf-8")
    with pytest.raises(AgentCaseFileExistsError):
        atomic_dump_agentcase(_minimal_case(), output)
    assert output.read_text(encoding="utf-8") == "existing"


def test_failed_publish_does_not_leave_normal_looking_partial_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import reproagent.agentcase.io as io_module

    output = tmp_path / "case.agentcase"

    def fail_link(source: object, target: object) -> None:
        raise OSError("synthetic publish failure")

    monkeypatch.setattr(io_module.os, "link", fail_link)
    with pytest.raises(Exception, match="unable to publish AgentCase"):
        atomic_dump_agentcase(_minimal_case(), output)

    assert not output.exists()
    assert not list(tmp_path.glob("*.tmp"))
