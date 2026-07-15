# ReproAgent

[![CI](https://github.com/MahdiNavaei/ReproAgent/actions/workflows/ci.yml/badge.svg)](https://github.com/MahdiNavaei/ReproAgent/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-3776AB)
![License](https://img.shields.io/badge/license-Apache--2.0-blue)
![Typing](https://img.shields.io/badge/typing-py.typed-informational)

> **The open-source flight recorder for AI agents. Capture failures. Replay them safely. Compare executions. Prevent regressions.**

Your agent failed once. ReproAgent turns that execution into a portable, versioned **AgentCase** that you can inspect, replay under an explicit offline contract, compare deterministically, and keep as a regression fixture.

```text
Record -> AgentCase / Failure Capsule -> Mock Replay -> Diff -> Regression Test
```

ReproAgent is local first. The core artifact is a JSON file, not a row in a hosted database and not an account in a SaaS control plane.

## Why this exists

Agent failures are unusually easy to lose.

A model chooses the wrong tool once. A provider upgrade changes a response shape. One tool argument is subtly different. A retry changes execution order. By the time someone opens the tracing dashboard, the exact context that produced the failure is gone or painful to reconstruct.

Logs and traces are excellent for answering **what happened?** ReproAgent is focused on the next questions:

- can I preserve this failure as a portable test artifact?
- can I re-run supported local code without calling the provider or executing the recorded tool again?
- can I compare this execution with another one deterministically?
- can CI tell me when this failure shape comes back?

ReproAgent complements logging, tracing, and observability systems. It is not trying to replace them.

## The core idea

An **AgentCase** is a bounded, data-only record of an agent execution.

It captures ordered execution evidence such as model requests and responses, tool calls and results, retries, exceptions, outcome, capture completeness, redaction metadata, and replay provenance.

That artifact can move from a debugging session into code review and regression tests without requiring ReproAgent-hosted storage.

## A quick tour

### 1. Capture an execution

```python
from reproagent.capture import capture

with capture(output="failure.agentcase", name="example-agent") as session:
    request_id = session.model_request(
        provider="example-provider",
        model="example-model",
        input={"prompt": "hello"},
    )

    session.model_response(
        parent_event_id=request_id,
        provider="example-provider",
        model="example-model",
        output={"text": "hi"},
    )
```

On context exit ReproAgent finalizes a validated AgentCase and persists it atomically when an output path is configured.

### 2. Replay supported local code against recorded interactions

```python
from reproagent.agentcase import load_agentcase
from reproagent.replay import MockReplayContext, run_mock_replay

case = load_agentcase("failure.agentcase")


def local_agent(replay: MockReplayContext) -> str:
    output = replay.model_response(
        provider="example-provider",
        model="example-model",
        input={"prompt": "hello"},
    )
    return str(output)


result = run_mock_replay(case, local_agent)
print(result.value)
```

`run_mock_replay` executes only the local callable you explicitly supply. Model and tool interactions requested through `MockReplayContext` must match the next recorded interaction and return recorded outputs or results as data.

There is no live provider or recorded-tool fallback.

### 3. Compare and keep the failure in CI

```python
from reproagent import DiffMode, assert_agentcase_regression, compare

result = compare(
    baseline_data,
    candidate_data,
    mode=DiffMode.NORMALIZED,
)

for difference in result.differences:
    print(difference.path, difference.kind)

assert_agentcase_regression(baseline_case, observed_case)
```

The optional pytest plugin also exposes an auto-discovered `agentcase_regression` fixture.

## What works today

### AgentCase and capture

- AgentCase format `0.1` open specification
- provider-neutral and framework-neutral domain models
- deterministic `.agentcase` JSON serialization
- strict loading, format validation, event ordering, identity, and parent-reference checks
- bounded input loading and atomic local persistence
- explicit framework-neutral Python `CaptureSession`
- message, model, tool, retry, exception, and logical-failure capture
- independent execution-outcome and capture-completeness semantics
- best-effort redaction before persistence
- context-local active sessions
- synchronous `@capture_tool` instrumentation that preserves normal Python invocation, return, and exception behavior

When an application exception escapes a capture context, that exception remains primary. Capture-side failures are best effort and must not replace the original application or provider exception.

### OpenAI Python SDK integration

The first provider adapter is explicit and instance local:

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

Current support:

- synchronous `OpenAI.responses.create(...)`
- synchronous `OpenAI.chat.completions.create(...)`
- exactly-once provider calls through the wrapped resource
- provider exceptions re-raised unchanged
- no global monkeypatching or API-key discovery
- unsupported normalization omits unsafe data and degrades capture completeness
- no arbitrary `repr` fallback for unsupported SDK objects
- `stream=True` passes the stream through unchanged, does not eagerly consume it, does not create a fake complete `model.response`, and marks capture degraded
- fake-client fault/security tests
- real `openai>=2,<3` SDK compatibility tests through offline `httpx.MockTransport`

Async OpenAI SDK capture is not implemented.

See [`docs/integrations/OPENAI_PYTHON_SDK.md`](docs/integrations/OPENAI_PYTHON_SDK.md).

### Safe mock replay execution

The supported execution replay API is `run_mock_replay(case, entrypoint)`.

The runner:

- re-executes only a caller-supplied local Python callable
- never imports an entrypoint from AgentCase data
- never calls a model provider
- never executes a recorded tool
- matches requested model and tool interactions in recorded order
- fails closed on missing, mismatched, extra, or unconsumed interactions
- has no live fallback

The caller-supplied callable is ordinary Python and is **not sandboxed**. The replay safety guarantee applies to external interactions routed through `MockReplayContext`.

### Replay artifact projection

A separate `mock_replay(case)` API and the CLI command below create a replay-provenance AgentCase projection:

```bash
reproagent replay failure.agentcase --mock --output replayed.agentcase
```

This operation copies validated recorded events as data and preserves the source `execution_id` because it does not represent a new application execution. A new `case_id` identifies the derived artifact and replay metadata records the projection.

It does **not** re-execute application code.

### Layered diff and regression

- exact deterministic comparison
- structural comparison
- normalized comparison
- stable JSONPath-like difference locations
- configurable floating-point tolerance
- `compare_agentcases()`
- `assert_agentcase_regression()`
- auto-discovered pytest fixture `agentcase_regression`

AgentCase regression defaults remove volatility only from known schema locations: root case/execution identity, root creation/replay provenance, and event-envelope identity, parent, and timestamps.

A business payload field named `timestamp`, `event_id`, or `replay` is still comparison data and still produces a regression when changed.

Semantic-model comparison is not included.

## CLI

Implemented commands:

```bash
reproagent --version
reproagent validate <case.agentcase>
reproagent inspect <case.agentcase>
reproagent replay <case.agentcase> --mock --output <output.agentcase>
```

The replay CLI is the data-only replay artifact projection described above. There is no live replay. Diff and regression are Python APIs rather than dedicated CLI commands in the initial release.

## Install from source

ReproAgent requires Python 3.11 or newer.

```bash
git clone https://github.com/MahdiNavaei/ReproAgent.git
cd ReproAgent
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
```

Optional runtime extras:

```bash
python -m pip install -e ".[openai]"
python -m pip install -e ".[pytest]"
```

The development extra includes the declared OpenAI SDK dependency so the advertised synchronous SDK surfaces are exercised offline in CI.

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

Read [`SECURITY.md`](SECURITY.md) and [`docs/architecture/SECURITY_AND_REDACTION_BASELINE.md`](docs/architecture/SECURITY_AND_REDACTION_BASELINE.md).

## Project status

ReproAgent is an **alpha-stage `0.1.x` project** with a deliberately narrow initial release boundary.

The working core is present and tested, but the Python APIs may still evolve. AgentCase format compatibility is treated separately from package API versioning: incompatible wire-format changes require an explicit version and compatibility decision rather than silent reinterpretation.

The project is intentionally choosing depth over a checklist of agent frameworks.

## Roadmap

Near-term work is driven by reproducible failure cases, compatibility pressure, security boundaries, and integration demand that can be tested offline.

Current priorities include learning from sanitized real-world failure shapes, maintaining OpenAI SDK compatibility, evaluating async capture, improving replay mismatch ergonomics, making regression reports easier to review in CI, and protecting AgentCase compatibility.

See [`docs/ROADMAP.md`](docs/ROADMAP.md) for the focused roadmap and explicit non-goals.

## Support the project

ReproAgent is independently maintained.

The most valuable support today is to try it on difficult agent failures, report minimal reproducible problems, contribute synthetic or independently sanitized failure shapes, improve compatibility tests, and share the project with engineers who debug agent systems.

If ReproAgent becomes useful to you or your team, sponsorship can help sustain SDK compatibility, security review, AgentCase compatibility, regression fixtures, documentation, and carefully scoped integrations.

The repository's official GitHub funding configuration is committed in [`.github/FUNDING.yml`](.github/FUNDING.yml). Only funding destinations displayed by GitHub from that configuration should be treated as official ReproAgent funding destinations.

See [`SUPPORT.md`](SUPPORT.md) for support and sustainability guidance.

## Architecture and specifications

Start with:

- [`docs/architecture/PROJECT_CHARTER.md`](docs/architecture/PROJECT_CHARTER.md)
- [`docs/architecture/MVP_SCOPE.md`](docs/architecture/MVP_SCOPE.md)
- [`docs/architecture/SYSTEM_ARCHITECTURE.md`](docs/architecture/SYSTEM_ARCHITECTURE.md)
- [`docs/architecture/CAPTURE_ENGINE.md`](docs/architecture/CAPTURE_ENGINE.md)
- [`docs/architecture/SECURITY_AND_REDACTION_BASELINE.md`](docs/architecture/SECURITY_AND_REDACTION_BASELINE.md)
- [`docs/architecture/REPLAY_SAFETY_MODEL.md`](docs/architecture/REPLAY_SAFETY_MODEL.md)
- [`docs/specs/AGENTCASE_SPEC_V0.md`](docs/specs/AGENTCASE_SPEC_V0.md)
- [`docs/specs/CAPTURE_EVENT_PAYLOADS_V0.md`](docs/specs/CAPTURE_EVENT_PAYLOADS_V0.md)

## Quality checks

```bash
python -m pytest
ruff check .
ruff format --check .
mypy src/reproagent
python -m build
```

GitHub Actions runs lint, formatting, strict typing, package-build verification, and the offline test suite across Python 3.11, 3.12, 3.13, and 3.14.

## Known initial-release limitations

- Capture is explicit; there is no arbitrary Python subprocess auto-instrumentation.
- The synchronous OpenAI integration is opt-in and limited to `responses.create` and `chat.completions.create`.
- Async OpenAI capture is not implemented.
- Anthropic, Ollama, LangGraph, CrewAI, AutoGen, and OpenAI Agents SDK integrations are not included.
- Replay execution requires an explicitly supplied local callable using `MockReplayContext`; caller code is not sandboxed.
- There is no live provider replay or side-effecting recorded-tool replay.
- Differential replay execution and semantic-model diff are not included.
- Diff and regression are Python APIs; dedicated CLI commands are not included.
- Redaction is a safety baseline, not a guarantee that an AgentCase is secret free or PII free.
- There is no dashboard, database, hosted service, or SaaS control plane.

These boundaries are intentional for a focused, reviewable initial release.

## Contributing

Read [`CONTRIBUTING.md`](CONTRIBUTING.md) before proposing changes. Strong issues start with a concrete failure or maintenance problem and the smallest synthetic reproduction that demonstrates it.

## Maintainer

ReproAgent is created and maintained by [Mahdi Navaei](https://github.com/MahdiNavaei).

The initial public release was gated by [`docs/RELEASE_READINESS.md`](docs/RELEASE_READINESS.md). PyPI publication and a GitHub Release remain separate explicit maintainer actions.
