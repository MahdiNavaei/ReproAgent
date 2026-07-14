"""Public CaptureSession wrapper with fail-safe context-manager teardown semantics."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import JsonValue

from reproagent.capture.context import reset_current_session
from reproagent.capture.session import CaptureSession as _BaseCaptureSession
from reproagent.capture.session import CaptureSessionState
from reproagent.domain import ExecutionOutcome
from reproagent.security import Redactor


class CaptureSession(_BaseCaptureSession):
    """Capture session whose instrumentation can never mask a propagating exception."""

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: Any,
    ) -> Literal[False]:
        capture_failure: BaseException | None = None

        if exc is not None:
            try:
                if self._state == CaptureSessionState.ACTIVE:
                    if id(exc) not in self._captured_exception_ids:
                        self.exception(exc, handled=False)
                    if self._builder.outcome in {
                        ExecutionOutcome.UNKNOWN,
                        ExecutionOutcome.SUCCESS,
                    }:
                        self._builder.set_outcome(ExecutionOutcome.FAILURE)
            except BaseException as capture_exc:
                capture_failure = capture_exc

        try:
            if self._state == CaptureSessionState.ACTIVE:
                self.finalize()
        except BaseException as finalize_exc:
            capture_failure = capture_failure or finalize_exc
        finally:
            if self._context_token is not None:
                token = self._context_token
                self._context_token = None
                try:
                    reset_current_session(token)
                except BaseException as reset_exc:
                    capture_failure = capture_failure or reset_exc

        if exc is not None:
            if capture_failure is not None:
                try:
                    exc.add_note(
                        "ReproAgent capture also failed while preserving the original application "
                        f"exception ({type(capture_failure).__name__})."
                    )
                except BaseException:
                    pass
            return False

        if capture_failure is not None:
            raise capture_failure
        return False


def capture(
    *,
    output: str | Path | None = None,
    name: str | None = None,
    entrypoint: str | None = None,
    user_metadata: dict[str, JsonValue] | None = None,
    overwrite: bool = False,
    redactor: Redactor | None = None,
) -> CaptureSession:
    """Create the public fail-safe CaptureSession context manager."""

    return CaptureSession(
        output=output,
        name=name,
        entrypoint=entrypoint,
        user_metadata=user_metadata,
        overwrite=overwrite,
        redactor=redactor,
    )
