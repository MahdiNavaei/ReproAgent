# ADR 0002: AgentCase v0 serialization

**Status:** Accepted

## Context

The MVP needs a portable artifact that can be inspected, validated, versioned, and moved between compatible environments. Binary attachments are not yet a concrete requirement.

## Decision

AgentCase v0 is a single UTF-8 JSON file with deterministic canonical serialization. The reader validates a strict format header before full model validation and applies a default 16 MiB input limit.

## Alternatives considered

- ZIP container with manifest and attachments: deferred until binary attachments are required.
- JSON plus sidecar attachments: rejected for v0 because portability becomes multi-file and integrity rules become more complex.
- Pickle or arbitrary Python serialization: rejected as unsafe and language-specific.
- SQLite: rejected because the artifact must not depend on a database format or query engine.

## Consequences

The format is easy to inspect and implement outside Python. Binary payloads and compression are inefficient until a future version introduces an explicit container contract. Such a version must not be silently treated as `0.1`.
