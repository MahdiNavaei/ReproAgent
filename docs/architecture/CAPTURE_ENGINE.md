# Capture Engine Architecture

## 1. Mission

The Capture Engine is the explicit path from observed local Python behavior to a valid AgentCase:

```text
explicit Python instrumentation / selected adapter
                     ↓
                Capture Session
                     ↓
          normalized payload contracts
                     ↓
              redaction boundary
                     ↓
            ordered AgentCase builder
                     ↓
          validated AgentCase model
                     ↓
           atomic local persistence
```

Capture is intentionally explicit. There is no arbitrary-process recorder, global provider monkeypatch, subprocess interception, or hidden telemetry.

## 2. Components

### `reproagent.capture.session`

Owns explicit lifecycle, public event methods, outcome/completeness control, exception behavior, finalization, and persistence orchestration.

### `reproagent.capture.payloads`

Defines strict provider-neutral normalized payload models before event retention.

### `reproagent.capture.builder`

Owns identity, sequence allocation, parent validation, accumulated events, capture health, redaction records, diagnostics, and final construction of the public AgentCase model.

### `reproagent.capture.context`

Uses `contextvars` for the active session. No unsafe process-global current-session value is used.

### `reproagent.capture.tools`

Provides synchronous `@capture_tool` convenience instrumentation.

### `reproagent.security.redaction`

Runs before observed payload or metadata is retained by the builder. It provides sensitive-key redaction, conservative secret-pattern rules, and additive user-defined string rules.

### `reproagent.agentcase.atomic_dump_agentcase`

Publishes validated canonical bytes atomically on the local filesystem when technically supported by the target filesystem semantics. Existing targets are not overwritten unless `overwrite=True` is explicit.

## 3. Lifecycle

A session moves through:

```text
created -> active -> finalizing -> closed
```

Rules:

- observations before activation or after close fail explicitly;
- one central builder assigns event sequences;
- repeated successful `finalize()` returns the same immutable case;
- `execution.start` is recorded at activation;
- `execution.end` is recorded during finalization;
- root and terminal outcomes use one authoritative value.

## 4. Context manager and exception semantics

### Normal exit

On normal exit an unknown outcome defaults to `success`, `execution.end` is appended, AgentCase validation runs, and configured persistence is attempted. A capture failure may surface because no application exception is already primary.

### Application exception

When a `BaseException` escapes application code:

1. ReproAgent attempts to observe the exception;
2. it attempts to set failure outcome when appropriate;
3. it attempts finalization and persistence;
4. it attempts context reset;
5. the original application exception remains primary and is re-raised by Python context-manager semantics.

Unexpected capture-side `BaseException` failures in those attempts are collected. They may add constant safe notes naming only the capture failure type to the original exception. They are not allowed to replace the original application/provider exception.

If capture observation itself fails, completeness is best-effort elevated to `partial` with a constant diagnostic reason before finalization when possible.

## 5. Logical failures and capture health

Not all failed agent runs raise Python exceptions. `session.set_outcome(...)` records explicit logical outcome and optional reason.

Execution outcome and capture completeness remain independent. Valid combinations include failure plus complete capture, success plus degraded capture, and failure plus partial capture.

Capture diagnostics live under `org.reproagent.capture/v1` and retain safe categories, counts, and constant reasons rather than raw failed payloads.

## 6. Redaction boundary

Redaction runs before event payloads, extensions, or explicit user metadata are retained. Defaults cover normalized sensitive-key forms and conservative bearer/`sk-...` style secret patterns.

When redaction fails, raw observed data is dropped rather than persisted unredacted and capture completeness becomes at least `partial`.

Default redaction is best effort. It does not guarantee removal of every secret or PII class and does not make an AgentCase safe to publish.

## 7. `@capture_tool` transparency

`@capture_tool` supports synchronous functions only.

With an active session it best-effort observes:

```text
tool.call -> wrapped function exactly once -> tool.result
```

Signature binding is an observation attempt, not a substitute for Python invocation. Binding failures are suppressed and the wrapped function is still invoked normally, so missing and duplicate argument errors originate from normal function call semantics.

For valid calls, omitted defaults and `*args`/`**kwargs` shapes are observed when normalization succeeds.

If the wrapped function raises, best-effort failure/result events are attempted and the original exception object is re-raised. Unexpected capture-side `BaseException` failures cannot replace it. A successful wrapped return object is returned unchanged even when result capture fails.

Without an active session the wrapped function is called directly.

## 8. Provider adapter boundary

Provider integrations emit through Capture Session contracts. The initial OpenAI adapter is explicit, instance-local, synchronous, and limited to `responses.create` and `chat.completions.create`.

Adapters must report degraded observation honestly. Unsupported provider values are omitted rather than stored through arbitrary representations. Adapter failures may not create additional provider calls or replace provider results/exceptions.

## 9. Ordering and concurrency

One builder owns one append-only event list and synchronized sequence allocator. `contextvars` lets ordinary asyncio tasks created in an active context inherit the session context.

New OS threads do not automatically inherit context-variable state. Multiprocessing and separate processes remain independent. There is no cross-process ordering or distributed tracing claim.

## 10. Nested sessions

Nested top-level capture sessions are rejected. Explicit child-span or child-case semantics must be designed separately rather than emerging accidentally from context nesting.

## 11. Performance posture

The implementation avoids serializing the full case per event and uses append-only construction with constant-time event lookup by ID. Canonical serialization happens at final persistence time.

## 12. Known limitations

- no transparent arbitrary-process or subprocess recording;
- no automatic framework interception;
- no async tool decorator;
- no automatic thread-context propagation;
- no distributed tracing;
- no guarantee default redaction finds every secret or PII class.

Replay, diff, and regression are implemented in separate package boundaries and are documented in the project charter, MVP scope, system architecture, and replay safety model.
