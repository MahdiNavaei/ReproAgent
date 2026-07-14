"""Safe, deterministic serialization for the data-only AgentCase v0 format."""

from __future__ import annotations

import json
import os
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from reproagent.agentcase.errors import (
    AgentCaseFileExistsError,
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
    """Write a canonical AgentCase file without atomic replacement guarantees."""

    Path(path).write_text(dumps_agentcase(case), encoding="utf-8", newline="\n")


def atomic_dump_agentcase(
    case: AgentCase,
    path: str | Path,
    *,
    overwrite: bool = False,
    create_parents: bool = False,
) -> None:
    """Publish a validated case atomically on ordinary local filesystems.

    The complete serialized bytes are written and fsynced to a temporary file in the
    destination directory before the target path is created or replaced. With the safe
    default ``overwrite=False``, an existing target is never replaced silently.
    """

    target = Path(path)
    parent = target.parent
    if create_parents:
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise AgentCaseSerializationError(
                f"unable to create AgentCase parent directory: {exc}"
            ) from exc
    elif not parent.exists():
        raise AgentCaseSerializationError(f"AgentCase parent directory does not exist: {parent}")

    data = dumps_agentcase(case).encode("utf-8")
    temp_path: Path | None = None
    try:
        temp_path = _write_temp_file(parent, target.name, data)
        if overwrite:
            os.replace(temp_path, target)
            temp_path = None
        else:
            try:
                os.link(temp_path, target)
            except FileExistsError as exc:
                raise AgentCaseFileExistsError(
                    f"AgentCase output already exists: {target}"
                ) from exc
            except OSError as exc:
                raise AgentCaseSerializationError(
                    f"unable to publish AgentCase without overwriting: {exc}"
                ) from exc
            temp_path.unlink()
            temp_path = None
        _fsync_directory(parent)
    finally:
        if temp_path is not None:
            with suppress(OSError):
                temp_path.unlink(missing_ok=True)


def _write_temp_file(parent: Path, target_name: str, data: bytes) -> Path:
    fd, raw_path = tempfile.mkstemp(
        prefix=f".{target_name}.",
        suffix=".tmp",
        dir=parent,
    )
    temp_path = Path(raw_path)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    return temp_path


def _fsync_directory(directory: Path) -> None:
    if os.name == "nt":
        return
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


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
