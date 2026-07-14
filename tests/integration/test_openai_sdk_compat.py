from __future__ import annotations

import json

import httpx
from openai import OpenAI

from reproagent.capture import capture
from reproagent.domain import EventType
from reproagent.integrations.openai import capture_openai


def test_real_openai_sdk_surfaces_capture_offline_through_mock_transport() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/responses"):
            payload = {
                "id": "resp_test",
                "object": "response",
                "created_at": 0,
                "status": "completed",
                "model": "gpt-test",
                "output": [],
                "parallel_tool_calls": True,
                "tool_choice": "auto",
                "tools": [],
            }
            return httpx.Response(200, json=payload)
        if request.url.path.endswith("/chat/completions"):
            payload = {
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "created": 0,
                "model": "gpt-test",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "hello"},
                        "finish_reason": "stop",
                        "logprobs": None,
                    }
                ],
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_tokens": 2,
                },
            }
            return httpx.Response(200, json=payload)
        return httpx.Response(404, json={"error": {"message": "unexpected test path"}})

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    client = OpenAI(
        api_key="sk-proj-synthetic-offline-key-123456789",
        base_url="https://openai.invalid/v1",
        http_client=http_client,
        max_retries=0,
    )

    with capture() as session:
        traced = capture_openai(client)
        response = traced.responses.create(model="gpt-test", input="hello")
        completion = traced.chat.completions.create(
            model="gpt-test",
            messages=[{"role": "user", "content": "hello"}],
        )

    assert response.id == "resp_test"
    assert completion.id == "chatcmpl-test"
    assert len(requests) == 2
    assert [request.url.path for request in requests] == [
        "/v1/responses",
        "/v1/chat/completions",
    ]
    assert all(json.loads(request.content) for request in requests)
    assert session.case is not None
    model_events = [
        event
        for event in session.case.events
        if event.event_type in {EventType.MODEL_REQUEST, EventType.MODEL_RESPONSE}
    ]
    assert [event.event_type for event in model_events] == [
        EventType.MODEL_REQUEST,
        EventType.MODEL_RESPONSE,
        EventType.MODEL_REQUEST,
        EventType.MODEL_RESPONSE,
    ]
