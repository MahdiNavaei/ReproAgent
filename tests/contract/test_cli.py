from pathlib import Path

from reproagent.cli.main import main

FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_version_command(capsys: object) -> None:
    import pytest

    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0


def test_validate_valid_case_returns_zero(capsys: object) -> None:
    result = main(["validate", str(FIXTURES / "valid_minimal.agentcase")])
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert result == 0
    assert "valid AgentCase" in captured.out


def test_validate_invalid_case_returns_nonzero(capsys: object) -> None:
    result = main(["validate", str(FIXTURES / "invalid_sequence.agentcase")])
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert result == 2
    assert "error:" in captured.err


def test_inspect_valid_case_returns_summary(capsys: object) -> None:
    result = main(["inspect", str(FIXTURES / "valid_minimal.agentcase")])
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert result == 0
    assert "Outcome: failure" in captured.out
    assert "Event count: 7" in captured.out
