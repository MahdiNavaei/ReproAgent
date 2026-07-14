# OpenAI Python SDK integration

ReproAgent provides an explicit opt-in wrapper for one OpenAI Python client instance. It does not monkeypatch the SDK, replace process-global state, inspect environment variables, or make any network calls of its own.

## Install

```bash
python -m pip install -e ".[openai]"
```

## Capture Responses API calls

```python
from openai import OpenAI

from reproagent.capture import capture
from reproagent.integrations.openai import capture_openai

client = OpenAI()

with capture(output="failure.agentcase"):
    traced = capture_openai(client)
    response = traced.responses.create(
        model="gpt-5.4-mini",
        input="Explain this synthetic failure.",
    )
```

## Capture Chat Completions calls

```python
with capture(output="chat.agentcase"):
    traced = capture_openai(client)
    completion = traced.chat.completions.create(
        model="gpt-5.4-mini",
        messages=[{"role": "user", "content": "hello"}],
    )
```

The wrapper records normalized `model.request` and `model.response` events through the active `CaptureSession`. `responses.create` and `chat.completions.create` are supported in this milestone. Other client resources are forwarded unchanged and are not implicitly captured.

## Failure behavior

Provider exceptions are re-raised unchanged. ReproAgent makes a best-effort attempt to add an exception event, but an instrumentation failure is never allowed to replace the original provider exception.

Capture normalization or response-serialization failures are also best-effort at the integration boundary. The wrapped provider call still runs and returns its original response. This design intentionally favors preserving application behavior over pretending a degraded capture is complete.

## Safety boundary

The integration is instance-local and explicit:

- no global monkeypatching
- no hidden telemetry
- no API-key discovery or storage
- no provider calls created by ReproAgent
- no live replay
- no execution of recorded code

The automated tests use fake clients only and do not require credentials or network access.
