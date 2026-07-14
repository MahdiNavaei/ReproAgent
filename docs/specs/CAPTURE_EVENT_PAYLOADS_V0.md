# Capture Event Payloads v0

**Status:** Initial normalized capture contract
**Applies to:** AgentCase format `0.1`
**Event envelope:** `docs/specs/AGENTCASE_SPEC_V0.md`

## 1. Purpose

AgentCase `0.1` defines a stable event envelope while leaving each `payload` as JSON data. This document defines the first normalized payload contracts emitted by the ReproAgent manual Python Capture Engine.

These contracts are provider neutral and framework neutral. Provider-specific or framework-specific detail that cannot be normalized honestly belongs in the event `extensions` map under a collision-resistant namespace.

Unknown extension data is preserved as data but is not verified core semantics.

## 2. General rules

- Payloads are JSON-safe data only.
- Missing information stays absent or `null`; capture code must not invent provider facts.
- Event order is defined by the AgentCase `sequence`, never by timestamps.
- Event payloads are redacted before they are appended to the case builder.
- Tool-call evidence is not replay authorization.
- Root `AgentCase.outcome` is authoritative for execution outcome.
- Event-level provider and model identifiers are authoritative for individual model interactions.
- Root provider/model metadata, when present, can only describe an explicitly declared primary value; it must not be rewritten repeatedly during multi-provider or multi-model runs.

## 3. `execution.start`

Normalized fields:

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `name` | string or null | no | Human-facing execution name. |
| `entrypoint` | string or null | no | Declared application entrypoint. |
| `working_directory` | string or null | no | Working directory observed at session activation. |
| `process_id` | non-negative integer | yes | Local process identifier. |

The Capture Engine does not dump environment variables, shell history, or arbitrary local files.

## 4. `execution.end`

Normalized fields:

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `outcome` | string | yes | Terminal outcome copied from the authoritative root outcome. |
| `duration_ms` | non-negative number | yes | Local monotonic elapsed duration. |
| `reason` | string or null | no | Optional explicit terminal reason. |

Construction must prevent a contradiction between this payload and the root `AgentCase.outcome`.

## 5. `message`

Normalized fields:

| Field | Type | Required |
|---|---|---:|
| `role` | non-empty string | yes |
| `content` | JSON value | yes |
| `name` | string or null | no |
| `message_id` | string or null | no |

`content` may be structured JSON. ReproAgent does not impose one provider's multimodal schema on the core payload.

## 6. `model.request`

Normalized fields:

| Field | Type | Required |
|---|---|---:|
| `provider` | non-empty string | yes |
| `model` | non-empty string | yes |
| `input` | JSON value | yes |
| `parameters` | JSON object | yes; may be empty |
| `tools` | JSON array | yes; may be empty |

Provider-specific request details may be stored in namespaced event extensions. OpenAI-compatible request shapes are not the core schema.

## 7. `model.response`

Normalized fields:

| Field | Type | Required |
|---|---|---:|
| `provider` | non-empty string | yes |
| `model` | non-empty string | yes |
| `output` | JSON value | yes |
| `finish_reason` | string or null | no |
| `usage` | JSON object or null | no |
| `latency_ms` | non-negative number or null | no |

Usage and latency are optional. ReproAgent does not estimate missing token counts and present them as provider-reported facts.

## 8. `tool.definition`

Normalized fields:

| Field | Type | Required |
|---|---|---:|
| `name` | non-empty string | yes |
| `description` | string or null | no |
| `input_schema` | JSON value or null | no |

An input schema is not fabricated when the source integration does not expose one.

## 9. `tool.call`

Normalized fields:

| Field | Type | Required |
|---|---|---:|
| `name` | non-empty string | yes |
| `call_id` | non-empty string | yes |
| `arguments` | JSON value | yes |

The `call_id` identifies the logical tool invocation within payload semantics. The event also has its independent AgentCase `event_id`.

Arguments are redacted before persistence.

## 10. `tool.result`

Normalized fields:

| Field | Type | Required |
|---|---|---:|
| `name` | non-empty string | yes |
| `call_id` | non-empty string | yes |
| `status` | `success` or `failure` | yes |
| `result` | JSON value or null | no |
| `error` | JSON value or null | required for `failure` |
| `latency_ms` | non-negative number or null | no |

The event must reference a preceding `tool.call`. Name and `call_id` must match the parent call.

A real thrown exception may additionally produce an `exception` event. A simple failure result with no observed exception should not fabricate one.

## 11. `exception`

Normalized fields:

| Field | Type | Required |
|---|---|---:|
| `exception_type` | non-empty string | yes |
| `message` | string | yes |
| `traceback` | string or null | no |
| `handled` | boolean | yes |

The Capture Engine serializes normalized text only. It does not serialize exception objects, local variables, frames, or executable Python objects.

Traceback text can expose paths and application details and remains sensitive even after default redaction.

## 12. `retry`

Normalized fields:

| Field | Type | Required |
|---|---|---:|
| `attempt` | integer >= 1 | yes |
| `reason` | string or null | no |
| `delay_ms` | non-negative number or null | no |
| `target` | string or null | no |

Retries are recorded only when explicitly observed or declared. ReproAgent does not infer framework retry semantics that were not exposed.

## 13. `custom`

`custom` payloads are JSON objects supplied by an integration or manual instrumentation when existing normalized event types cannot represent the observation honestly.

`custom` is an escape hatch, not a way to redefine an entire framework trace as opaque core semantics. Stable adapter-specific meaning should also identify itself through a namespaced extension.

## 14. Parent relationship rules used by the manual API

The first Capture Engine enforces these stronger construction rules:

- `model.response` must reference a preceding `model.request`.
- `tool.result` must reference a preceding `tool.call`.
- `tool.result.name` and `tool.result.call_id` must match the parent tool call.
- `execution.end` references the session's `execution.start`.

Other event types may use a valid earlier parent when the observation has a meaningful causal relationship.
