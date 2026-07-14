"""Safe, deterministic serialization for the data-only AgentCase v0 format."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from reproagent.agentcase.errors import (
    AgentCaseFileTooLargeError,
    AgentCaseSerializationError,
    UnsupportedAgentCaseVersionError,
)
from reproagent.domain import (
    AGENTCASE_FORMAT_NAME,
    SUPPORTED_AGENTCASE_FORMAT_VERSIONS,
    AgentCase,
)

DEFAULT_MAX_AGENTCASE_BYTES = 16 * 1024 * 1024


def dumps_agentcase(case: AgentCase) -> str:
    """Serialize a case into canonical UTF-8 JSON text with deterministic key ordering."""

    payload = case.model_dump(mode="json")
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    )


def dump_agentcase(case: AgentCase, path: str | Path) -> None:
    """Write a canonical AgentCase file."""

    Path(path).write_text(dumps_agentcase(case), encoding="utf-8", newline="\n")


def loads_agentcase(
    data: str | bytes, *, max_bytes: int = DEFAULT_MAX_AGENTCASE_BYTES
) -> AgentCase:
    """Load and validate AgentCase JSON without executable object deserialization."""

    raw_bytes = data.encode("utf-8") if isinstance(data, str) else data
    if len(raw_bytes) > max_bytes:
        raise AgentCaseFileTooLargeError(
            f"AgentCase is {len(raw_bytes)} bytes; maximum allowed is {max_bytes} bytes"
        )

    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AgentCaseSerializationError("AgentCase must be valid UTF-8") from exc

    try:
        payload: Any = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AgentCaseSerializationError(f"malformed AgentCase JSON: {exc.msg}") from exc

    if not isinstance(payload, dict):
        raise AgentCaseSerializationError("AgentCase root value must be a JSON object")

    _validate_format_header(payload)

    try:
        return AgentCase.model_validate(payload)
    except ValidationError as exc:
        raise AgentCaseSerializationError(f"invalid AgentCase data: {exc}") from exc


def load_agentcase(
    path: str | Path,
    *,
    max_bytes: int = DEFAULT_MAX_AGENTCASE_BYTES,
) -> AgentCase:
    """Read and validate an AgentCase file with a bounded input size."""

    file_path = Path(path)
    try:
        file_size = file_path.stat().st_size
    except OSError as exc:
        raise AgentCaseSerializationError(f"unable to read AgentCase: {exc}") from exc

    if file_size > max_bytes:
        raise AgentCaseFileTooLargeError(
            f"AgentCase is {file_size} bytes; maximum allowed is {max_bytes} bytes"
        )

    try:
        data = file_path.read_bytes()
    except OSError as exc:
        raise AgentCaseSerializationError(f"unable to read AgentCase: {exc}") from exc
    return loads_agentcase(data, max_bytes=max_bytes)


def _validate_format_header(payload: dict[str, Any]) -> None:
    format_name = payload.get("format_name")
    if format_name != AGENTCASE_FORMAT_NAME:
        raise AgentCaseSerializationError(
            f"unsupported or missing format_name: expected {AGENTCASE_FORMAT_NAME!r}"
        )

    version = payload.get("format_version")
    if not isinstance(version, str):
        raise UnsupportedAgentCaseVersionError("missing or invalid AgentCase format_version")
    if version not in SUPPORTED_AGENTCASE_FORMAT_VERSIONS:
        supported = ", ".join(sorted(SUPPORTED_AGENTCASE_FORMAT_VERSIONS))
        raise UnsupportedAgentCaseVersionError(
            f"unsupported AgentCase format version {version!r}; supported: {supported}"
        )
