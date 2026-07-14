# Security and Redaction Baseline

## Security posture

An AgentCase may contain credentials, personal data, customer content, private prompts, retrieved documents, tool output, filesystem paths, exception text, and operational metadata. The default assumption is that captured execution data is sensitive.

Redaction metadata is evidence about redaction activity; it is not proof that an artifact contains no secrets.

## Threat surface

### Secrets in process and environment data

Capture integrations may encounter API keys, bearer tokens, authorization headers, cookies, connection strings, passwords, private keys, and environment variables.

The current manual Capture Engine does **not** dump the process environment, shell history, or arbitrary local files. If a user explicitly includes environment-like data in captured metadata or event payloads, that data passes through the same redaction pipeline before retention.

### Secrets in arbitrary payloads

Credentials may appear inside message content, tool arguments, tool results, exception text, URLs, headers, or nested JSON. Redaction therefore cannot rely only on field names.

### PII and customer data

User prompts, retrieved documents, and tool output can contain personal or regulated data. ReproAgent records whether redaction rules fired and marks capture-generated cases as potentially containing sensitive unredacted content. It does not claim automated PII elimination.

### Malicious serialized payloads

`.agentcase` is data only. The loader accepts bounded UTF-8 JSON and validates it against strict models. It does not use `pickle`, `eval`, `exec`, YAML object constructors, arbitrary imports, or dynamic class loading.

This boundary reduces code-execution risk but does not prove that every downstream renderer or future integration is safe. Consumers must continue treating strings and extension data as untrusted.

### Unsafe replay

A captured tool call can represent a destructive action. The existence of recorded arguments is not authorization to execute them again.

> Capturing data is not permission to replay side effects.

### Accidental live side effects

Current mock replay is fail closed and has no live provider or recorded-tool fallback. Any future live replay mode must remain a separate explicit execution decision and must never be inferred from opening, validating, inspecting, diffing, or mock-replaying an AgentCase.

The explicit local `run_mock_replay` entrypoint is caller-supplied ordinary Python and is not sandboxed. ReproAgent guarantees recorded substitution only for interactions routed through `MockReplayContext`; callers remain responsible for their own code outside that context.

## Implemented redaction baseline

The current implementation applies best-effort redaction before observed capture data is retained by the AgentCase builder.

### Structured sensitive-key redaction

Sensitive-key matching canonicalizes casing and common separators while retaining exact canonical-name matching. This covers common forms including:

- `authorization` and casing/separator variants;
- `proxy-authorization`;
- `api_key` / `api-key` / `apiKey`;
- `x-api-key`;
- `token`;
- `access_token`;
- `refresh_token`;
- `password` / `passwd`;
- `secret`;
- `client_secret`;
- `cookie` / `set-cookie`;
- `connection_string`.

Nearby names such as `token_count`, `secretary`, and `authorization_mode` are not broadly redacted merely because they contain a sensitive substring.

The matching is intentionally conservative and is not a complete secret scanner.

### String-pattern redaction

The default implementation includes conservative high-confidence patterns for:

- bearer-token shaped strings;
- `sk-...` style API keys.

Users and future adapters can add string rules without replacing the defaults.

### Recursive behavior

The redactor traverses JSON-safe dictionaries and lists, produces new values rather than mutating caller-owned input objects, and records only:

- the redacted field path;
- the rule identifier;
- the irreversible replacement marker.

Original secret values are never copied into redaction metadata.

## Redaction field paths

AgentCase `0.1` uses RFC 6901 JSON Pointer syntax for `RedactionRecord.field_path`.

Examples:

```text
/metadata/user_metadata/api_key
/events/3/payload/headers/authorization
/events/5/extensions/com.example~1adapter/v1/token
```

The `~` and `/` characters in path segments are escaped according to JSON Pointer rules.

This is a backward-compatible clarification of the existing `field_path` string contract and does not change AgentCase format version `0.1`.

## Fail-closed behavior

If redaction fails for an observed event:

- the known raw event payload is not retained by default;
- the event is counted as dropped;
- capture completeness becomes at least `partial`;
- a safe diagnostic records the event type and failure category;
- the secret or raw payload is not copied into diagnostics.

If explicit user metadata cannot be redacted during session construction, Capture Session creation fails rather than retaining the raw metadata.

## Provider-integration normalization boundary

The synchronous OpenAI adapter does not retain unsupported request or response objects through arbitrary `repr` strings. Unsupported values are omitted and capture completeness is degraded with a constant safe diagnostic reason.

Synchronous `stream=True` results are passed through unchanged and are not eagerly consumed or represented as a complete `model.response` before stream consumption. Capture completeness is degraded because streaming event capture is unsupported in the initial release.

Provider exceptions remain primary. ReproAgent makes no additional provider call to recover capture data.

## Capture diagnostics

Capture-specific health data uses the namespaced root extension:

```text
org.reproagent.capture/v1
```

It may contain warnings, redaction/normalization failure categories, dropped-event counts, and degraded reasons. This extension is data and is not verified AgentCase core semantics.

## Exception capture

Exceptions are normalized into text fields such as exception type, message, and optional textual traceback. ReproAgent does not serialize exception objects, frame locals, or arbitrary attached attributes.

Exception messages and traceback text still pass through redaction, but filesystem paths and application details may remain sensitive.

## Atomic local persistence

Capture-generated AgentCases are serialized completely into a temporary file in the destination directory, flushed, fsynced, and then published. Existing targets are not overwritten unless the caller explicitly selects overwrite behavior.

This prevents an interrupted normal write from leaving a target path that looks like a complete AgentCase while containing only partially written bytes. It is not a stronger durability guarantee for every filesystem, network share, or storage layer.

## Current guarantees and non-guarantees

The current implementation establishes and tests:

- strict data validation;
- bounded default AgentCase loading;
- data-only JSON parsing;
- no arbitrary Python-object deserialization;
- no automatic environment dump;
- redaction-before-retention for Capture Session payloads and explicit user metadata;
- separator/casing sensitive-key regression coverage;
- fail-closed handling for tested redaction failures;
- original-secret absence in tested serialized outputs and redaction metadata;
- unsupported OpenAI-object omission without arbitrary `repr` retention;
- synthetic authorization/API-key and provider-exception secret absence in OpenAI hardening tests;
- no hidden network calls in the manual capture path;
- no extra provider calls introduced by the OpenAI adapter.

It does **not** guarantee:

- removal of every secret;
- removal of PII;
- that an AgentCase is safe to publish;
- that every future integration has the same capture coverage;
- sandboxing of caller-supplied local replay code;
- that a validated AgentCase is safe to use as authorization for side effects.
