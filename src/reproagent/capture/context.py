"""Context-local active capture session handling."""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from reproagent.capture.session import CaptureSession

_CURRENT_SESSION: ContextVar[CaptureSession | None] = ContextVar(
    "reproagent_current_capture_session",
    default=None,
)


def get_current_session() -> CaptureSession | None:
    """Return the active session for this context, or ``None`` when absent."""

    return _CURRENT_SESSION.get()


def set_current_session(session: CaptureSession) -> Token[CaptureSession | None]:
    return _CURRENT_SESSION.set(session)


def reset_current_session(token: Token[CaptureSession | None]) -> None:
    _CURRENT_SESSION.reset(token)
