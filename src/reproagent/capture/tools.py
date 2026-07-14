"""Synchronous function instrumentation built on the active Capture Session API."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from contextlib import suppress
from functools import wraps
from time import perf_counter
from typing import ParamSpec, TypeVar, cast

from pydantic import JsonValue

from reproagent.capture.context import get_current_session
from reproagent.capture.payloads import ToolResultStatus

P = ParamSpec("P")
R = TypeVar("R")


def capture_tool(*, name: str | None = None) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Capture synchronous tool calls without changing wrapped-function behavior."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        if inspect.iscoroutinefunction(func):
            raise TypeError("capture_tool supports synchronous functions only in this milestone")
        tool_name = name or func.__name__
        try:
            signature = inspect.signature(func)
        except BaseException:
            signature = None

        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            try:
                session = get_current_session()
            except BaseException:
                session = None
            if session is None:
                return func(*args, **kwargs)

            call_event_id = None
            if signature is not None:
                try:
                    bound = signature.bind(*args, **kwargs)
                    bound.apply_defaults()
                    arguments = _to_json_value(dict(bound.arguments))
                    call_event_id = session.tool_call(name=tool_name, arguments=arguments)
                except BaseException:
                    call_event_id = None

            started = _safe_perf_counter()
            try:
                result = func(*args, **kwargs)
            except BaseException as exc:
                latency_ms = _safe_latency_ms(started)
                if call_event_id is not None:
                    error: dict[str, JsonValue] = {"exception_type": type(exc).__name__}
                    try:
                        error["message"] = str(exc)
                    except BaseException:
                        error["message"] = "<unavailable>"
                    with suppress(BaseException):
                        session.tool_result(
                            parent_event_id=call_event_id,
                            name=tool_name,
                            status=ToolResultStatus.FAILURE,
                            error=error,
                            latency_ms=latency_ms,
                        )
                    with suppress(BaseException):
                        session.exception(
                            exc,
                            parent_event_id=call_event_id,
                            handled=False,
                        )
                raise

            latency_ms = _safe_latency_ms(started)
            if call_event_id is not None:
                with suppress(BaseException):
                    session.tool_result(
                        parent_event_id=call_event_id,
                        name=tool_name,
                        status=ToolResultStatus.SUCCESS,
                        result=cast(JsonValue, result),
                        latency_ms=latency_ms,
                    )
            return result

        return wrapper

    return decorator


def _to_json_value(value: object) -> JsonValue:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _to_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_json_value(item) for item in value]
    raise TypeError(f"unsupported tool observation type: {type(value).__name__}")


def _safe_perf_counter() -> float | None:
    try:
        return perf_counter()
    except BaseException:
        return None


def _safe_latency_ms(started: float | None) -> float | None:
    if started is None:
        return None
    try:
        return max(0.0, (perf_counter() - started) * 1000.0)
    except BaseException:
        return None
