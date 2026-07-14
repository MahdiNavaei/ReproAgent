"""Deterministic layered comparison utilities for captured agent data."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from math import isclose
from typing import Any

JsonValue = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]


class DiffMode(StrEnum):
    """Supported deterministic comparison modes."""

    EXACT = "exact"
    STRUCTURAL = "structural"
    NORMALIZED = "normalized"


@dataclass(frozen=True, slots=True)
class Difference:
    """One deterministic difference between two values."""

    path: str
    kind: str
    expected: JsonValue
    actual: JsonValue


@dataclass(frozen=True, slots=True)
class DiffResult:
    """Complete result for a comparison."""

    mode: DiffMode
    equal: bool
    differences: tuple[Difference, ...]


def compare(
    expected: JsonValue,
    actual: JsonValue,
    *,
    mode: DiffMode = DiffMode.EXACT,
    ignored_keys: frozenset[str] = frozenset(),
    float_tolerance: float = 1e-9,
) -> DiffResult:
    """Compare JSON-compatible values without executing code or using semantic models.

    ``exact`` compares values and sequence order.
    ``structural`` compares container shape and scalar types while ignoring scalar values.
    ``normalized`` ignores mapping key order, trims string edge whitespace, normalizes CRLF/CR
    to LF, and compares finite floats using ``float_tolerance``.
    """

    if float_tolerance < 0:
        raise ValueError("float_tolerance must be non-negative")

    differences: list[Difference] = []
    _compare_value(
        expected,
        actual,
        path="$",
        mode=mode,
        ignored_keys=ignored_keys,
        float_tolerance=float_tolerance,
        differences=differences,
    )
    return DiffResult(mode=mode, equal=not differences, differences=tuple(differences))


def _compare_value(
    expected: JsonValue,
    actual: JsonValue,
    *,
    path: str,
    mode: DiffMode,
    ignored_keys: frozenset[str],
    float_tolerance: float,
    differences: list[Difference],
) -> None:
    if _is_mapping(expected) and _is_mapping(actual):
        _compare_mapping(
            expected,
            actual,
            path=path,
            mode=mode,
            ignored_keys=ignored_keys,
            float_tolerance=float_tolerance,
            differences=differences,
        )
        return

    if _is_sequence(expected) and _is_sequence(actual):
        _compare_sequence(
            expected,
            actual,
            path=path,
            mode=mode,
            ignored_keys=ignored_keys,
            float_tolerance=float_tolerance,
            differences=differences,
        )
        return

    if type(expected) is not type(actual):
        differences.append(Difference(path, "type_mismatch", expected, actual))
        return

    if mode is DiffMode.STRUCTURAL:
        return

    if mode is DiffMode.NORMALIZED and _normalized_equal(
        expected, actual, float_tolerance=float_tolerance
    ):
        return

    if expected != actual:
        differences.append(Difference(path, "value_mismatch", expected, actual))


def _compare_mapping(
    expected: Mapping[str, JsonValue],
    actual: Mapping[str, JsonValue],
    *,
    path: str,
    mode: DiffMode,
    ignored_keys: frozenset[str],
    float_tolerance: float,
    differences: list[Difference],
) -> None:
    expected_keys = set(expected).difference(ignored_keys)
    actual_keys = set(actual).difference(ignored_keys)

    for key in sorted(expected_keys - actual_keys):
        differences.append(Difference(_key_path(path, key), "missing_key", expected[key], None))
    for key in sorted(actual_keys - expected_keys):
        differences.append(Difference(_key_path(path, key), "unexpected_key", None, actual[key]))
    for key in sorted(expected_keys & actual_keys):
        _compare_value(
            expected[key],
            actual[key],
            path=_key_path(path, key),
            mode=mode,
            ignored_keys=ignored_keys,
            float_tolerance=float_tolerance,
            differences=differences,
        )


def _compare_sequence(
    expected: Sequence[JsonValue],
    actual: Sequence[JsonValue],
    *,
    path: str,
    mode: DiffMode,
    ignored_keys: frozenset[str],
    float_tolerance: float,
    differences: list[Difference],
) -> None:
    if len(expected) != len(actual):
        differences.append(
            Difference(path, "length_mismatch", len(expected), len(actual))
        )

    for index, (expected_item, actual_item) in enumerate(zip(expected, actual, strict=False)):
        _compare_value(
            expected_item,
            actual_item,
            path=f"{path}[{index}]",
            mode=mode,
            ignored_keys=ignored_keys,
            float_tolerance=float_tolerance,
            differences=differences,
        )


def _normalized_equal(
    expected: JsonValue, actual: JsonValue, *, float_tolerance: float
) -> bool:
    if isinstance(expected, str) and isinstance(actual, str):
        return _normalize_string(expected) == _normalize_string(actual)
    if isinstance(expected, float) and isinstance(actual, float):
        return isclose(expected, actual, rel_tol=float_tolerance, abs_tol=float_tolerance)
    return expected == actual


def _normalize_string(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n").strip()


def _key_path(path: str, key: str) -> str:
    return f"{path}.{key}" if key.isidentifier() else f"{path}[{key!r}]"


def _is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


__all__ = ["DiffMode", "DiffResult", "Difference", "JsonValue", "compare"]
