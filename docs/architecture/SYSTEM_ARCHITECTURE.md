# System Architecture

## Architecture baseline

ReproAgent is a lightweight local-first Python package with a portable data artifact at its center.

```text
manual instrumentation / selected adapters
                 ↓
          Capture Session
                 ↓
      normalization + redaction
                 ↓
       ordered AgentCase builder
                 ↓
          AgentCase v0 JSON
          /       |        \
         ↓        ↓         ↓
     inspect   mock replay   diff
                 execution    ↓
                    ↓       regression
          caller-supplied local code
          + recorded substitutions
```

## Current package boundaries

### `reproagent.domain`

Owns provider-neutral, framework-neutral validated domain types and enums. It has no network behavior and does not import capture or provider integrations.

### `reproagent.agentcase`

Owns bounded data-only `.agentcase` loading, format validation, deterministic canonical serialization, atomic local publication, and summaries.

### `reproagent.capture`

Owns explicit execution capture, lifecycle control, normalized payload contracts, ordered event creation, capture diagnostics, context-local active sessions, and synchronous `@capture_tool` instrumentation. Capture-side failures are best effort and may not replace an application exception that is already propagating.

### `reproagent.integrations`

Owns opt-in provider adapters. The initial OpenAI adapter wraps one synchronous client instance and only captures `responses.create` and `chat.completions.create`. It does not monkeypatch the SDK or discover API keys. Unsupported values are omitted with degraded completeness rather than stored through arbitrary object representations. Streaming responses pass through unchanged and are not represented as complete responses.

### `reproagent.replay`

Owns validated mock replay contracts. `run_mock_replay` executes one caller-supplied local callable against `MockReplayContext`. The context substitutes recorded model outputs and tool results, matches them in recorded order, and fails closed with no live fallback. ReproAgent never obtains executable code from AgentCase data.

`mock_replay` is a separate replay-provenance artifact projection. It copies validated events as data and does not execute user code.

### `reproagent.diff`

Owns deterministic exact, structural, and normalized JSON-data comparison.

### `reproagent.regression`

Owns AgentCase regression comparison and assertions. Default volatility removal is limited to known AgentCase schema locations; identically named fields inside event payloads remain business data.

### `reproagent.cli`

Owns the thin local CLI for version, validation, inspection, and mock replay artifact projection. It contains no provider logic and does not expose live replay.

## Dependency direction

```text
integrations / user instrumentation → capture
capture → security + agentcase + domain
replay → domain
regression → diff + domain
cli → agentcase + replay
agentcase → domain
```

The domain package does not depend on capture, CLI, security implementation, replay, diff, regression, or provider SDKs. The OpenAI SDK remains an optional integration dependency rather than a core runtime dependency.

## Artifact boundary

AgentCase v0 is bounded UTF-8 JSON. Loading does not execute Python code or reconstruct arbitrary Python objects. Unknown top-level fields are rejected. Namespaced extension values are preserved as data but are not treated as verified core semantics.

Canonical serialization uses UTF-8, sorted object keys, compact separators, no NaN or Infinity, normalized JSON forms for UUIDs/enums/datetimes, and one trailing newline.

## Capture architecture

The Capture Engine is explicit and framework neutral:

1. user code or an adapter calls the Capture Session API;
2. normalized payload models validate common semantics;
3. redaction runs before observed payload data is retained;
4. one ordered builder allocates event sequences and validates parents;
5. capture health and degradation remain explicit;
6. the builder constructs the public AgentCase model;
7. persistence uses deterministic serialization and atomic local publication.

Capture diagnostics are recorded under `org.reproagent.capture/v1`.

## Instrumentation transparency

`CaptureSession.__exit__` treats an already-propagating application exception as primary. Unexpected capture-side `BaseException` failures during exception observation, outcome update, finalization, or context reset are retained only as safe notes when possible and cannot become the raised primary exception.

`@capture_tool` executes the wrapped function exactly once. Signature binding and event recording are observation attempts, not replacement invocation validation. Missing or duplicate arguments therefore retain normal Python call semantics. Successful return objects and raised exception objects are preserved.

## Replay architecture

A validated AgentCase is never an executable program. The current execution replay API requires the caller to provide a local callable directly:

```text
validated AgentCase + explicit callable
                 ↓
          MockReplayContext
                 ↓
 next recorded request/call must match
                 ↓
 recorded response/result returned as data
```

No source-module path, entrypoint string, or recorded code from AgentCase is imported. Missing or mismatched interactions raise `ReplayContractError`; there is no provider or tool fallback. The caller-owned callable itself is ordinary local Python and is not sandboxed.

## Regression architecture

Generic diff still supports caller-selected recursive ignored keys. AgentCase regression defaults do not use recursive name-only ignoring. They normalize only root `case_id`, `execution_id`, `created_at`, `replay`, and event-envelope `event_id`, `parent_event_id`, and `timestamp` locations before diff. Payload fields with those names remain visible to regression checks.

## Concurrency boundary

Active capture uses `contextvars`; ordinary asyncio tasks created inside an active context inherit the session. Event append uses one synchronized sequence allocator. New OS threads do not automatically inherit the context and separate processes remain independent.

## Current limitations

There is no transparent arbitrary-process recording, async OpenAI capture, automatic thread propagation, distributed tracing, live replay, side-effecting tool replay, differential replay execution, semantic-model diff, hosted service, or SaaS control plane.
