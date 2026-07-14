"""Offline compatibility checks against the real declared OpenAI Python SDK."""

from __future__ import annotations

import json

import httpx
from openai import OpenAI

from reproagent.capture import capture
from reproagent.domain import EventType
from reproagent.integrations.openai import capture_openai


def test_real_openai_sdk_responses_and_chat_surfaces_use_mock_transport_only() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/v1/responses":
            return httpx.Response(
                200,
                request=request,
                json={
                    "id": "resp_test",
                    "object": "response",
                    "created_at": 1,
                    "status": "completed",
                    "error": None,
                    "incomplete_details": None,
                    "instructions": None,
                    "max_output_tokens": None,
                    "model": "gpt-test",
                    "output": [],
                    "parallel_tool_calls": True,
                    "previous_response_id": None,
                    "reasoning": None,
                    "store": False,
                    "temperature": 1.0,
                    "text": {"format": {"type": "text"}},
                    "tool_choice": "auto",
                    "tools": [],
                    "top_p": 1.0,
                    "truncation": "disabled",
                    "usage": {
                        "input_tokens": 1,
                        "input_tokens_details": {"cached_tokens": 0},
                        "output_tokens": 1,
                        "output_tokens_details": {"reasoning_tokens": 0},
                        "total_tokens": 2,
                    },
                    "metadata": {},
                },
            )
        if request.url.path == "/v1/chat/completions":
            return httpx.Response(
                200,
                request=request,
                json={
                    "id": "chatcmpl_test",
                    "object": "chat.completion",
                    "created": 1,
                    "model": "gpt-test",
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": "hello",
                                "refusal": None,
                                "annotations": [],
                            },
                            "logprobs": None,
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 1,
                        "completion_tokens": 1,
                        "total_tokens": 2,
                    },
                },
            )
        raise AssertionError(f"unexpected SDK request path: {request.url.path}")

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    client = OpenAI(
        api_key="sk-proj-offlinecompatibility000000",
        base_url="https://offline.invalid/v1",
        http_client=http_client,
    )

    with capture() as session:
        traced = capture_openai(client)
        response = traced.responses.create(model="gpt-test", input="hello")
        completion = traced.chat.completions.create(
            model="gpt-test",
            messages=[{"role": "user", "content": "hello"}],
        )

    assert response.id == "resp_test"
    assert completion.id == "chatcmpl_test"
    assert [request.url.path for request in requests] == [
        "/v1/responses",
        "/v1/chat/completions",
    ]
    assert all(json.loads(request.content) for request in requests)
    assert session.case is not None
    assert sum(
        event.event_type == EventType.MODEL_REQUEST for event in session.case.events
    ) == 2
    assert sum(
        event.event_type == EventType.MODEL_RESPONSE for event in session.case.events
    ) == 2
