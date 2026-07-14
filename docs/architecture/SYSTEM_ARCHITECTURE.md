# System Architecture

## Architecture baseline

ReproAgent is a lightweight Python package with a portable data artifact at its center.

```text
User instrumentation / future adapters
                 |
                 v
          Capture Session
                 |
                 v
      Normalized event payloads
                 |
                 v
       Redaction before retention
                 |
                 v
      Ordered AgentCase builder
                 |
                 v
      Provider-neutral Domain Model
                 |
                 v
          AgentCase v0 JSON
           /      |      \
          v       v       v
       Inspect   Replay   Diff        (replay and diff are future)
                          |
                          v
                   Regression Tests    (future)
```

## Current package boundaries

### `reproagent.domain`

Owns provider-neutral, framework-neutral validated domain types and enums. It has no network behavior and does not import capture or integration implementation.

### `reproagent.agentcase`

Owns the data-only `.agentcase` serialization boundary: bounded file loading, format header checks, model validation, deterministic canonical serialization, atomic local publication, and human-readable summaries.

### `reproagent.capture`

Owns the first real execution capture path: explicit manual Python instrumentation, lifecycle control, normalized payload contracts, ordered event creation, capture diagnostics, context-local active-session access, and synchronous tool convenience instrumentation.

### `reproagent.security`

Owns the current best-effort redaction pipeline and additive user-defined redaction-rule extension point.

### `reproagent.cli`

Owns the thin local command-line adapter. It delegates validation and inspection to the core package and contains no provider logic.

Replay, diff, regression execution, and provider/framework integration packages are intentionally not implemented yet.

## Dependency direction

```text
user instrumentation / future integrations
                 ↓
              capture
                 ↓
       normalization + builder
                 ↓
              domain
                 ↓
             agentcase

cli → agentcase → domain
capture → security
capture → agentcase
capture → domain
```

The domain package does not depend on capture, CLI, security implementation, or integrations. AgentCase serialization does not depend on provider SDKs.

## Python support baseline

The package requires Python 3.11 or newer. Python 3.11 is the minimum supported version so the project does not begin on a runtime close to upstream end of life while still covering modern supported interpreter lines in CI.

## Validation approach

Pydantic v2 remains the single runtime dependency. It provides typed public domain models, strict normalized payload models, deterministic validation errors, and rejection of unknown schema fields. The wire format remains plain JSON and is documented independently from Pydantic.

## Artifact boundary

AgentCase v0 is UTF-8 JSON. Loading does not execute Python code or reconstruct arbitrary Python objects. Unknown top-level fields are rejected. Controlled evolution is available through explicit `extensions` maps whose values are preserved as data but are not treated as verified core semantics.

## Deterministic serialization

Canonical serialization uses:

- UTF-8,
- sorted object keys,
- compact separators,
- no NaN or Infinity,
- normalized JSON forms for UUIDs, enums, and datetimes,
- one trailing newline.

Deterministic serialization means the same validated semantic model produces the same bytes under the same AgentCase format rules. It does not mean two independent live executions are behaviorally deterministic.

## Current capture architecture

The first Capture Engine is explicit and framework neutral:

1. user code or a future adapter calls the public Capture Session API,
2. strict normalized payload models validate common semantics,
3. redaction runs before observed payload data is retained,
4. one ordered builder allocates event sequences and validates parents,
5. the builder constructs the same public `AgentCase` domain model used everywhere else,
6. persistence uses deterministic serialization and atomic local publication.

Capture diagnostics are recorded under the namespaced extension `org.reproagent.capture/v1` rather than changing the AgentCase `0.1` root schema.

## Concurrency boundary

The active session uses `contextvars`, not one unsafe process-global mutable value. Ordinary asyncio tasks created inside the active context inherit the session context. Event append operations use one synchronized sequence allocator.

New OS threads do not automatically inherit context-variable state. Multiprocessing and separate processes remain independent. Prompt 02 does not claim distributed tracing.

## Future integration architecture

Provider and framework adapters will observe their native callbacks or SDK behavior and emit through the same Capture Session API. They must normalize common semantics before using namespaced extensions and must report unsupported or degraded observations explicitly.

No current code monkeypatches provider SDKs, HTTP clients, frameworks, or subprocesses.

## Future replay architecture

Replay will consume a validated AgentCase plus an explicit replay plan. The plan selects mock, live, or differential mode and records substitutions and unresolved dependencies. Mock replay and live replay must be separate code paths at the command boundary; no fallback may silently cross that boundary.

## Future diff architecture

Diff will expose layered comparators rather than one opaque score. Exact and structural comparison remain deterministic. Normalized comparison applies documented canonicalization rules. Semantic comparison is optional and additive.

## Future test architecture

Regression assertions should operate on validated AgentCase and replay results through a small public assertion API. A future pytest plugin can be an optional integration rather than a core runtime dependency.
