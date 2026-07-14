"""Synchronous function instrumentation built on the active Capture Session API."""

from __future__ import annotations

import inspect
from collections.abc import Callable
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

        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            session = get_current_session()
            if session is None:
                return func(*args, **kwargs)

            call_event_id = None
            try:
                call_event_id = session.tool_call(
                    name=tool_name,
                    arguments=cast(
                        JsonValue,
                        {"args": list(args), "kwargs": dict(kwargs)},
                    ),
                )
            except BaseException:
                # Instrumentation is best-effort. In particular, do not pre-bind the
                # signature: Python must remain the authority for invocation errors.
                call_event_id = None

            started = perf_counter()
            try:
                result = func(*args, **kwargs)
            except BaseException as exc:
                latency_ms = max(0.0, (perf_counter() - started) * 1000.0)
                if call_event_id is not None:
                    try:
                        session.tool_result(
                            parent_event_id=call_event_id,
                            name=tool_name,
                            status=ToolResultStatus.FAILURE,
                            error={"exception_type": type(exc).__name__},
                            latency_ms=latency_ms,
                        )
                    except BaseException:
                        pass
                    try:
                        session.exception(
                            exc,
                            parent_event_id=call_event_id,
                            handled=False,
                        )
                    except BaseException:
                        pass
                raise

            latency_ms = max(0.0, (perf_counter() - started) * 1000.0)
            if call_event_id is not None:
                try:
                    session.tool_result(
                        parent_event_id=call_event_id,
                        name=tool_name,
                        status=ToolResultStatus.SUCCESS,
                        result=cast(JsonValue, result),
                        latency_ms=latency_ms,
                    )
                except BaseException:
                    pass
            return result

        return wrapper

    return decorator
