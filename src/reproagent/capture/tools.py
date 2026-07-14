"""Synchronous function instrumentation built on the active Capture Session API."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from contextlib import suppress
from functools import wraps
from time import perf_counter
from typing import ParamSpec, TypeVar, cast

from pydantic import JsonValue

from reproagent.capture.context import get_current_session
from reproagent.capture.errors import CaptureError
from reproagent.capture.payloads import ToolResultStatus

P = ParamSpec("P")
R = TypeVar("R")


def capture_tool(*, name: str | None = None) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Capture synchronous tool calls when a session is active; otherwise call normally."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        if inspect.iscoroutinefunction(func):
            raise TypeError("capture_tool supports synchronous functions only in this milestone")
        tool_name = name or func.__name__
        signature = inspect.signature(func)

        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            session = get_current_session()
            if session is None:
                return func(*args, **kwargs)

            call_event_id = None
            try:
                bound = signature.bind(*args, **kwargs)
                call_event_id = session.tool_call(
                    name=tool_name,
                    arguments=cast(JsonValue, dict(bound.arguments)),
                )
            except CaptureError:
                call_event_id = None

            started = perf_counter()
            try:
                result = func(*args, **kwargs)
            except BaseException as exc:
                latency_ms = max(0.0, (perf_counter() - started) * 1000.0)
                if call_event_id is not None:
                    with suppress(CaptureError):
                        session.tool_result(
                            parent_event_id=call_event_id,
                            name=tool_name,
                            status=ToolResultStatus.FAILURE,
                            error={"exception_type": type(exc).__name__, "message": str(exc)},
                            latency_ms=latency_ms,
                        )
                    with suppress(CaptureError):
                        session.exception(
                            exc,
                            parent_event_id=call_event_id,
                            handled=False,
                        )
                raise

            latency_ms = max(0.0, (perf_counter() - started) * 1000.0)
            if call_event_id is not None:
                with suppress(CaptureError):
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
