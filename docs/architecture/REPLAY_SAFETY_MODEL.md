# Replay Safety Model

## Principle

Replay is an execution decision, not a property inferred from a recorded trace.

A future CLI must never silently upgrade a mocked replay into a live replay. Missing mocks, unresolved dependencies, or unsupported events must produce an explicit incomplete, blocked, degraded, or failed result according to the future replay contract.

## Mock Replay

Mock replay reuses recorded external interactions and avoids real provider or tool calls for interactions covered by the recording.

### Intended guarantees

- offline reproduction where all required interactions are captured and supported,
- stable use of recorded responses,
- no intentional live side effects.

### Non-guarantees

- deterministic behavior if the agent itself uses time, randomness, concurrency, local mutable state, or uncaptured dependencies,
- completeness when the original capture is partial,
- equivalence to current external services.

A mock replay with missing required external interactions must not automatically call the live dependency.

## Live Replay

Live replay executes against current providers or tools.

### Intended use

- reproduce behavior against current dependencies,
- verify whether a failure still occurs,
- inspect environmental or provider drift.

### Non-guarantees

- deterministic equivalence to the original run,
- stable model output,
- unchanged external state,
- safe side effects by default.

Live mode must be explicitly selected. Side-effecting actions require explicit user intent beyond merely opening or validating a case.

## Differential Replay

Differential replay executes the same logical case with one or more declared substitutions, such as a changed model, provider, prompt, configuration, or implementation.

The replay result must record those substitutions. Comparison must not present changed conditions as an identical replay.

Differential replay can be mock-backed, live, or mixed in future versions, but the execution plan must state which dependencies are live and what deterministic guarantees remain.

## Side-effect classes

Examples of side-effecting tools include:

- sending email or messages,
- deleting or modifying data,
- making purchases or financial transactions,
- writing to databases,
- calling mutating external APIs,
- triggering workflows, deployments, or jobs.

A future replay implementation should classify tool interactions at the adapter or replay-plan boundary. Unknown tools must not be assumed safe.

## Command boundary requirements

The future command surface must preserve these rules:

1. `mock` is fail-closed with respect to missing live interactions.
2. `live` requires explicit selection.
3. destructive or potentially destructive live actions require an additional explicit approval mechanism.
4. replay metadata records mode, source case, substitutions, changed dependencies, determinism guarantees, and unresolved external dependencies.
5. validation and inspection never execute recorded tools.

## Current implementation boundary

This milestone stores replay metadata but performs no replay. The absence of an execution engine is intentional. The safety contract is established before implementation so future convenience behavior cannot redefine the boundary silently.
