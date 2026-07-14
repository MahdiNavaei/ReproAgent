"""Replay-specific errors with fail-closed semantics."""


class ReplayError(Exception):
    """Base class for replay failures."""


class ReplaySafetyError(ReplayError):
    """Raised when a replay request would violate the safety model."""


class ReplayContractError(ReplayError):
    """Raised when a source AgentCase is not replayable under the selected mode."""
