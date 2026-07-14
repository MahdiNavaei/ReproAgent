# ReproAgent roadmap

ReproAgent is intentionally narrow: capture difficult agent executions, turn them into portable AgentCases, replay supported local code against recorded interactions, compare executions, and prevent regressions.

The roadmap is ordered by maintenance value and real debugging pressure, not by feature count. There are no date promises in this document.

## Current release boundary

The initial public release includes:

- explicit `CaptureSession` instrumentation;
- synchronous `@capture_tool` instrumentation;
- synchronous OpenAI Python SDK capture for `responses.create` and `chat.completions.create`;
- AgentCase format `0.1` with bounded data-only loading;
- explicit local `run_mock_replay` execution through `MockReplayContext`;
- replay-provenance AgentCase projection;
- exact, structural, and normalized diff;
- AgentCase regression assertions and a pytest fixture;
- offline CI, package build verification, redaction tests, and malicious-input coverage.

## Near-term priorities

### 1. Learn from real sanitized failure cases

The highest-value input is a minimal, synthetic, or independently sanitized reproduction of an agent failure that current capture or replay contracts represent poorly.

Priorities include:

- missing event semantics that recur across real agent stacks;
- capture degradation that is difficult to diagnose safely;
- replay mismatches that need clearer contract errors;
- regression reports that are technically correct but hard to act on.

Real secrets, customer traces, production prompts, and private retrieved content are not acceptable test fixtures.

### 2. Keep provider compatibility honest

The current OpenAI adapter is synchronous and deliberately small. Near-term work includes maintaining compatibility with the declared SDK range and evaluating async OpenAI capture without weakening exception transparency, exactly-once provider calls, or streaming safety.

Additional provider adapters should be added only when they can emit through the provider-neutral AgentCase contracts and can be tested offline.

### 3. Improve replay ergonomics without live fallback

The current replay runner requires caller-supplied local Python code to route recorded model and tool interactions through `MockReplayContext`.

Useful next work may include:

- clearer mismatch diagnostics;
- explicit replay assertions;
- better helpers for adapting existing local agent code;
- richer declared substitutions and unresolved-dependency reporting.

Live provider replay and side-effecting recorded-tool replay are not a shortcut for these ergonomics.

### 4. Make regression failures easier to review in CI

The Python regression API is stable enough for the initial release. Candidate improvements include:

- concise human-readable summaries;
- machine-readable reports for CI artifacts;
- dedicated diff/test CLI commands after the Python contracts settle;
- focused assertions for outcomes, tool use, and selected payload paths.

### 5. Protect AgentCase compatibility

AgentCase is the center of the project. Work in this area includes:

- compatibility fixtures across package versions;
- explicit migration decisions before any incompatible format change;
- clearer extension guidance for integrations;
- validation hardening against malformed or adversarial artifacts.

## Explicitly not on the near-term roadmap

ReproAgent is not currently trying to become:

- a hosted observability platform;
- a generic agent framework;
- a prompt-management product;
- a model gateway;
- a multi-tenant SaaS control plane;
- a live side-effect replay system;
- an arbitrary remote-code execution service.

## How priorities are chosen

Maintainer time goes first to correctness, compatibility, security boundaries, reproducible user failures, and integrations with clear real-world demand.

A focused issue with a synthetic reproduction is a stronger priority signal than a broad request to support an entire framework ecosystem. See [`SUPPORT.md`](../SUPPORT.md) and [`CONTRIBUTING.md`](../CONTRIBUTING.md).
