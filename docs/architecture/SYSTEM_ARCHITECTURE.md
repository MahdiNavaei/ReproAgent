# System Architecture

## Architecture baseline

ReproAgent begins as a lightweight Python package with a portable data artifact at its center.

```text
Framework / Provider Adapters (future)
              |
              v
       Capture Normalization (future)
              |
              v
      Provider-neutral Domain Model
              |
              v
         AgentCase v0 JSON
          /      |      \
         v       v       v
      Inspect   Replay   Diff        (replay and diff are future)
                         |
                         v
                  Regression Tests    (future)
```

## Current package boundaries

### `reproagent.domain`

Owns provider-neutral, framework-neutral validated domain types and enums. It has no network behavior and no integration-specific capture logic.

### `reproagent.agentcase`

Owns the data-only `.agentcase` serialization boundary: bounded file loading, format header checks, model validation, deterministic canonical serialization, and human-readable summaries.

### `reproagent.cli`

Owns the thin local command-line adapter. It delegates validation and inspection to the core package and contains no provider logic.

Packages for capture, replay, diff, testing integration, and framework adapters are intentionally not created yet. Empty abstraction layers would imply stability that does not exist. They will be added when their first concrete implementation milestone begins.

## Dependency direction

```text
cli -> agentcase -> domain
```

The domain package does not depend on CLI or integrations. Future adapters may depend on domain contracts, but the domain must not import adapters.

## Python support baseline

The package requires Python 3.11 or newer. At the foundation date (2026-07-14), Python 3.10 is scheduled to reach end of life in October 2026, while Python 3.11 remains in security support until October 2027. Choosing 3.11 avoids starting a new public library on a runtime with only a few months of upstream support left while still covering four active interpreter lines in CI: Python 3.11 through 3.14.

## Validation approach

Pydantic v2 is the single runtime dependency. It provides typed public models, deterministic validation errors, and strict rejection of unknown schema fields. The wire format remains plain JSON and is documented independently from Pydantic.

## Artifact boundary

AgentCase v0 is UTF-8 JSON. Loading does not execute Python code or reconstruct arbitrary Python objects. Unknown top-level fields are rejected. Controlled evolution is available through explicit `extensions` maps whose values are preserved as data but are not treated as verified core semantics.

## Deterministic serialization

Canonical serialization uses:

- UTF-8
- sorted object keys
- compact separators
- no NaN or Infinity
- normalized Pydantic JSON forms for UUIDs, enums, and datetimes
- one trailing newline

Deterministic serialization means the same validated semantic model produces the same bytes under the same AgentCase format rules. It does not mean two independent live executions are behaviorally deterministic.

## Future capture architecture

Capture will be split into:

1. adapters that observe framework/provider-specific events,
2. a normalization boundary that emits core events,
3. an ordered case builder that tracks capture completeness and failures,
4. redaction before artifact persistence wherever technically possible.

Adapters must report unsupported or degraded capture explicitly instead of dropping information silently.

## Future replay architecture

Replay will consume a validated AgentCase plus an explicit replay plan. The plan selects mock, live, or differential mode and records substitutions and unresolved dependencies. Mock replay and live replay must be separate code paths at the command boundary; no fallback may silently cross that boundary.

## Future diff architecture

Diff will expose layered comparators rather than one opaque score. Exact and structural comparison remain deterministic. Normalized comparison applies documented canonicalization rules. Semantic comparison is optional and additive.

## Future test architecture

Regression assertions should operate on validated AgentCase and replay results through a small public assertion API. A future pytest plugin can be an optional integration rather than a core runtime dependency.
