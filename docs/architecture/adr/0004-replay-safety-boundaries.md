# ADR 0004: Replay safety boundaries

**Status:** Accepted

## Context

Recorded tool calls can contain actions that mutate real systems. A replay feature that silently invokes live dependencies can cause damage and falsely claim deterministic behavior.

## Decision

Mock, live, and differential replay are explicit modes with recorded provenance. Mock replay is fail-closed with respect to missing live interactions. Live replay requires explicit user selection. Potentially destructive side effects require an additional explicit approval mechanism in the future replay engine.

## Alternatives considered

- Automatically fall back from mock to live calls: rejected as unsafe and semantically dishonest.
- Treat all tools as read-only unless marked otherwise: rejected because unknown tools must not be assumed safe.
- Block all future live replay: rejected because live reproduction is a core product use case when explicitly requested.

## Consequences

Replay implementation will require an execution plan and side-effect boundary before convenience features. Some replays will stop as blocked or incomplete rather than silently continuing.
