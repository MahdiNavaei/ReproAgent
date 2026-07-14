# ReproAgent

> **The open-source flight recorder for AI agents. Capture failures. Replay them safely. Compare executions. Prevent regressions.**

ReproAgent is a local-first Python toolkit for turning difficult AI-agent executions into portable, versioned AgentCases that can be inspected, replayed under explicit offline contracts, compared deterministically, and used as regression fixtures.

```text
Record -> AgentCase / Failure Capsule -> Mock Replay -> Diff -> Regression Test
```

ReproAgent is not a generic agent framework, hosted observability platform, prompt-management system, model gateway, or SaaS control plane.

## Current initial-release scope

### AgentCase and capture

- AgentCase format `0.1` open specification
- provider-neutral and framework-neutral domain models
- deterministic `.agentcase` JSON serialization
- strict loading, format validation, event ordering, identity, and parent-reference integrity checks
- bounded input loading and atomic local persistence
- explicit framework-neutral Python `CaptureSession`
- execution, message, model, tool, retry, exception, and logical-failure capture
- independent execution-outcome and capture-completeness semantics
- best-effort redaction before persistence
- context-local active sessions
- synchronous `@capture_tool` helper that preserves normal Python invocation, return, and exception behavior

### OpenAI Python SDK integration

- explicit instance-local `capture_openai(client)` wrapper
- synchronous `OpenAI.responses.create(...)` capture
- synchronous `OpenAI.chat.completions.create(...)` capture
- no global monkeypatching, environment-variable discovery, or API-key discovery
- provider calls execute exactly once through the wrapped resource
- provider exceptions re-raised unchanged
- unsupported normalization omits unsafe data and degrades capture completeness
- no arbitrary `repr` fallback for unsupported SDK objects
- `stream=True` responses pass through unchanged, are not eagerly consumed, do not create fake complete model responses, and mark capture degraded
- fake-client fault/security tests plus real `openai>=2,<3` SDK compatibility tests using offline `httpx.MockTransport`

Async OpenAI SDK capture is not implemented.

See [`docs/integrations/OPENAI_PYTHON_SDK.md`](docs/integrations/OPENAI_PYTHON_SDK.md).

### Safe mock replay

The supported execution replay API is explicit:

```python
from reproagent.replay import MockReplayContext, run_mock_replay


def local_agent(replay: MockReplayContext) -> str:
    output = replay.model_response(
        provider="example-provider",
        model="example-model",
        input={"prompt": "hello"},
    )
    return str(output)


result = run_mock_replay(recorded_case, local_agent)
```

`run_mock_replay` re-executes only the local callable supplied directly by the caller. ReproAgent never imports or executes an entrypoint from AgentCase data. Model and tool interactions requested through `MockReplayContext` must match the next recorded interaction and return recorded outputs/results as data.

The runner is fail closed:

- no provider calls
- no recorded tool execution
- no recorded-code imports
- no live fallback
- missing or mismatched interactions raise `ReplayContractError`
- a successful run must consume all recorded model/tool interactions

The caller-supplied local callable is ordinary Python and is not sandboxed. The replay guarantee applies to dependencies explicitly routed through `MockReplayContext`.

A separate `mock_replay(case)` API and `reproagent replay ... --mock` CLI command create a replay-provenance AgentCase projection. They copy validated recorded events as data; they do **not** re-execute application code.

### Layered diff and regression

- exact, structural, and normalized deterministic diff
- stable JSONPath-like difference locations
- configurable floating-point tolerance
- `compare_agentcases()` and `assert_agentcase_regression()`
- auto-discovered pytest fixture `agentcase_regression`

Regression defaults remove volatility only from known AgentCase schema locations: root case/execution identity, root creation/replay provenance, and event-envelope identity/parent/timestamps. Payload fields named `timestamp`, `event_id`, or `replay` remain business data and still produce regressions when changed.

Semantic-model comparison is not included.

### CLI

Implemented commands:

```bash
reproagent --version
reproagent validate <case.agentcase>
reproagent inspect <case.agentcase>
reproagent replay <case.agentcase> --mock --output <output.agentcase>
```

The replay CLI is the data-only replay artifact projection described above. There is no live replay. Diff and regression are Python APIs rather than dedicated CLI commands.

## Requirements and development

ReproAgent requires Python 3.11 or newer. CI exercises Python 3.11, 3.12, 3.13, and 3.14.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
```

Optional runtime extras:

```bash
python -m pip install -e ".[openai]"
python -m pip install -e ".[pytest]"
```

The development extra includes the declared OpenAI SDK dependency so the advertised synchronous SDK surfaces are tested offline in CI.

## Manual capture

```python
from reproagent.capture import capture

with capture(output="runs/example.agentcase", name="example-agent") as session:
    session.message(role="user", content="Find order 123")

    request_id = session.model_request(
        provider="example-provider",
        model="example-model",
        input={"messages": [{"role": "user", "content": "Find order 123"}]},
    )

    response_id = session.model_response(
        parent_event_id=request_id,
        provider="example-provider",
        model="example-model",
        output={"message": {"role": "assistant", "content": "I will look it up."}},
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
    )
```

On normal context exit the session records `execution.end`, validates the AgentCase, and persists it when an output path is configured.

When an application exception escapes a capture context, that exception remains primary. ReproAgent attempts to observe and finalize the capture, but an unexpected capture-side failure must not replace the original application exception.

## Capture an OpenAI client explicitly

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

Only the supplied synchronous client facade and supported create methods are captured. Other resources are forwarded unchanged.

## Diff and regression

```python
from reproagent import DiffMode, compare

result = compare(baseline_data, candidate_data, mode=DiffMode.NORMALIZED)
for difference in result.differences:
    print(difference.path, difference.kind)
```

```python
from reproagent import assert_agentcase_regression

assert_agentcase_regression(baseline_case, observed_case)
```

Or use the optional pytest fixture:

```python
def test_agent_behavior(agentcase_regression, baseline_case, observed_case):
    agentcase_regression(baseline_case, observed_case)
```

## Offline examples

```bash
python examples/manual_capture_agent.py /tmp/manual-success.agentcase
reproagent validate /tmp/manual-success.agentcase
reproagent inspect /tmp/manual-success.agentcase
```

```bash
python examples/manual_capture_failure.py /tmp/manual-failure.agentcase
reproagent validate /tmp/manual-failure.agentcase
reproagent inspect /tmp/manual-failure.agentcase
```

The failure example intentionally exits through its original Python exception; the artifact should still exist when capture and persistence succeed.

## Security warning

Captured executions can contain API keys, authorization headers, cookies, connection strings, PII, customer content, private prompts, retrieved documents, filesystem paths, exception text, and sensitive tool output.

ReproAgent applies a minimum redaction baseline before capture data is persisted. The defaults reduce obvious credential exposure, but they do **not** guarantee removal of all secrets or PII and do not make an AgentCase safe to publish.

Treat every `.agentcase` as sensitive until independently reviewed.

Capturing data is not permission to replay side effects. Current mock replay never calls providers or executes recorded tools. The explicit caller-supplied local replay callable is not sandboxed, so callers remain responsible for their own code outside `MockReplayContext`.

## AgentCase v0

An `.agentcase` file is a bounded UTF-8 JSON data artifact. Loading, inspection, diff, regression comparison, replay artifact projection, and construction of a replay context do not deserialize arbitrary Python objects or execute AgentCase-provided code.

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

GitHub Actions runs lint, formatting, strict typing, package build verification, and the offline test suite across the supported Python matrix.

## Known initial-release limitations

- Capture is explicit; there is no arbitrary Python subprocess auto-instrumentation.
- The synchronous OpenAI integration is opt-in and limited to `responses.create` and `chat.completions.create`.
- Async OpenAI capture is not implemented.
- Anthropic, Ollama, LangGraph, CrewAI, AutoGen, and OpenAI Agents SDK integrations are not included.
- Replay execution requires an explicitly supplied local callable using `MockReplayContext`; caller code is not sandboxed.
- There is no live provider replay or side-effecting recorded-tool replay.
- Differential replay execution and semantic-model diff are not included.
- Diff and regression are Python APIs; dedicated CLI commands are not included.
- Redaction is a safety baseline, not a guarantee that an AgentCase is secret-free or PII-free.
- There is no dashboard, database, hosted service, or SaaS control plane.

These boundaries are intentional for a focused, reviewable initial release.

## Contributing and security

Read [`CONTRIBUTING.md`](CONTRIBUTING.md) before proposing changes and [`SECURITY.md`](SECURITY.md) before reporting a vulnerability.

The repository must remain private until [`docs/RELEASE_READINESS.md`](docs/RELEASE_READINESS.md) has been verified against the final `main` commit. PyPI publication and a GitHub Release are separate explicit owner actions.
