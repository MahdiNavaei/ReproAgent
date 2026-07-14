# ADR 0003: Framework-neutral event model

**Status:** Accepted

## Context

Agent frameworks expose different callback, trace, message, and tool abstractions. Copying any one framework's event model into AgentCase would make portability dependent on that framework.

## Decision

Use a small normalized event envelope with stable identity, sequence, timestamp, optional parent, JSON payload, capture status, redaction status, and explicit extension data. The initial taxonomy covers execution boundaries, messages, model requests/responses, tool definitions/calls/results, exceptions, retries, and custom events.

## Alternatives considered

- Mirror OpenAI-compatible request objects: rejected as provider-specific.
- Mirror LangGraph or another framework trace model: rejected as framework-specific.
- Use only an opaque generic event type: rejected because common comparison and replay semantics would be impossible without adapter-specific knowledge.

## Consequences

Adapters must normalize common semantics and may use `custom` plus namespaced extensions for unsupported detail. Some provider-specific fidelity will remain in extension data instead of the core taxonomy.
