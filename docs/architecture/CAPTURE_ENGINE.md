# Capture Engine Architecture

## 1. Mission

Prompt 02 introduces the first real executable path from Python behavior to a valid AgentCase:

```text
explicit Python instrumentation
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

This is intentionally manual instrumentation. There is no provider monkeypatching, framework interception, subprocess recording, or network dependency.

## 2. Dependency direction

```text
integrations / user instrumentation
             ↓
        capture API
             ↓
      capture session
             ↓
     normalization layer
             ↓
      AgentCase builder
             ↓
       domain models
             ↓
   agentcase serialization
```

The domain package does not import capture. AgentCase serialization does not import provider SDKs.

## 3. Components

### `reproagent.capture.session`

Owns the explicit lifecycle, public event methods, outcome/completeness control, exception behavior, and finalization.

### `reproagent.capture.payloads`

Defines strict provider-neutral normalized payload models before data reaches the event builder.

### `reproagent.capture.builder`

Owns case/execution identity, central sequence allocation, parent validation, accumulated events, capture health, redaction records, diagnostics, and final construction of the public `AgentCase` model.

It does not create a second wire representation.

### `reproagent.capture.context`

Uses `contextvars` for the active session. No process-global mutable current session is used.

### `reproagent.capture.tools`

Provides the first convenience adapter, `@capture_tool`, for synchronous Python functions.

### `reproagent.security.redaction`

Runs before observed payload or metadata is retained by the builder. It provides structured sensitive-key redaction, conservative secret-pattern rules, and additive user-defined string rules.

### `reproagent.agentcase.atomic_dump_agentcase`

Writes validated canonical bytes to a temporary file in the destination directory, flushes and fsyncs the file, then publishes it. Existing targets are not overwritten unless `overwrite=True` is explicit.

This is a local-filesystem atomic publication strategy, not a claim of crash-proof durability on every filesystem or storage layer.

## 4. Lifecycle

A session moves through:

```text
created → active → finalizing → closed
```

Rules:

- observations before activation fail explicitly,
- observations after close fail explicitly,
- one central builder assigns event sequences,
- repeated `finalize()` after successful finalization returns the same immutable case,
- an `execution.start` event is recorded at activation,
- an `execution.end` event is recorded during finalization,
- the root outcome and terminal event outcome are constructed from one authoritative value.

## 5. Context manager semantics

### Normal exit

When the application leaves the context normally:

1. an unknown outcome defaults to `success`,
2. `execution.end` is appended,
3. the AgentCase is validated,
4. the case is atomically persisted when an output path exists.

### Application exception

When an exception escapes the context:

1. a normalized `exception` event is attempted,
2. outcome becomes `failure` unless a more specific outcome was already set,
3. `execution.end` is attempted,
4. the AgentCase is finalized and persistence is attempted,
5. the original application exception is re-raised.

A Capture Engine failure must not replace the original application exception. When both fail, the original exception remains primary and receives a safe note identifying that capture also failed.

## 6. Logical failures

Not all failed agent runs raise Python exceptions. `session.set_outcome(...)` records an explicit outcome and optional reason as data.

Execution outcome and capture completeness are independent. Examples include:

- failure + complete capture,
- success + degraded capture,
- failure + partial capture.

## 7. Diagnostics extension

Capture-specific diagnostics use the namespaced root extension:

```text
org.reproagent.capture/v1
```

Current fields include:

- warnings,
- unsupported observations,
- redaction failures,
- normalization failures,
- serialization warnings,
- dropped event count,
- degraded reasons.

Diagnostics intentionally retain safe categories and counts rather than raw failed payloads or secret values. Unknown extensions are not verified AgentCase core semantics.

## 8. Redaction boundary

Redaction runs before event payloads, event extensions, or explicit user metadata are retained by the builder.

Default behavior includes:

- case-insensitive sensitive-key matching,
- common authorization/token/password/connection-string key forms,
- conservative bearer-token detection in strings,
- conservative `sk-...` style key detection,
- additive user-defined string rules.

When redaction fails, the raw observed event is dropped rather than persisted unredacted. Capture completeness becomes at least `partial`, and safe diagnostics record the failure category.

Default redaction is best-effort. It does not guarantee removal of all secrets or PII and does not make an AgentCase safe to publish.

## 9. Ordering and concurrency

One builder owns one append-only event list and sequence allocator. Appends are protected by a re-entrant lock.

`contextvars` means ordinary asyncio tasks created within an active context inherit the same session context. Event order reflects actual observation order at the synchronized append boundary.

Limitations:

- new OS threads do not automatically inherit context-variable state,
- multiprocessing and separate processes have independent sessions,
- Prompt 02 is not distributed tracing,
- no cross-process ordering contract exists.

## 10. Nested sessions

Nested top-level capture sessions are rejected in the MVP. This avoids ambiguous active-session routing and accidental cross-case event attribution.

Future explicit child-span or child-case semantics may be designed separately rather than emerging accidentally from context nesting.

## 11. Tool helper semantics

`@capture_tool` supports synchronous functions only.

With an active session it attempts to record:

```text
tool.call → function execution → tool.result
```

If the function raises, the helper records a failed `tool.result` and an `exception` event when capture remains available, then re-raises the original exception.

Without an active session the wrapped function behaves normally.

Capture-helper failures are not allowed to replace the wrapped function's return value or application exception. Unsupported async decoration fails explicitly rather than pretending to work.

## 12. Performance posture

Prompt 02 is not a high-volume tracing benchmark. The implementation nevertheless avoids repeatedly serializing the entire case on each event and uses append-only event construction with constant-time event lookup by ID.

Canonical serialization happens at final persistence time.

## 13. Known limitations

- no transparent provider interception,
- no framework adapters,
- no subprocess `record` command,
- no async tool decorator,
- no automatic thread-context propagation,
- no distributed tracing,
- no guarantee that default redaction finds every secret or any particular PII class,
- no replay, diff, or regression execution.
