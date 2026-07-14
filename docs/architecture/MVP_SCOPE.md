# MVP Scope

## Product flow

The intended MVP workflow is:

```bash
reproagent record python my_agent.py
reproagent inspect failure.agentcase
reproagent replay failure.agentcase
reproagent diff baseline.agentcase candidate.agentcase
reproagent test cases/
```

The current repository implements `--version`, `validate`, and `inspect`, plus explicit manual Python capture through `reproagent.capture`. The `record`, `replay`, `diff`, and `test` commands remain planned contracts and are not implemented.

## Capture scope

The current manual Capture Engine can explicitly represent execution metadata, ordered events, messages, model requests and responses, tool definitions and calls, tool results and failures, retries, exceptions, latency when observed, token usage when provided, provider and model identifiers, timestamps, parent-child relationships, execution outcome, capture completeness, diagnostics, and redaction metadata.

The first supported integration is explicit framework-neutral Python instrumentation. Automatic provider/framework interception is not implemented. Future adapters must emit through the same capture contract; no framework is permitted to define the core event model.

## Replay scope

Three replay modes are in scope:

- **Mock replay:** reuse recorded external interactions where possible; intended for deterministic offline reproduction.
- **Live replay:** execute against current providers or tools; inherently dependent on current external state.
- **Differential replay:** execute the same logical case with an intentional change to model, provider, configuration, prompt, or implementation.

The foundation defines replay metadata and safety boundaries only. It performs no replay.

## Diff scope

Future comparison must support metadata, event sequence, model selection, content, tool selection, arguments, results, exceptions, outcomes, latency, token usage, and structural or semantic divergence.

Comparison levels are distinct:

1. exact equality
2. structural equality
3. normalized equality
4. semantic comparison

Semantic comparison is optional and may later use a model, but it must never be the only comparison path.

## Regression scope

Recorded cases must eventually support assertions for outcome, failure class, required or forbidden tool use, tool arguments, output schema, deterministic predicates, latency, cost, and secret exposure. The design should permit a future pytest integration without making pytest a runtime dependency of the core package.

## Explicit non-goals

The initial MVP does not include SaaS, hosted control planes, accounts, authentication, RBAC, teams, billing, Kubernetes, distributed tracing backends, centralized telemetry, dashboards, web UI, multi-tenancy, enterprise policy engines, prompt management, a model gateway, a generic agent framework, a generic evaluation platform, arbitrary remote code execution, browser automation, automatic cloud upload, or a proprietary hosted requirement.

## Scope guardrail

A proposed feature belongs in ReproAgent only when it directly improves one or more of these capabilities: reproducing agent executions, inspecting failures, replaying safely, comparing executions, or preventing regressions.
