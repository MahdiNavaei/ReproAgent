# ReproAgent

> **The open-source flight recorder for AI agents. Capture failures. Replay them safely. Compare executions. Prevent regressions.**

ReproAgent is a local-first Python toolkit for turning difficult AI-agent executions into portable, versioned cases that can be inspected, replayed with recorded outputs, compared deterministically, and used as regression fixtures.

The product is focused on one journey:

```text
Record -> AgentCase / Failure Capsule -> Mock Replay -> Diff -> Regression Test
```

ReproAgent is not a generic agent framework, hosted observability platform, prompt-management system, model gateway, or SaaS control plane.

## Why this exists

Agent failures are often difficult to reproduce. A model can choose the wrong tool, a tool can fail only for one input, retries can change execution order, a provider or model upgrade can change behavior, or the original context can disappear before anyone debugs it.

ReproAgent's core artifact is an **AgentCase**: a portable, versioned, data-only record of an execution.

## Current release scope

The initial MVP implements the complete local workflow at a deliberately narrow safety boundary.

### AgentCase and capture

- AgentCase format `0.1` open specification
- typed provider-neutral and framework-neutral domain models
- deterministic `.agentcase` JSON serialization
- strict loading and format-version validation
- event identity, ordering, and parent-reference integrity checks
- bounded input loading
- atomic local persistence for capture-generated cases
- explicit framework-neutral Python `CaptureSession`
- execution, message, model, tool, retry, exception, and logical-failure capture
- independent execution-outcome and capture-completeness semantics
- best-effort sensitive-key redaction before persistence
- malicious-input regression coverage for common sensitive-key spelling bypasses
- context-local active sessions
- synchronous `@capture_tool` helper

### OpenAI Python SDK integration

- explicit opt-in `capture_openai(client)` wrapper for one client instance
- `client.responses.create(...)` capture
- `client.chat.completions.create(...)` capture
- no global monkeypatching
- no environment-variable or API-key discovery
- provider exceptions re-raised unchanged
- capture failures are best-effort and must not replace application/provider exceptions
- fake-client, offline test coverage only

See [`docs/integrations/OPENAI_PYTHON_SDK.md`](docs/integrations/OPENAI_PYTHON_SDK.md).

### Safe mock replay

- deterministic, data-only `mock_replay()`
- strict source validation by default
- one-to-one model request/response and tool call/result replay contracts
- explicit replay provenance and substitutions in AgentCase metadata
- fail-closed handling for incomplete captures unless explicitly allowed
- no provider calls
- no tool execution
- no recorded-code imports
- no live side effects

### Layered diff

- exact comparison
- structural comparison
- normalized comparison
- deterministic JSONPath-like difference locations
- recursive ignored-key support
- configurable floating-point tolerance
- no semantic-model or network dependency in the initial release

### Regression testing and pytest

- `compare_agentcases()`
- `assert_agentcase_regression()`
- deterministic `RegressionResult`
- safe defaults for volatile identity, timestamp, and replay fields
- auto-discovered pytest fixture: `agentcase_regression`

### CLI

Implemented commands:

```bash
reproagent --version
reproagent validate <case.agentcase>
reproagent inspect <case.agentcase>
reproagent replay <case.agentcase> --mock --output <output.agentcase>
```

The CLI does **not** provide live replay. Diff and regression comparison are currently Python APIs rather than CLI commands.

## Requirements

ReproAgent requires Python 3.11 or newer. CI currently exercises Python 3.11, 3.12, 3.13, and 3.14.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
```

Optional extras:

```bash
python -m pip install -e ".[openai]"
python -m pip install -e ".[pytest]"
```

## Manual capture

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

## Capture an OpenAI SDK client explicitly

```python
from openai import OpenAI

from reproagent.capture import capture
from reproagent.integrations.openai import capture_openai

client = OpenAI()

with capture(output="runs/openai.agentcase"):
    traced = capture_openai(client)
    response = traced.responses.create(
        model="your-model",
        input="Explain this synthetic failure.",
    )
```

ReproAgent wraps only the client instance you pass. Other client resources are forwarded unchanged and are not implicitly captured.

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

When an application exception escapes a capture context, ReproAgent attempts to record the failure, finalize the execution, and persist the AgentCase when technically possible. It then re-raises the original application exception.

A Capture Engine or provider-integration failure must not silently replace the original application/provider exception.

## Safe mock replay

Python API:

```python
from reproagent.replay import mock_replay

replayed = mock_replay(recorded_case)
```

CLI:

```bash
reproagent replay failure.agentcase --mock --output replayed.agentcase
```

Mock replay reuses recorded outputs as data. It does not call providers, execute tools, or import recorded application code.

## Diff executions

```python
from reproagent import DiffMode, compare

result = compare(
    baseline_data,
    candidate_data,
    mode=DiffMode.NORMALIZED,
)

if not result.equal:
    for difference in result.differences:
        print(difference.path, difference.kind)
```

The initial release intentionally does not include semantic-model comparison.

## Regression tests

```python
from reproagent import assert_agentcase_regression

assert_agentcase_regression(baseline_case, observed_case)
```

Or use the pytest fixture:

```python
def test_agent_behavior(agentcase_regression, baseline_case, observed_case):
    agentcase_regression(baseline_case, observed_case)
```

By default, volatile AgentCase identity, timestamp, and replay fields are ignored for regression comparison.

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

```bash
reproagent validate examples/cases/minimal_failure.agentcase
reproagent inspect examples/cases/minimal_failure.agentcase
```

## Security warning

Captured executions can contain API keys, authorization headers, cookies, connection strings, PII, customer content, private prompts, retrieved documents, filesystem paths, exception text, and sensitive tool output.

ReproAgent applies a minimum redaction baseline before capture data is persisted. The defaults reduce obvious credential exposure, including common separator and casing variants of known sensitive keys, but they do **not** guarantee removal of all secrets, do not guarantee PII removal, and do not make an AgentCase safe to publish.

Treat every `.agentcase` as sensitive unless you have independently verified otherwise.

**Capturing data is not permission to replay side effects.** Mock replay never authorizes sending email, deleting data, making purchases, modifying databases, triggering workflows, or calling live external systems.

## AgentCase v0

An `.agentcase` file is a single UTF-8 JSON document. It is data only: loading, inspection, mock replay, diff, and regression comparison do not execute tools, import recorded application code, deserialize Python objects, or call a provider.

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

GitHub Actions runs lint, formatting, strict typing, build verification, and the offline test suite across the supported Python matrix.

## Known initial-release limitations

- Capture is explicit; ReproAgent does not auto-instrument arbitrary Python subprocesses.
- The OpenAI Python SDK integration is opt-in and limited to `responses.create` and `chat.completions.create`.
- Anthropic, Ollama, LangGraph, CrewAI, AutoGen, and OpenAI Agents SDK integrations are not included yet.
- Replay is deterministic mock replay only. There is no live side-effecting replay.
- Diff is exact, structural, or normalized. Semantic comparison is not included.
- Diff and regression comparison are Python APIs; dedicated CLI commands are not included.
- Redaction is a safety baseline, not a guarantee that an AgentCase is secret-free or PII-free.
- There is no dashboard, database, hosted service, or SaaS control plane.

These limits are intentional for a focused, reviewable initial public release.

## Contributing and security

Read [`CONTRIBUTING.md`](CONTRIBUTING.md) before proposing changes and [`SECURITY.md`](SECURITY.md) before reporting a vulnerability.

The repository should not be made public until the release-readiness checklist in [`docs/RELEASE_READINESS.md`](docs/RELEASE_READINESS.md) has been verified against the final `main` commit.
