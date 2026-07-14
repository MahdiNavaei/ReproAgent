# ReproAgent Project Charter

## Mission

ReproAgent is the open-source flight recorder for AI agents: capture failures, replay them, compare executions, and prevent regressions.

The project exists to make a failed agent execution portable enough to inspect later, replay under explicit conditions, compare against another execution, and convert into a regression fixture.

The canonical product journey is:

```text
Record -> AgentCase / Failure Capsule -> Replay -> Diff -> Regression Test
```

## Problem boundary

AI agents can fail because of model behavior, prompts, context, tool selection, malformed tool results, retries, provider changes, external dependencies, and implementation changes. Ordinary logs are often incomplete, framework-specific, or unsuitable for deterministic replay.

ReproAgent focuses on reproducible execution failures and regression prevention. It is not a generic observability suite, agent framework, prompt platform, model gateway, or hosted control plane.

## Product principles

1. **Local first.** Core workflows work without a ReproAgent cloud account.
2. **Portable artifacts.** AgentCase data is independent of an internal database.
3. **Deterministic where possible.** Deterministic, best-effort, and live behavior are never conflated.
4. **Provider neutral.** The core schema does not encode one provider's API as the domain model.
5. **Framework neutral.** Framework-specific capture is implemented by adapters.
6. **Security by default.** Captured data is assumed sensitive and redaction is first-class metadata.
7. **Honest failure semantics.** Partial, degraded, unsupported, interrupted, and unknown states remain explicit.
8. **Open specification.** The portable format is documented independently from Python implementation details.

## MVP success definition

The MVP is complete when a supported local Python agent execution can be captured into an AgentCase, inspected, replayed in clearly defined modes, compared with another execution, and used as a regression fixture.

This foundation milestone does not implement that complete journey. It establishes the contracts required to implement it without changing the product's identity.

## Frozen scope for the foundation milestone

Included now:

- AgentCase v0 specification and versioning contract
- provider-neutral, framework-neutral domain models
- deterministic JSON serialization and bounded safe loading
- event integrity validation
- minimal `--version`, `validate`, and `inspect` CLI commands
- replay safety and security contracts
- example artifact, tests, quality tooling, and CI

Excluded now:

- capture engine and provider interception
- agent replay execution
- diff engine
- regression runner and pytest plugin
- hosted services, databases, dashboards, accounts, RBAC, billing, and telemetry upload

## Compatibility posture

The Python package, public API, and AgentCase format are versioned independently. Format incompatibility is a hard error rather than a silent reinterpretation. Extension fields use explicit namespaced extension maps.

## Maintainer rule

A smaller implementation that preserves these contracts is preferred over speculative abstractions. New infrastructure must answer a current product requirement, not a hypothetical enterprise future.


## Current implementation status after the Capture Engine foundation

The repository now includes the first real manual Python Capture Engine in addition to the original AgentCase v0 foundation. A local Python application can explicitly open a capture session, record normalized execution/model/tool events, apply the minimum redaction baseline, and atomically persist a valid AgentCase.

Replay, diff, regression execution, automatic provider/framework interception, hosted services, and SaaS infrastructure remain outside the current implementation. The product mission and MVP boundary are unchanged.
