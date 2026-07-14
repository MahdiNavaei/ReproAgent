# MVP Scope

## Product flow

The implemented initial-release workflow is intentionally split between explicit Python APIs and a thin CLI:

```text
CaptureSession / selected adapter
            ↓
        AgentCase
            ↓
 inspect / validate
            ↓
 explicit run_mock_replay(case, caller_supplied_entrypoint)
            ↓
 deterministic diff
            ↓
 AgentCase regression assertion / pytest fixture
```

Implemented CLI commands are `--version`, `validate`, `inspect`, and data-only replay artifact projection through `replay --mock --output`. There is no `record python`, `diff`, or `test` CLI command in this release. Diff and regression are Python APIs.

## Capture scope

The Capture Engine explicitly represents execution metadata, ordered events, messages, model requests and responses, tool definitions and calls, tool results and failures, retries, exceptions, latency when observed, token usage when provided, provider and model identifiers, timestamps, parent-child relationships, execution outcome, capture completeness, diagnostics, and redaction metadata.

The framework-neutral manual API is the baseline. `@capture_tool` instruments synchronous Python functions while preserving wrapped-function return and exception behavior. The first provider adapter is the explicit instance-local synchronous OpenAI Python SDK wrapper for `responses.create` and `chat.completions.create`.

OpenAI streaming responses are passed through unchanged and not eagerly consumed. They do not produce a fake complete `model.response`; capture completeness is degraded explicitly. Unsupported request or response values are omitted rather than serialized through arbitrary `repr`.

## Replay scope

The initial release has two mock replay surfaces with different purposes.

### Explicit local replay execution

`run_mock_replay(case, entrypoint)` re-executes one explicitly caller-supplied local Python callable. The callable receives `MockReplayContext` and must request recorded model outputs or tool results through that context.

The runner:

- validates the source replay contract;
- never imports code or an entrypoint from AgentCase data;
- never calls a model provider;
- never executes a recorded tool;
- matches requested interactions against the next recorded interaction;
- fails closed on missing, mismatched, extra, or unconsumed interactions;
- has no live fallback.

The caller-supplied callable is ordinary local Python code and is not sandboxed by ReproAgent. The replay guarantee applies to external interactions requested through `MockReplayContext`.

### Replay artifact projection

`mock_replay(case)` and `reproagent replay ... --mock` produce a new AgentCase with explicit replay provenance while copying validated recorded events as data. This is an artifact/provenance operation, not execution of application code.

### Future replay modes

Live provider/tool replay and differential replay execution remain out of scope. Live behavior must never be selected implicitly from mock replay.

## Diff scope

The implemented comparison layers are:

1. exact equality;
2. structural equality;
3. normalized equality.

Normalized comparison documents its deterministic string and floating-point normalization. Semantic comparison is not implemented and must never become the only comparison path.

## Regression scope

`compare_agentcases()` and `assert_agentcase_regression()` compare validated AgentCases. Default volatility normalization is schema-location aware: root case/execution identity, root creation/replay provenance, and event-envelope identity/parent/timestamps are removed at known paths only. A business payload field named `timestamp`, `event_id`, or `replay` remains comparison data.

The optional pytest integration provides the auto-discovered `agentcase_regression` fixture without making pytest a core runtime dependency.

## Explicit non-goals

The initial release does not include SaaS, hosted control planes, accounts, authentication, RBAC, teams, billing, Kubernetes, distributed tracing backends, centralized telemetry, dashboards, web UI, multi-tenancy, enterprise policy engines, prompt management, a model gateway, a generic agent framework, arbitrary remote code execution, browser automation, automatic cloud upload, transparent arbitrary-process recording, async OpenAI capture, live provider replay, side-effecting tool replay, or semantic-model diff.

## Scope guardrail

A proposed feature belongs in ReproAgent only when it directly improves reproducing agent executions, inspecting failures, replaying safely, comparing executions, or preventing regressions.
