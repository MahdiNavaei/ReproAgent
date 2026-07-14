import ast
import socket
from pathlib import Path

import pytest

from reproagent.agentcase import load_agentcase
from reproagent.capture import CaptureNormalizationError, capture
from reproagent.domain import EventType


class ExceptionWithArbitraryObject(RuntimeError):
    def __init__(self) -> None:
        super().__init__("safe synthetic exception")
        self.arbitrary_object = object()


def test_source_does_not_introduce_pickle_eval_or_exec_loading_paths() -> None:
    source_root = Path(__file__).parents[2] / "src" / "reproagent"
    for path in source_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [alias.name for alias in node.names]
                assert "pickle" not in names
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {"eval", "exec"}


def test_capture_does_not_dump_process_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("REPROAGENT_SYNTHETIC_SECRET", "environment-secret-value")
    output = tmp_path / "env.agentcase"
    with capture(output=output):
        pass

    raw = output.read_text(encoding="utf-8")
    assert "REPROAGENT_SYNTHETIC_SECRET" not in raw
    assert "environment-secret-value" not in raw


def test_exception_capture_serializes_text_not_arbitrary_exception_objects(tmp_path: Path) -> None:
    output = tmp_path / "exception.agentcase"
    with pytest.raises(ExceptionWithArbitraryObject), capture(output=output):
        raise ExceptionWithArbitraryObject()

    raw = output.read_text(encoding="utf-8")
    assert "arbitrary_object" not in raw
    case = load_agentcase(output)
    event = next(event for event in case.events if event.event_type == EventType.EXCEPTION)
    assert event.payload["exception_type"] == "ExceptionWithArbitraryObject"


def test_capture_path_makes_no_network_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def blocked(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "create_connection", blocked)
    output = tmp_path / "offline.agentcase"
    with capture(output=output) as session:
        session.message(role="user", content="offline")
    load_agentcase(output)


def test_non_json_observation_is_dropped_and_never_serialized(tmp_path: Path) -> None:
    output = tmp_path / "non-json.agentcase"
    marker = "OBJECT_REPR_MUST_NOT_APPEAR"

    class NonJson:
        def __repr__(self) -> str:
            return marker

    with capture(output=output) as session, pytest.raises(CaptureNormalizationError):
        session.message(role="user", content=NonJson())  # type: ignore[arg-type]

    raw = output.read_text(encoding="utf-8")
    assert marker not in raw
    case = load_agentcase(output)
    diagnostics = case.extensions["org.reproagent.capture/v1"]
    assert diagnostics["normalization_failures"]


def test_synthetic_bearer_token_and_api_key_are_absent_from_serialized_output(
    tmp_path: Path,
) -> None:
    output = tmp_path / "secrets.agentcase"
    bearer = "Bearer abcdefghijklmnopqrstuvwxyz123456"
    api_key = "sk-proj-abcdefghijklmnopqrstuvwxyz123456"
    with capture(output=output) as session:
        session.message(
            role="user",
            content={"text": f"headers {bearer}", "api_key": api_key},
        )

    raw = output.read_text(encoding="utf-8")
    assert bearer not in raw
    assert api_key not in raw
