# Replay Safety Model

## Principle

Replay is an execution decision, not a property inferred from a recorded trace. A validated AgentCase is data, never executable code.

Mock replay must never silently upgrade to a live provider or tool call. Missing recordings, request mismatches, unsupported events, and unconsumed interactions fail closed.

## Current mock replay execution

`run_mock_replay(case, entrypoint)` is the supported local execution replay contract in the initial release.

The caller explicitly supplies `entrypoint`, a local Python callable receiving `MockReplayContext`. ReproAgent never reads an executable entrypoint from AgentCase metadata, never dynamically imports recorded code, and never evaluates recorded source.

The context exposes recorded external interactions as data:

- `model_response(...)` matches the next recorded model request and returns its recorded output;
- `tool_result(...)` matches the next recorded tool call and returns a data-only `RecordedToolResult`;
- exhausted recordings do not fall back to a provider or tool;
- mismatched requests fail with `ReplayContractError`;
- a successful replay must consume every recorded model/tool interaction.

The caller-supplied callable is ordinary local Python code and is not sandboxed by ReproAgent. It may use time, randomness, local state, files, or other dependencies on its own. The deterministic safety claim is limited to external interactions explicitly routed through `MockReplayContext`.

### Intended guarantees

- recorded model/tool substitutions are used in captured order;
- no model provider is called by the replay context;
- no recorded tool is executed by the replay context;
- no AgentCase-provided code path is imported or executed;
- no live fallback exists;
- interaction mismatch and missing recordings are explicit failures.

### Non-guarantees

- deterministic behavior for caller code that uses uncaptured time, randomness, concurrency, mutable state, filesystem state, or other dependencies;
- sandboxing of caller-supplied local Python code;
- completeness when an incomplete source is explicitly allowed;
- equivalence to current external services.

## Replay artifact projection

`mock_replay(case)` and `reproagent replay ... --mock` perform a separate data-only operation. They validate the source and produce a new AgentCase containing replay provenance while retaining recorded events. They do not execute an agent.

This surface is useful for provenance and artifact workflows, but documentation must not describe it as re-executing application code.

## Incomplete captures

Complete source capture is required by default. `allow_incomplete=True` is an explicit override for investigation; it does not authorize live fallback and does not change the source completeness truth.

## Live replay

Live replay against current providers or tools is not implemented. Any future live mode must be explicitly selected and separated from mock code paths. Side-effecting actions require explicit intent beyond opening, inspecting, validating, or mock-replaying a case.

## Differential replay

Differential replay execution is not implemented. Future differential replay may declare model, provider, prompt, configuration, or implementation substitutions, but changed conditions must be recorded and must never be presented as an identical replay.

## Side-effect classes

Potentially side-effecting tools include sending messages, deleting or modifying data, making purchases, writing databases, calling mutating APIs, and triggering workflows or deployments. Unknown tools must never be assumed safe for a future live mode.

## Command boundary requirements

1. `mock` is fail closed with respect to missing live interactions.
2. `live` requires explicit future implementation and explicit selection.
3. destructive live actions require an additional explicit approval mechanism.
4. replay metadata records mode, source case, substitutions, determinism guarantees, and unresolved dependencies.
5. validation and inspection never execute recorded tools or code.
6. AgentCase metadata is never an executable entrypoint source.

## Current implementation boundary

The initial release implements explicit caller-supplied local mock replay execution and data-only replay artifact projection. It intentionally does not implement live replay, side-effecting tool replay, automatic application import, or a sandbox for arbitrary caller code.
