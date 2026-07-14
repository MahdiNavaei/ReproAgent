# ReproAgent

> **The open-source flight recorder for AI agents. Capture failures. Replay them. Compare executions. Prevent regressions.**

ReproAgent is an early-stage local-first project for turning difficult AI-agent failures into portable execution cases that can be inspected, replayed under explicit conditions, compared, and eventually used as regression tests.

## The problem

Agent failures are often hard to reproduce. A model may choose the wrong tool, a tool may return malformed data, a retry loop may appear only with one context, or a model/provider change may alter behavior after the original trace is gone.

ReproAgent is focused on one workflow:

```text
Record -> AgentCase / Failure Capsule -> Replay -> Diff -> Regression Test
```

It is not intended to become a generic agent framework, hosted observability platform, prompt manager, or model gateway.

## Current status

This repository currently contains the **MVP foundation**, not the complete product.

### What works now

- AgentCase format `0.1` specification
- typed provider-neutral and framework-neutral domain models
- deterministic `.agentcase` JSON serialization
- strict loading and format-version validation
- event identity, ordering, and parent-reference integrity checks
- bounded input loading
- minimal CLI commands:
  - `reproagent --version`
  - `reproagent validate <case.agentcase>`
  - `reproagent inspect <case.agentcase>`
- synthetic example and contract/security tests

### What does not work yet

The following product commands are **planned, not implemented**:

```bash
reproagent record python my_agent.py
reproagent replay failure.agentcase
reproagent diff baseline.agentcase candidate.agentcase
reproagent test cases/
```

There is no provider interception, capture engine, replay execution, diff engine, pytest plugin, dashboard, database, or hosted service in this milestone.

## Installation for development

ReproAgent requires Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
```

## Minimal local usage

Validate the included synthetic failed execution:

```bash
reproagent validate examples/cases/minimal_failure.agentcase
```

Inspect it:

```bash
reproagent inspect examples/cases/minimal_failure.agentcase
```

Run the test suite and quality checks:

```bash
python -m pytest
ruff check .
ruff format --check .
mypy src/reproagent
```

## AgentCase v0

An `.agentcase` file is currently a single UTF-8 JSON document. It is data only: loading or inspecting it does not execute tools, import recorded code, or call a provider.

The open format contract is documented in [`docs/specs/AGENTCASE_SPEC_V0.md`](docs/specs/AGENTCASE_SPEC_V0.md).

## Security warning

Captured executions may contain API keys, authorization headers, cookies, connection strings, PII, customer content, private prompts, retrieved documents, and sensitive tool output.

Treat every `.agentcase` as sensitive unless you have verified otherwise. Redaction metadata records what the capture process claims to have redacted; it is not proof that an artifact contains no secrets.

**Capturing data is not permission to replay side effects.** Validation and inspection never authorize a future replay to send email, delete data, make purchases, modify databases, trigger workflows, or call other live external systems.

See:

- [`docs/architecture/SECURITY_AND_REDACTION_BASELINE.md`](docs/architecture/SECURITY_AND_REDACTION_BASELINE.md)
- [`docs/architecture/REPLAY_SAFETY_MODEL.md`](docs/architecture/REPLAY_SAFETY_MODEL.md)

## Architecture

Start with:

- [`docs/architecture/PROJECT_CHARTER.md`](docs/architecture/PROJECT_CHARTER.md)
- [`docs/architecture/MVP_SCOPE.md`](docs/architecture/MVP_SCOPE.md)
- [`docs/architecture/SYSTEM_ARCHITECTURE.md`](docs/architecture/SYSTEM_ARCHITECTURE.md)

The next milestone is the actual Capture Engine foundation. It is intentionally not part of this repository state yet.
