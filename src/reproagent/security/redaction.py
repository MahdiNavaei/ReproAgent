"""Framework-neutral, best-effort redaction before AgentCase persistence."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol, cast, runtime_checkable

from pydantic import JsonValue, TypeAdapter, ValidationError

_JSON_VALUE_ADAPTER: TypeAdapter[JsonValue] = TypeAdapter(JsonValue)

_SENSITIVE_KEYS = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "api-key",
        "x-api-key",
        "token",
        "access-token",
        "refresh-token",
        "password",
        "passwd",
        "secret",
        "client-secret",
        "cookie",
        "set-cookie",
        "connection-string",
    }
)


class RedactionError(RuntimeError):
    """Raised when redaction cannot safely produce a replacement value."""


@dataclass(frozen=True)
class RedactionHit:
    """A secret replacement record without the original secret value."""

    field_path: str
    rule_id: str
    replacement_marker: str


@dataclass(frozen=True)
class RedactionResult:
    """Redacted JSON-safe data and the rules that fired."""

    value: JsonValue
    hits: tuple[RedactionHit, ...]


@runtime_checkable
class StringRedactionRule(Protocol):
    """Extension point for rules that transform individual string values."""

    rule_id: str
    replacement_marker: str

    def apply(self, value: str) -> tuple[str, bool]:
        """Return the transformed value and whether the rule matched."""


@dataclass(frozen=True)
class RegexRedactionRule:
    """User-extensible regex rule applied in addition to ReproAgent defaults."""

    rule_id: str
    pattern: str
    replacement_marker: str = "[REDACTED:user-rule]"
    flags: int = 0

    def __post_init__(self) -> None:
        if not self.rule_id.strip():
            raise ValueError("rule_id must not be empty")
        if not self.replacement_marker:
            raise ValueError("replacement_marker must not be empty")
        re.compile(self.pattern, self.flags)

    def apply(self, value: str) -> tuple[str, bool]:
        transformed, count = re.subn(
            self.pattern,
            self.replacement_marker,
            value,
            flags=self.flags,
        )
        return transformed, count > 0


_DEFAULT_STRING_RULES = cast(
    tuple[StringRedactionRule, ...],
    (
        RegexRedactionRule(
            rule_id="default.bearer-token",
            pattern=r"(?i)\bBearer\s+[A-Za-z0-9._~+/=\-]{8,}",
            replacement_marker="[REDACTED:bearer-token]",
        ),
        RegexRedactionRule(
            rule_id="default.openai-style-key",
            pattern=r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b",
            replacement_marker="[REDACTED:api-key]",
        ),
    ),
)


class Redactor:
    """Recursively redact JSON-safe structures without mutating caller-owned data."""

    def __init__(
        self,
        *,
        additional_rules: tuple[StringRedactionRule, ...] = (),
    ) -> None:
        self._string_rules = (*_DEFAULT_STRING_RULES, *additional_rules)

    def redact(self, value: object, *, base_pointer: str = "") -> RedactionResult:
        try:
            json_value = _JSON_VALUE_ADAPTER.validate_python(value)
        except ValidationError as exc:
            raise RedactionError("value is not JSON-safe and cannot be redacted") from exc

        hits: list[RedactionHit] = []
        try:
            redacted = self._redact_value(json_value, base_pointer, hits)
        except RedactionError:
            raise
        except Exception as exc:
            raise RedactionError("a redaction rule failed") from exc
        return RedactionResult(value=redacted, hits=tuple(hits))

    def _redact_value(
        self,
        value: JsonValue,
        pointer: str,
        hits: list[RedactionHit],
    ) -> JsonValue:
        if isinstance(value, dict):
            redacted_dict: dict[str, JsonValue] = {}
            for key, item in value.items():
                child_pointer = _join_pointer(pointer, key)
                if _normalize_sensitive_key(key) in _SENSITIVE_KEYS:
                    marker = "[REDACTED:sensitive-key]"
                    redacted_dict[key] = marker
                    hits.append(
                        RedactionHit(
                            field_path=child_pointer,
                            rule_id="default.sensitive-key",
                            replacement_marker=marker,
                        )
                    )
                    continue
                redacted_dict[key] = self._redact_value(item, child_pointer, hits)
            return redacted_dict

        if isinstance(value, list):
            return [
                self._redact_value(item, _join_pointer(pointer, str(index)), hits)
                for index, item in enumerate(value)
            ]

        if isinstance(value, str):
            transformed = value
            for rule in self._string_rules:
                try:
                    transformed, matched = rule.apply(transformed)
                except Exception as exc:
                    raise RedactionError(f"redaction rule {rule.rule_id!r} failed") from exc
                if matched:
                    hits.append(
                        RedactionHit(
                            field_path=pointer or "/",
                            rule_id=rule.rule_id,
                            replacement_marker=rule.replacement_marker,
                        )
                    )
            return transformed

        return value


def _normalize_sensitive_key(key: str) -> str:
    return key.strip().casefold().replace("_", "-")


def _join_pointer(base: str, segment: str) -> str:
    escaped = segment.replace("~", "~0").replace("/", "~1")
    if not base:
        return f"/{escaped}"
    return f"{base}/{escaped}"
