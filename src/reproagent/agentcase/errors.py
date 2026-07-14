"""Public exceptions for AgentCase loading and validation."""


class AgentCaseError(ValueError):
    """Base exception for AgentCase data errors."""


class AgentCaseFileTooLargeError(AgentCaseError):
    """Raised before parsing when an AgentCase exceeds the configured size limit."""


class AgentCaseSerializationError(AgentCaseError):
    """Raised when AgentCase bytes are not valid supported JSON data."""


class UnsupportedAgentCaseVersionError(AgentCaseError):
    """Raised when the file format version is not supported by this reader."""
