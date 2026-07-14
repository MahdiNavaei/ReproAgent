# ReproAgent

> **The open-source flight recorder for AI agents. Capture failures. Replay them. Compare executions. Prevent regressions.**

ReproAgent is an early-stage local-first Python project for turning difficult AI-agent executions into portable cases that can be inspected now and, in later milestones, replayed, compared, and used as regression fixtures.

The product is intentionally focused on one journey:

```text
Record -> AgentCase / Failure Capsule -> Replay -> Diff -> Regression Test
```

ReproAgent is not a generic agent framework, hosted observability platform, prompt-management system, model gateway, or SaaS control plane.

## Why this exists

Agent failures are often difficult to reproduce. A model can choose the wrong tool, a tool can fail only for one input, a retry can change execution order, a provider or model upgrade can change behavior, or the original context can disappear before anyone debugs it.

ReproAgent's core artifact is an **AgentCase**: a portable, versioned, data-only record of an execution.

## Current status

The repository currently contains the **AgentCase v0 foundation and the first real manual Python Capture Engine**.

### Works now

- AgentCase format `0.1` open specification
- typed provider-neutral and framework-neutral domain models
- deterministic `.agentcase` JSON serialization
- strict loading and format-version validation
- event identity, ordering, and parent-reference integrity checks
- bounded input loading
- atomic local persistence for capture-generated cases
- manual Python `CaptureSession`
- execution start/end capture
- message capture
- normalized model request/response capture
- tool definition/call/result capture
- retry capture
- exception capture with original exception re-raising
- explicit logical failure outcomes
- independent capture-completeness semantics
- best-effort redaction before persistence
- context-local active sessions
- synchronous `@capture_tool` helper
- CLI commands:
  - `reproagent --version`
  - `reproagent validate <case.agentcase>`
  - `reproagent inspect <case.agentcase>`
- offline success and failure examples
- unit, contract, and security tests

### Not implemented yet

The following product commands remain planned and are **not** implemented:

```bash
reproagent record python my_agent.py
reproagent replay failure.agentcase
reproagent diff baseline.agentcase candidate.agentcase
reproagent test cases/
```

There is no transparent OpenAI/Anthropic/Ollama interception, no LangGraph/CrewAI/AutoGen/OpenAI Agents SDK integration, no subprocess auto-instrumentation, no replay engine, no diff engine, no pytest plugin, no dashboard, no database, and no hosted service.

## Requirements

ReproAgent requires Python 3.11 or newer.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
```

## Manual capture

The first supported capture integration is explicit framework-neutral Python instrumentation:

```python
from reproagent.capture import capture

with capture(
    output="runs/example.agentcase",
    name="example-agent",
) as session:
    session.message(
        role="user",
        content="Find order 123",
    )

    request_id = session.model_request(
        provider="example-provider",
        model="example-model",
        input={
            "messages": [
                {"role": "user", "content": "Find order 123"}
            ]
        },
    )

    response_id = session.model_response(
        parent_event_id=request_id,
        provider="example-provider",
        model="example-model",
        output={
            "message": {
                "role": "assistant",
                "content": "I will look up the order.",
            }
        },
        usage={"input_tokens": 10, "output_tokens": 12},
        latency_ms=120.5,
    )

    tool_call_id = session.tool_call(
        parent_event_id=response_id,
        name="lookup_order",
        arguments={"order_id": "123"},
    )

    session.tool_result(
        parent_event_id=tool_call_id,
        name="lookup_order",
        status="success",
        result={"status": "shipped"},
        latency_ms=8.2,
    )
```

On normal context exit, the session records `execution.end`, validates the AgentCase, and persists it when an output path is configured.

## Capturing logical failures

A failed agent execution does not have to raise a Python exception:

```python
from reproagent.capture import capture
from reproagent.domain import ExecutionOutcome

with capture(output="runs/logical-failure.agentcase") as session:
    session.set_outcome(
        ExecutionOutcome.FAILURE,
        reason="agent returned an invalid business decision",
    )
```

Execution outcome and capture completeness are separate concepts.

## Exception behavior

When an application exception escapes a capture context, ReproAgent attempts to:

1. record a normalized exception event,
2. mark the execution as failed unless a more specific outcome was already established,
3. record `execution.end`,
4. persist the AgentCase when technically possible,
5. re-raise the original application exception.

A Capture Engine failure must not silently replace the original application exception.

## Tool helper

Synchronous Python functions can use the optional convenience helper:

```python
from reproagent.capture import capture_tool

@capture_tool(name="lookup_order")
def lookup_order(order_id: str) -> dict[str, str]:
    return {"order_id": order_id, "status": "shipped"}
```

With no active Capture Session, the function behaves normally. Async tool decoration is explicitly unsupported in this milestone.

## Run the offline examples

Success path:

```bash
python examples/manual_capture_agent.py /tmp/manual-success.agentcase
reproagent validate /tmp/manual-success.agentcase
reproagent inspect /tmp/manual-success.agentcase
```

Failure path:

```bash
python examples/manual_capture_failure.py /tmp/manual-failure.agentcase
```

The failure example intentionally exits through its original Python exception. The artifact should still exist when capture and persistence succeed:

```bash
reproagent validate /tmp/manual-failure.agentcase
reproagent inspect /tmp/manual-failure.agentcase
```

## Validate and inspect existing cases

Validate the included synthetic Prompt 01 fixture:

```bash
reproagent validate examples/cases/minimal_failure.agentcase
```

Inspect it:

```bash
reproagent inspect examples/cases/minimal_failure.agentcase
```

## Security warning

Captured executions can contain API keys, authorization headers, cookies, connection strings, PII, customer content, private prompts, retrieved documents, filesystem paths, exception text, and sensitive tool output.

ReproAgent now applies a minimum redaction baseline before capture data is persisted. The defaults reduce obvious credential exposure, but they do **not** guarantee removal of all secrets, do not guarantee PII removal, and do not make an AgentCase safe to publish.

Treat every `.agentcase` as sensitive unless you have independently verified otherwise.

**Capturing data is not permission to replay side effects.** Validation and inspection never authorize future replay to send email, delete data, make purchases, modify databases, trigger workflows, or call live external systems.

## AgentCase v0

An `.agentcase` file is a single UTF-8 JSON document. It is data only: loading or inspecting it does not execute tools, import recorded application code, deserialize Python objects, or call a provider.

See:

- [`docs/specs/AGENTCASE_SPEC_V0.md`](docs/specs/AGENTCASE_SPEC_V0.md)
- [`docs/specs/CAPTURE_EVENT_PAYLOADS_V0.md`](docs/specs/CAPTURE_EVENT_PAYLOADS_V0.md)

## Architecture

Start with:

- [`docs/architecture/PROJECT_CHARTER.md`](docs/architecture/PROJECT_CHARTER.md)
- [`docs/architecture/MVP_SCOPE.md`](docs/architecture/MVP_SCOPE.md)
- [`docs/architecture/SYSTEM_ARCHITECTURE.md`](docs/architecture/SYSTEM_ARCHITECTURE.md)
- [`docs/architecture/CAPTURE_ENGINE.md`](docs/architecture/CAPTURE_ENGINE.md)
- [`docs/architecture/SECURITY_AND_REDACTION_BASELINE.md`](docs/architecture/SECURITY_AND_REDACTION_BASELINE.md)
- [`docs/architecture/REPLAY_SAFETY_MODEL.md`](docs/architecture/REPLAY_SAFETY_MODEL.md)

## Quality checks

```bash
python -m pytest
ruff check .
ruff format --check .
mypy src/reproagent
python -m build
```

The next milestone has not been started. Replay, diff, regression execution, and automatic provider/framework instrumentation remain outside this repository state.
