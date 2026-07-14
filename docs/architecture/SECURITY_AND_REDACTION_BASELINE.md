# Security and Redaction Baseline

## Security posture

An AgentCase may contain credentials, personal data, customer content, private prompts, retrieved documents, tool output, and operational metadata. The default assumption is that captured execution data is sensitive.

Redaction metadata is evidence about redaction activity; it is not proof that an artifact contains no secrets.

## Threat surface

### Secrets in process and environment data

Capture integrations may encounter API keys, bearer tokens, authorization headers, cookies, connection strings, passwords, private keys, and environment variables. Integrations must minimize collection and apply configured redaction before persistence where possible.

### Secrets in arbitrary payloads

Credentials may appear inside message content, tool arguments, tool results, exception text, URLs, headers, or nested JSON. Redaction therefore cannot rely only on field names.

### PII and customer data

User prompts, retrieved documents, and tool output can contain personal or regulated data. ReproAgent v0 records whether redaction occurred and whether potentially sensitive unredacted content may remain. It does not claim automated PII elimination.

### Malicious serialized payloads

`.agentcase` is data only. The loader accepts bounded UTF-8 JSON and validates it against strict models. It does not use `pickle`, `eval`, `exec`, YAML object constructors, arbitrary imports, or dynamic class loading.

This boundary reduces code-execution risk but does not prove that every downstream renderer or future integration is safe. Consumers must continue treating strings and extension data as untrusted.

### Unsafe replay

A captured tool call can represent a destructive action. The existence of recorded arguments is not authorization to execute them again.

> Capturing data is not permission to replay side effects.

### Accidental live side effects

A future replay engine must distinguish recorded/mock interactions from live execution. A mock replay may not silently fall back to a network call or tool invocation. Live actions require explicit user intent and an explicit replay mode.

## Redaction contract

AgentCase v0 provides:

- overall redaction status,
- field paths that were redacted,
- redaction rule identifiers,
- irreversible replacement markers,
- warnings,
- a flag for potentially sensitive unredacted content.

Redaction metadata must never contain the original secret value. A redaction record is invalid if it claims a reversible replacement in AgentCase v0.

Suggested replacement markers are stable opaque values such as `[REDACTED:api-key]`. The marker must not encode the secret.

## Future extension points

Future capture adapters may provide redaction rules for structured fields and content scanners. The core should accept redaction reports through the domain contract without depending on a specific secret-scanning vendor.

A future policy layer may classify side effects or enforce organization rules, but no full policy engine is part of the MVP foundation.

## Current guarantees and non-guarantees

The current implementation guarantees strict data validation, bounded default input size, data-only JSON parsing, and redaction metadata invariants tested by the suite.

It does not guarantee that an AgentCase is free of secrets, that arbitrary content is harmless, or that future replay is safe merely because the case validated.
