# AgentCase Specification v0

**Status:** Draft foundation contract
**Format name:** `agentcase`
**Format version:** `0.1`
**Default file extension:** `.agentcase`

## 1. Purpose

AgentCase is a portable, data-only record of one agent execution or one replay-derived execution. It is designed for inspection, replay planning, comparison, and regression testing without requiring an internal database.

This specification defines the initial v0 wire contract independently from the Python implementation.

## 2. Serialization

AgentCase v0 is one UTF-8 encoded JSON object stored directly in a `.agentcase` file.

A conforming writer uses canonical serialization:

- JSON object root,
- UTF-8 encoding,
- lexicographically sorted object keys,
- compact separators,
- no NaN or Infinity values,
- JSON strings for UUIDs and enum values,
- timezone-aware RFC 3339 / ISO 8601 datetime strings,
- one trailing newline.

A reader may accept non-canonical whitespace but must validate semantic structure before treating the file as an AgentCase.

### Rationale

Plain JSON is chosen for v0 because the required MVP data is structured text and numbers, portability is more important than compression, and inspection should not require a container library. ZIP or JSON-plus-attachments would add complexity before the MVP has a concrete binary-attachment requirement.

### Limitations

- large binary payloads are inefficient,
- repeated content is not compressed,
- one file must fit within implementation-specific safety limits,
- raw attachments are not supported in v0.

A future independently versioned format may introduce a container with a manifest and content-addressed attachments. Readers must not reinterpret such a format as AgentCase `0.1`.

## 3. Root object

Required root fields:

| Field | Type | Meaning |
|---|---|---|
| `format_name` | string | Must equal `agentcase`. |
| `format_version` | string | Must equal a version supported by the reader; this spec defines `0.1`. |
| `case_id` | UUID string | Stable identity of this portable case. |
| `execution_id` | UUID string | Identity of the represented execution. |
| `created_at` | timezone-aware datetime string | Artifact creation timestamp. |
| `metadata` | object | Execution metadata. |
| `events` | array of event objects | Ordered execution events. |
| `outcome` | enum string | Explicit execution outcome. |
| `completeness` | enum string | Explicit capture completeness. |
| `redaction` | object | Redaction metadata. |
| `replay` | object or null | Replay provenance when applicable. |
| `extensions` | object | Namespaced non-core data. |

Unknown root fields are rejected by AgentCase v0 readers. Forward-compatible experimental data belongs under `extensions` and is preserved as unverified data.

## 4. Identity

`case_id` and `execution_id` are UUIDs and serve different purposes. A case may be copied without changing `case_id`; a new execution, including a replay execution, receives a distinct `execution_id`. Replay provenance identifies the source case separately.

## 5. Execution metadata

`metadata` contains:

- `reproagent_version`: package version of the writer,
- `runtime`: Python implementation and Python version,
- `platform`: operating system, release, and machine architecture,
- optional `provider`: provider identifier and optional provider version,
- optional `model`: model identifier and JSON-safe configuration,
- optional `integration`: adapter/integration identifier and optional version,
- `user_metadata`: user-defined JSON-safe metadata,
- `extensions`: namespaced non-core data.

The provider, model, and integration objects are descriptive metadata. Their absence must be represented as `null`, not guessed.

## 6. Event model

Events form one deterministic ordered sequence. Each event contains:

| Field | Type | Meaning |
|---|---|---|
| `event_id` | UUID string | Unique within the case. |
| `event_type` | enum string | Normalized event taxonomy value. |
| `sequence` | non-negative integer | Zero-based event position. |
| `timestamp` | timezone-aware datetime string | Observed event time. |
| `parent_event_id` | UUID string or null | Earlier parent event when applicable. |
| `payload` | JSON object | Event-specific data. |
| `capture_status` | enum string | Capture quality for this event. |
| `redaction_status` | enum string | Redaction state for this event. |
| `extensions` | object | Namespaced non-core event data. |

### 6.1 Ordering rules

- Event IDs are unique within one case.
- Sequence values are contiguous, unique, zero-based, and stored in sequence order.
- A parent reference must identify an event in the same case.
- A parent event must appear before its child.

Timestamps do not define canonical ordering because clocks can collide or move. `sequence` defines order.

### 6.2 Initial taxonomy

| Event type | Purpose |
|---|---|
| `execution.start` | Execution boundary start. |
| `execution.end` | Execution boundary end and terminal details. |
| `message` | System, user, assistant, or other normalized message. |
| `model.request` | Request sent or prepared for a model provider. |
| `model.response` | Response received from a model provider. |
| `tool.definition` | Tool contract made available to the agent. |
| `tool.call` | Agent request to invoke a tool. |
| `tool.result` | Tool success or failure result. |
| `exception` | Exception observed during execution. |
| `retry` | Explicit retry attempt or retry scheduling event. |
| `custom` | Adapter-specific event that cannot yet be normalized without inventing semantics. |

The taxonomy separates execution boundaries, communication, model interactions, tool lifecycle, and failures while keeping payloads provider-neutral. Tool failure is represented by `tool.result` payload state and may also be accompanied by an `exception` when an exception was actually observed. This avoids inventing duplicate event classes for every provider-specific failure shape.

`custom` is an escape hatch, not permission to encode a framework's entire trace model as opaque core semantics. Adapters should normalize common behavior first and identify custom payloads through namespaced extension data.

### 6.3 Capture status

Allowed event capture states:

- `captured`
- `partial`
- `failed`
- `unsupported`

An event marked `partial`, `failed`, or `unsupported` remains visible evidence that capture was incomplete.

## 7. Outcome model

Allowed execution outcomes:

- `success`
- `failure`
- `partial`
- `cancelled`
- `timeout`
- `unknown`

A boolean success field is insufficient and is not part of the core contract.

## 8. Capture completeness

Allowed case-level completeness values:

- `complete`: all data required by the active capture contract was captured,
- `partial`: some expected data is missing,
- `degraded`: capture continued with reduced fidelity,
- `interrupted`: capture ended before normal completion,
- `unsupported`: the integration could not represent the execution reliably.

Completeness is independent from outcome. A failed execution can be completely captured; a successful execution can have a partial capture.

## 9. Replay metadata

When an AgentCase represents a replay-derived execution, `replay` may contain:

- `mode`: `mock`, `live`, or `differential`,
- `source_case_id`,
- `replayed_at`,
- declared `substitutions`,
- `changed_provider`,
- `changed_model`,
- `changed_configuration`,
- `determinism_guarantee`: `deterministic`, `best_effort`, `none`, or `unknown`,
- `unresolved_external_dependencies`,
- `live_side_effects_approved`,
- `extensions`.

A mock replay cannot declare live side effects approved. Missing mock data must never silently cause a live call.

## 10. Security and redaction metadata

The root `redaction` object contains:

- `status`: `none`, `redacted`, `partial`, or `unknown`,
- `records`: redaction record array,
- `warnings`: warning strings,
- `potentially_sensitive_unredacted`: boolean,
- `extensions`.

Each redaction record contains:

- `field_path`: path identifying the redacted location,
- `rule_id`: stable redaction rule identifier,
- `replacement_marker`: irreversible replacement marker,
- `irreversible`: must be `true` in v0.

Original secret values must never be stored in redaction metadata. A redaction status of `none` cannot include records; `redacted` requires at least one record.

### 10.1 Redaction field path syntax

`field_path` uses RFC 6901 JSON Pointer syntax. This is a backward-compatible clarification of the existing string field, not a wire-format version change. Path segments escape `~` as `~0` and `/` as `~1`.

Examples:

```text
/metadata/user_metadata/api_key
/events/3/payload/headers/authorization
/events/5/extensions/com.example~1adapter/v1/token
```

## 11. Extensibility

Every major core object includes an `extensions` map. Extension keys should use a collision-resistant namespace, for example:

```json
{
  "extensions": {
    "com.example.my-adapter/v1": {
      "trace_hint": "synthetic"
    }
  }
}
```

Core readers preserve extension values as JSON data but do not treat unknown extensions as verified core semantics. Unknown top-level fields are rejected to prevent accidental reinterpretation.

The Prompt 02 Capture Engine uses the project-owned root extension namespace `org.reproagent.capture/v1` for capture diagnostics such as dropped-event counts and safe degradation reasons. This extension does not change AgentCase `0.1` core semantics.

For multi-provider or multi-model executions, event-level `model.request` and `model.response` payloads are the source of truth for each interaction. Optional root provider/model metadata may only represent an explicitly declared primary value and must not be repeatedly overwritten to imply that the final interaction was the only one used.

## 12. Versioning and compatibility

The AgentCase format version is independent from the Python package version.

### Reader behavior

- Supported versions are validated normally.
- Older supported versions may be read directly or through an explicit documented migration path.
- Newer unsupported versions fail with a clear unsupported-version error.
- Malformed version fields fail.
- Readers must never silently reinterpret an incompatible version.

### Migration policy

A migration must be explicit, testable, and preserve the source artifact unless the user requests replacement. Lossy migration must report what is lost. No migration framework exists in v0 because only one format version exists.

## 13. Integrity rules

A conforming AgentCase v0 reader validates at least:

- supported format name and version,
- valid UUID identifiers,
- timezone-aware timestamps,
- unique event IDs,
- contiguous deterministic sequence numbers beginning at zero,
- valid backward-only parent references,
- valid enum values,
- strict known core fields,
- JSON-safe payload values.

## 14. Security boundary

AgentCase v0 is data only. It must not contain or require executable Python object serialization. Loading a case must not execute tools, import referenced modules, evaluate expressions, or perform network calls.

Validating or inspecting a case is never authorization to replay side effects.

## 15. Example minimal shape

```json
{
  "case_id": "11111111-1111-4111-8111-111111111111",
  "completeness": "complete",
  "created_at": "2026-07-14T00:00:00Z",
  "events": [],
  "execution_id": "22222222-2222-4222-8222-222222222222",
  "extensions": {},
  "format_name": "agentcase",
  "format_version": "0.1",
  "metadata": {
    "extensions": {},
    "integration": null,
    "model": null,
    "platform": {"machine": "x86_64", "release": "synthetic", "system": "Linux"},
    "provider": null,
    "reproagent_version": "0.1.0",
    "runtime": {"implementation": "CPython", "python_version": "3.11.0"},
    "user_metadata": {}
  },
  "outcome": "unknown",
  "redaction": {
    "extensions": {},
    "potentially_sensitive_unredacted": false,
    "records": [],
    "status": "none",
    "warnings": []
  },
  "replay": null
}
```
