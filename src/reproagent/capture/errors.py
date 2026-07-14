"""Explicit failures raised by the Capture Engine."""


class CaptureError(RuntimeError):
    """Base exception for Capture Engine failures."""


class CaptureLifecycleError(CaptureError):
    """Raised when a capture session lifecycle rule is violated."""


class NestedCaptureSessionError(CaptureLifecycleError):
    """Raised when a top-level capture session is nested inside another one."""


class CaptureNormalizationError(CaptureError):
    """Raised when user-observed data cannot be normalized into JSON-safe payload data."""


class CaptureRedactionError(CaptureError):
    """Raised when payload redaction fails and unsafe raw data is dropped."""


class CapturePersistenceError(CaptureError):
    """Raised when a finalized AgentCase cannot be persisted safely."""
