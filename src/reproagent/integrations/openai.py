"""Explicit, duck-typed capture wrapper for the OpenAI Python SDK."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import suppress
from time import perf_counter
from typing import Any
from uuid import UUID

from pydantic import JsonValue

from reproagent.capture import CaptureSession, get_current_session
from reproagent.domain import CaptureCompleteness


class _UnsupportedNormalization(TypeError):
    """Internal signal that an SDK value cannot be retained as verified JSON data."""


class _CapturedCreateProxy:
    def __init__(
        self,
        resource: Any,
        *,
        endpoint: str,
        session: CaptureSession | None,
    ) -> None:
        self._resource = resource
        self._endpoint = endpoint
        self._session = session

    def create(self, *args: Any, **kwargs: Any) -> Any:
        session = self._resolve_session()
        request_event_id = self._capture_request(session, args, kwargs)
        started = _safe_perf_counter()
        try:
            response = self._resource.create(*args, **kwargs)
        except BaseException as exc:
            self._capture_exception(session, exc, request_event_id)
            raise

        if kwargs.get("stream") is True:
            _mark_degraded(
                session,
                "OpenAI streaming response capture is unsupported; stream passed through unchanged",
            )
            return response

        self._capture_response(
            session,
            response,
            request_event_id,
            latency_ms=_safe_latency_ms(started),
            request_kwargs=kwargs,
        )
        return response

    def __getattr__(self, name: str) -> Any:
        return getattr(self._resource, name)

    def _resolve_session(self) -> CaptureSession | None:
        if self._session is not None:
            return self._session
        try:
            return get_current_session()
        except BaseException:
            return None

    def _capture_request(
        self,
        session: CaptureSession | None,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> UUID | None:
        if session is None:
            return None
        try:
            model = kwargs.get("model")
            if not isinstance(model, str):
                raise _UnsupportedNormalization("OpenAI model identifier is not a string")
            raw_input = kwargs.get("input")
            if self._endpoint == "chat.completions" and raw_input is None:
                raw_input = kwargs.get("messages")
            parameters = {
                key: _to_json(value)
                for key, value in kwargs.items()
                if key not in {"model", "input", "messages", "tools"}
            }
            if args:
                parameters["positional_args"] = _to_json(args)
            raw_tools = kwargs.get("tools", ())
            tools = tuple(_to_json(item) for item in raw_tools) if raw_tools else ()
            return session.model_request(
                provider="openai",
                model=model,
                input=_to_json(raw_input),
                parameters=parameters,
                tools=tools,
                extensions={
                    "reproagent.integration": "openai",
                    "openai.endpoint": self._endpoint,
                },
            )
        except BaseException:
            _mark_degraded(
                session,
                "OpenAI request capture could not be normalized safely; request data omitted",
            )
            return None

    def _capture_response(
        self,
        session: CaptureSession | None,
        response: Any,
        request_event_id: UUID | None,
        *,
        latency_ms: float | None,
        request_kwargs: dict[str, Any],
    ) -> None:
        if session is None or request_event_id is None:
            return
        try:
            model = request_kwargs.get("model")
            if not isinstance(model, str):
                raise _UnsupportedNormalization("OpenAI model identifier is not a string")
            payload = _to_json(response)
            session.model_response(
                parent_event_id=request_event_id,
                provider="openai",
                model=model,
                output=payload,
                finish_reason=_finish_reason(payload),
                usage=_usage(payload),
                latency_ms=latency_ms,
                extensions={
                    "reproagent.integration": "openai",
                    "openai.endpoint": self._endpoint,
                },
            )
        except BaseException:
            _mark_degraded(
                session,
                "OpenAI response capture could not be normalized safely; response data omitted",
            )

    @staticmethod
    def _capture_exception(
        session: CaptureSession | None,
        exc: BaseException,
        request_event_id: UUID | None,
    ) -> None:
        if session is None:
            return
        try:
            session.exception(exc, parent_event_id=request_event_id, handled=False)
        except BaseException:
            _mark_degraded(
                session,
                "OpenAI provider exception observation could not be captured completely",
            )


class _ChatProxy:
    def __init__(self, chat: Any, *, session: CaptureSession | None) -> None:
        self._chat = chat
        self.completions = _CapturedCreateProxy(
            chat.completions,
            endpoint="chat.completions",
            session=session,
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._chat, name)


class OpenAICaptureClient:
    """Transparent client facade that captures selected synchronous OpenAI create calls."""

    def __init__(self, client: Any, *, session: CaptureSession | None = None) -> None:
        self._client = client
        self.responses = _CapturedCreateProxy(
            client.responses,
            endpoint="responses",
            session=session,
        )
        self.chat = _ChatProxy(client.chat, session=session)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


def capture_openai(
    client: Any,
    *,
    session: CaptureSession | None = None,
) -> OpenAICaptureClient:
    """Wrap one synchronous OpenAI client instance without global SDK patching."""

    return OpenAICaptureClient(client, session=session)


def _mark_degraded(session: CaptureSession | None, reason: str) -> None:
    if session is None:
        return
    with suppress(BaseException):
        session.set_completeness(CaptureCompleteness.DEGRADED, reason=reason)


def _to_json(value: Any) -> JsonValue:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Mapping):
        return {str(key): _to_json(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_to_json(item) for item in value]

    try:
        model_dump = getattr(value, "model_dump", None)
    except BaseException as exc:
        raise _UnsupportedNormalization("SDK value attributes are not safely inspectable") from exc
    if callable(model_dump):
        try:
            return _to_json(model_dump(mode="json"))
        except BaseException as exc:
            raise _UnsupportedNormalization("SDK model_dump value is unsupported") from exc

    try:
        to_dict = getattr(value, "to_dict", None)
    except BaseException as exc:
        raise _UnsupportedNormalization("SDK value attributes are not safely inspectable") from exc
    if callable(to_dict):
        try:
            return _to_json(to_dict())
        except BaseException as exc:
            raise _UnsupportedNormalization("SDK to_dict value is unsupported") from exc

    raise _UnsupportedNormalization(f"unsupported SDK value type: {type(value).__name__}")


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


def _finish_reason(payload: JsonValue) -> str | None:
    if not isinstance(payload, dict):
        return None
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    if not isinstance(first, dict):
        return None
    finish_reason = first.get("finish_reason")
    return finish_reason if isinstance(finish_reason, str) else None


def _usage(payload: JsonValue) -> dict[str, JsonValue] | None:
    if not isinstance(payload, dict):
        return None
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None
    return {str(key): value for key, value in usage.items()}
