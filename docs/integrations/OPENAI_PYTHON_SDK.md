# OpenAI Python SDK integration

ReproAgent provides an explicit opt-in wrapper for one **synchronous** OpenAI Python client instance. It does not monkeypatch the SDK, replace process-global state, inspect environment variables, discover or store API keys, or make provider calls of its own.

## Install

```bash
python -m pip install -e ".[openai]"
```

The development extra also installs the declared OpenAI SDK dependency so CI can exercise the real SDK surfaces offline.

## Capture Responses API calls

```python
from openai import OpenAI

from reproagent.capture import capture
from reproagent.integrations.openai import capture_openai

client = OpenAI()

with capture(output="failure.agentcase"):
    traced = capture_openai(client)
    response = traced.responses.create(
        model="your-model",
        input="Explain this synthetic failure.",
    )
```

## Capture Chat Completions calls

```python
with capture(output="chat.agentcase"):
    traced = capture_openai(client)
    completion = traced.chat.completions.create(
        model="your-model",
        messages=[{"role": "user", "content": "hello"}],
    )
```

The wrapper records normalized `model.request` and `model.response` events through the active `CaptureSession` for synchronous `responses.create` and `chat.completions.create`. Other client resources are forwarded unchanged and are not implicitly captured.

## Failure and completeness behavior

The wrapped provider call executes exactly once. Provider exceptions are re-raised unchanged. ReproAgent makes a best-effort attempt to record the exception, but any capture-side failure is suppressed so it cannot replace the provider exception.

Request or response normalization is fail-safe at the integration boundary. Unsupported SDK/request values are **not** retained through arbitrary `repr` strings. Instead, the unsupported capture data is omitted and capture completeness is marked `degraded` with a constant safe diagnostic reason. The provider call still runs and its original result is returned.

This means a degraded OpenAI capture is never represented as a verified complete observation merely because the provider call succeeded.

## Streaming

Synchronous calls with `stream=True` pass the returned stream object through unchanged. ReproAgent does not eagerly iterate or buffer the stream and does not create a fake complete `model.response` event before stream consumption. Capture completeness is marked `degraded` because stream event capture is not supported in this release.

## Async boundary

`AsyncOpenAI` and async resource capture are not implemented in this release. `capture_openai` documents and supports synchronous client surfaces only; it must not be treated as an async instrumentation adapter.

## Offline compatibility tests

The test suite covers both fake clients for fault/security injection and the real declared `openai>=2,<3` SDK using `httpx.MockTransport`. The real-SDK test calls `OpenAI.responses.create` and `OpenAI.chat.completions.create` through deterministic in-process fake HTTP responses. It uses a synthetic credential and performs no live provider or network call.

## Safety boundary

The integration is instance-local and explicit:

- no global monkeypatching;
- no hidden telemetry;
- no API-key discovery or storage;
- no provider calls created by ReproAgent;
- no extra provider retries created by ReproAgent;
- no live replay;
- no execution of recorded code.

Captured content can still be sensitive. The redaction layer is a baseline, not a secrecy or PII-removal guarantee. Treat every AgentCase as sensitive until independently reviewed.
