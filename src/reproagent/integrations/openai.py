"""Explicit, duck-typed capture wrapper for the OpenAI Python SDK."""

from __future__ import annotations

from collections.abc import Mapping
from time import perf_counter
from typing import Any
from uuid import UUID

from pydantic import JsonValue

from reproagent.capture import CaptureSession, get_current_session
from reproagent.domain import CaptureCompleteness


class _UnsupportedNormalization(TypeError):
    """Internal signal that a value cannot be represented as verified JSON capture data."""


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
        session = self._session or get_current_session()
        request_event_id = self._capture_request(session, args, kwargs)
        started = perf_counter()
        try:
            response = self._resource.create(*args, **kwargs)
        except BaseException as exc:
            self._capture_exception(session, exc, request_event_id)
            raise

        if kwargs.get("stream") is True:
            _mark_unsupported(session, "openai streaming response capture is unsupported")
            return response

        self._capture_response(
            session,
            response,
            request_event_id,
            latency_ms=max(0.0, (perf_counter() - started) * 1000.0),
            request_kwargs=kwargs,
        )
        return response

    def __getattr__(self, name: str) -> Any:
        return getattr(self._resource, name)

    def _capture_request(
        self,
        session: CaptureSession | None,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> UUID | None:
        if session is None:
            return None
        try:
            model = kwargs.get("model", "unknown")
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
                model=str(model),
                input=_to_json(raw_input),
                parameters=parameters,
                tools=tools,
                extensions={
                    "reproagent.integration": "openai",
                    "openai.endpoint": self._endpoint,
                },
            )
        except BaseException:
            _mark_degraded(session, "openai request normalization failed; request data omitted")
            return None

    def _capture_response(
        self,
        session: CaptureSession | None,
        response: Any,
        request_event_id: UUID | None,
        *,
        latency_ms: float,
        request_kwargs: dict[str, Any],
    ) -> None:
        if session is None:
            return
        if request_event_id is None:
            _mark_degraded(session, "openai response could not be linked to a captured request")
            return
        try:
            payload = _to_json(response)
            session.model_response(
                parent_event_id=request_event_id,
                provider="openai",
                model=str(request_kwargs.get("model", "unknown")),
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
            _mark_degraded(session, "openai response normalization failed; response data omitted")

    @staticmethod
    def _capture_exception(
        session: CaptureSession | None,
        exc: BaseException,
        request_event_id: UUID | None,
    ) -> None:
        if session is None:
            return
        try:
            session.custom(
                payload={
                    "kind": "provider_exception",
                    "provider": "openai",
                    "exception_type": type(exc).__name__,
                },
                parent_event_id=request_event_id,
                extensions={"reproagent.integration": "openai"},
            )
        except BaseException:
            _mark_degraded(session, "openai provider exception metadata could not be captured")


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
    """Transparent synchronous client facade for selected OpenAI SDK create calls."""

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
    try:
        session.set_completeness(CaptureCompleteness.DEGRADED, reason=reason)
    except BaseException:
        pass


def _mark_unsupported(session: CaptureSession | None, reason: str) -> None:
    if session is None:
        return
    try:
        session.set_completeness(CaptureCompleteness.UNSUPPORTED, reason=reason)
    except BaseException:
        pass


def _to_json(value: Any) -> JsonValue:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Mapping):
        return {str(key): _to_json(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_to_json(item) for item in value]

    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return _to_json(model_dump(mode="json"))
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return _to_json(to_dict())

    raise _UnsupportedNormalization(
        f"unsupported OpenAI capture value type: {type(value).__name__}"
    )


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
