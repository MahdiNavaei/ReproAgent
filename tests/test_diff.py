from __future__ import annotations

import pytest

from reproagent.diff import DiffMode, compare


def test_exact_reports_deterministic_nested_paths() -> None:
    result = compare(
        {"events": [{"type": "model.response", "payload": {"text": "hello"}}]},
        {"events": [{"type": "model.response", "payload": {"text": "world"}}]},
    )

    assert result.equal is False
    assert result.mode is DiffMode.EXACT
    assert [difference.path for difference in result.differences] == ["$.events[0].payload.text"]
    assert result.differences[0].kind == "value_mismatch"


def test_structural_ignores_scalar_values_but_not_types_or_shape() -> None:
    assert compare(
        {"count": 1, "message": "before"},
        {"count": 999, "message": "after"},
        mode=DiffMode.STRUCTURAL,
    ).equal

    type_result = compare({"count": 1}, {"count": "1"}, mode=DiffMode.STRUCTURAL)
    assert type_result.equal is False
    assert type_result.differences[0].kind == "type_mismatch"

    shape_result = compare([1], [1, 2], mode=DiffMode.STRUCTURAL)
    assert shape_result.equal is False
    assert shape_result.differences[0].kind == "length_mismatch"


def test_normalized_handles_line_endings_whitespace_and_float_tolerance() -> None:
    result = compare(
        {"text": "  hello\r\nworld  ", "score": 0.3000000001},
        {"score": 0.3, "text": "hello\nworld"},
        mode=DiffMode.NORMALIZED,
        float_tolerance=1e-8,
    )

    assert result.equal
    assert result.differences == ()


def test_ignored_keys_are_removed_recursively() -> None:
    result = compare(
        {"run_id": "a", "nested": {"run_id": "b", "value": 1}},
        {"run_id": "x", "nested": {"run_id": "y", "value": 1}},
        ignored_keys=frozenset({"run_id"}),
    )

    assert result.equal


def test_missing_and_unexpected_keys_are_sorted_for_stable_output() -> None:
    result = compare({"z": 1, "a": 2}, {"y": 3, "b": 4})

    assert [(item.path, item.kind) for item in result.differences] == [
        ("$.a", "missing_key"),
        ("$.z", "missing_key"),
        ("$.b", "unexpected_key"),
        ("$.y", "unexpected_key"),
    ]


def test_boolean_and_integer_are_not_treated_as_same_type() -> None:
    result = compare(True, 1)

    assert result.equal is False
    assert result.differences[0].kind == "type_mismatch"


def test_negative_float_tolerance_fails_closed() -> None:
    with pytest.raises(ValueError, match="float_tolerance must be non-negative"):
        compare(1.0, 1.0, mode=DiffMode.NORMALIZED, float_tolerance=-1.0)
