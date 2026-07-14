# ReproAgent Project Charter

## Mission

ReproAgent is the open-source flight recorder for AI agents: capture failures, replay them under explicit conditions, compare executions, and prevent regressions.

The canonical product journey is:

```text
Record -> AgentCase / Failure Capsule -> Replay -> Diff -> Regression Test
```

## Problem boundary

AI agents can fail because of model behavior, prompts, context, tool selection, malformed tool results, retries, provider changes, external dependencies, and implementation changes. Ordinary logs are often incomplete, framework-specific, or unsuitable for deterministic reproduction.

ReproAgent focuses on reproducible execution failures and regression prevention. It is not a generic observability suite, agent framework, prompt platform, model gateway, or hosted control plane.

## Product principles

1. **Local first.** Core workflows work without a ReproAgent cloud account.
2. **Portable artifacts.** AgentCase data is independent of an internal database.
3. **Deterministic where possible.** Deterministic, best-effort, and live behavior are never conflated.
4. **Provider neutral.** The core schema does not encode one provider API as the domain model.
5. **Framework neutral.** Framework-specific capture is implemented by adapters.
6. **Security by default.** Captured data is assumed sensitive and redaction is first-class metadata.
7. **Honest failure semantics.** Partial, degraded, unsupported, interrupted, and unknown states remain explicit.
8. **Open specification.** The portable format is documented independently from Python implementation details.

## MVP success definition

The MVP is complete when a supported local Python agent execution can be captured into an AgentCase, inspected, replayed under a clearly defined supported contract, compared with another execution, and used as a regression fixture.

The current initial-release candidate meets that definition at a deliberately narrow boundary:

- capture is explicit through `CaptureSession` and selected opt-in adapters;
- replay execution requires a caller-supplied local Python callable and explicit `MockReplayContext` use;
- recorded model outputs and tool results are substituted without provider calls or tool execution;
- missing, mismatched, or unconsumed recorded interactions fail closed;
- diff is deterministic exact, structural, or normalized comparison;
- regression comparison and pytest integration operate on validated AgentCases.

## Replay identity and safety boundary

ReproAgent never imports or executes an entrypoint from AgentCase data. A replayed Python callable is supplied explicitly by the caller. The current mock replay runner does not sandbox that caller-owned local code; it guarantees only that interactions requested through `MockReplayContext` use recorded data and never fall back to a live provider or recorded tool.

The older `mock_replay()` API and CLI command create a replay-provenance AgentCase projection from recorded events. They are useful for artifact provenance, but they are not the execution contract. Actual supported local replay execution is `run_mock_replay(case, entrypoint)`.

## Current initial-release scope

Implemented:

- AgentCase v0 specification and versioning contract;
- provider-neutral, framework-neutral domain models;
- deterministic JSON serialization and bounded safe loading;
- event integrity validation;
- explicit Capture Session and synchronous `@capture_tool` instrumentation;
- opt-in synchronous OpenAI Python SDK capture for `responses.create` and `chat.completions.create`;
- explicit caller-supplied deterministic mock replay execution with recorded interaction substitution;
- replay-provenance artifact projection and mock replay CLI;
- exact, structural, and normalized diff;
- AgentCase regression assertion API and pytest fixture;
- redaction baseline, tests, quality tooling, package build, and CI.

Not implemented:

- transparent arbitrary-process recording;
- async OpenAI SDK capture;
- Anthropic, Ollama, LangGraph, CrewAI, AutoGen, or OpenAI Agents SDK adapters;
- live provider replay or side-effecting tool replay;
- differential replay execution;
- semantic-model diff;
- hosted services, databases, dashboards, accounts, RBAC, billing, or telemetry upload.

## Compatibility posture

The Python package, public API, and AgentCase format are versioned independently. Format incompatibility is a hard error rather than a silent reinterpretation. Extension fields use explicit namespaced extension maps.

## Maintainer rule

A smaller implementation that preserves these contracts is preferred over speculative abstractions. New infrastructure must answer a current product requirement, not a hypothetical enterprise future.
