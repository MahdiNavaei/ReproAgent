# ADR 0001: Python package architecture

**Status:** Accepted

## Context

ReproAgent needs a small foundation that can evolve toward capture, replay, diff, and testing without creating empty layers or coupling the core to one framework.

## Decision

Use a `src/` layout with three initial packages: `domain`, `agentcase`, and `cli`. Dependency direction is `cli -> agentcase -> domain`. Future capability packages are added only when concrete implementation begins. Python 3.11 is the minimum supported version. Pydantic v2 is the only runtime dependency.

## Alternatives considered

- Create all future packages immediately: rejected because empty abstractions create false stability.
- Use only standard-library dataclasses: viable, but would require substantial custom validation and error plumbing for a public wire contract.
- Build around a framework SDK: rejected because it would violate framework neutrality.

## Consequences

The current package is small and explicit. Future adapters can depend on the domain without reversing dependency direction. Adding new capability packages later is an intentional architectural event.
