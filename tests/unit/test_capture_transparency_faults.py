from __future__ import annotations

import pytest

from reproagent.capture import capture


class PrimaryApplicationError(RuntimeError):
    pass


def test_unexpected_exception_capture_failure_cannot_mask_original(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = capture()
    original = PrimaryApplicationError("primary")

    with pytest.raises(PrimaryApplicationError) as raised:
        with session:
            def fail_capture(*args: object, **kwargs: object) -> None:
                raise KeyboardInterrupt("capture fault")

            monkeypatch.setattr(session, "exception", fail_capture)
            raise original

    assert raised.value is original
    assert any("KeyboardInterrupt" in note for note in original.__notes__)


def test_unexpected_outcome_capture_failure_cannot_mask_original(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = capture()
    original = PrimaryApplicationError("primary")

    with pytest.raises(PrimaryApplicationError) as raised:
        with session:
            def fail_outcome(*args: object, **kwargs: object) -> None:
                raise SystemExit("capture outcome fault")

            monkeypatch.setattr(session._builder, "set_outcome", fail_outcome)
            raise original

    assert raised.value is original
    assert any("SystemExit" in note for note in original.__notes__)
