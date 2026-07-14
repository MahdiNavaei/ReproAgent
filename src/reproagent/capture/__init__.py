"""Public framework-neutral manual Capture Engine API."""

from reproagent.capture.context import get_current_session
from reproagent.capture.errors import (
    CaptureError,
    CaptureLifecycleError,
    CaptureNormalizationError,
    CapturePersistenceError,
    CaptureRedactionError,
    NestedCaptureSessionError,
)
from reproagent.capture.payloads import ToolResultStatus
from reproagent.capture.session import CaptureSession, CaptureSessionState, capture
from reproagent.capture.tools import capture_tool

__all__ = [
    "CaptureError",
    "CaptureLifecycleError",
    "CaptureNormalizationError",
    "CapturePersistenceError",
    "CaptureRedactionError",
    "CaptureSession",
    "CaptureSessionState",
    "NestedCaptureSessionError",
    "ToolResultStatus",
    "capture",
    "capture_tool",
    "get_current_session",
]
