# Initial public release readiness

This checklist is the final gate before changing repository visibility from private to public.

It is deliberately conservative. Passing CI configuration is not enough: the tested source must equal the committed release source, and CI evidence must be reported exactly as observed.

## Product journey

The release candidate must preserve this narrow local journey:

```text
Capture -> AgentCase -> explicit local mock replay -> Diff -> Regression Test
```

Verify that:

- manual `CaptureSession` produces a valid AgentCase;
- capture completeness remains distinct from execution outcome;
- unexpected capture-side `BaseException` failures cannot replace an already-propagating application/provider exception;
- synchronous `@capture_tool` preserves normal Python invocation errors, successful return values, exception identity, and exactly-once wrapped-function execution;
- the opt-in OpenAI wrapper remains instance-local and explicit;
- real declared OpenAI SDK surfaces `OpenAI.responses.create` and `OpenAI.chat.completions.create` are covered offline through a deterministic fake HTTP transport;
- OpenAI provider calls execute exactly once and ReproAgent creates no extra provider calls;
- unsupported OpenAI request/response values are omitted without arbitrary `repr` retention and degrade completeness honestly;
- `stream=True` passes through unchanged, is not eagerly consumed, produces no fake complete `model.response`, and degrades capture completeness;
- `run_mock_replay` executes only an explicitly caller-supplied local callable;
- replay never imports or executes an entrypoint from AgentCase data;
- mock replay interaction substitution performs no provider calls, recorded-tool execution, or live fallback;
- missing, mismatched, extra, or unconsumed interactions fail closed;
- exact, structural, and normalized diff modes remain deterministic;
- AgentCase regression default volatility normalization is schema-location aware and does not hide payload fields named `timestamp`, `event_id`, or `replay`;
- the pytest fixture is auto-discovered when the package is installed.

## AgentCase and compatibility

Verify that:

- format `0.1` remains documented accurately;
- unsupported format versions are rejected rather than silently reinterpreted;
- malformed event identity, ordering, and parent references are rejected;
- bounded input loading remains enforced;
- `.agentcase` loading remains UTF-8 JSON data-only;
- no `pickle`, `eval`, dynamic recorded-code import, or arbitrary object deserialization is introduced.

Any future incompatible format change requires an explicit version and migration/compatibility decision.

## Security and privacy

Verify that:

- no real API keys, tokens, customer data, private prompts, or production traces are committed;
- redaction regression coverage includes casing and separator variants of sensitive keys;
- nearby non-sensitive keys are not broadly over-redacted by the default matcher;
- OpenAI hardening tests prove unsupported objects, custom authorization/API-key headers, and provider exception text do not persist synthetic secret originals;
- documentation states redaction is a baseline, not a secrecy or PII-removal guarantee;
- capture is not authorization for replay side effects;
- no hidden telemetry or extra provider calls are introduced by ReproAgent;
- no live side-effecting replay is enabled.

Before publication, use repository security controls available to the owner and manually inspect final diff/history for obvious credentials or private data. Connector/API visibility limitations must be stated rather than treated as evidence that a security control passed.

## Packaging

Verify that:

- `python -m build` passes on the final release candidate;
- wheel and sdist are built from the committed candidate;
- package metadata names the correct project, Python requirement, Apache-2.0 license, and version;
- `LICENSE` is included in package metadata;
- `README.md` is valid package long-description content;
- `py.typed` is included;
- console entry point `reproagent` is installed;
- optional runtime extras `openai` and `pytest` remain explicit;
- the development extra installs the declared OpenAI SDK so advertised SDK compatibility tests actually run in CI.

Do not publish to PyPI as part of this checklist. PyPI publication is a separate owner action.

## Documentation and examples

Verify that:

- README, PROJECT_CHARTER, MVP_SCOPE, SYSTEM_ARCHITECTURE, REPLAY_SAFETY_MODEL, and OpenAI integration docs describe the same implemented boundary;
- replay artifact projection is not described as application re-execution;
- explicit local `run_mock_replay` execution and its unsandboxed caller-code limitation are documented;
- mock replay is clearly separated from future live replay;
- README states diff/regression are Python APIs when no dedicated CLI exists;
- examples use synthetic data only;
- install, test, build, replay, diff, and regression instructions are internally consistent;
- `SECURITY.md` and `CONTRIBUTING.md` are present and accurate.

## CI and committed-source verification

For the release-candidate PR, observe a successful GitHub Actions run containing:

- Ruff lint;
- Ruff format check;
- strict Mypy check for `src/reproagent`;
- package build;
- offline pytest suite on Python 3.11;
- offline pytest suite on Python 3.12;
- offline pytest suite on Python 3.13;
- offline pytest suite on Python 3.14.

Merge only the source proven by that PR CI. After merge, verify persisted `main` content/commit ancestry matches the tested PR source.

The repository workflow also triggers on pushes to `main`. When tooling can observe the resulting push-triggered run, record that successful final-main evidence. If the available connector only exposes pull-request-triggered workflow runs, state that exact observability limitation and do **not** claim the push-triggered final-main run was observed.

A successful PR merge and tested-source ancestry are not permission to falsify a checklist item that specifically requires an observed push-triggered final-main run.

## Repository state

Before publication:

- final release candidate is on `main`;
- no release milestone PR remains open;
- successful release-candidate PR CI is observed;
- tested PR source equals the source merged to `main`;
- final-main push CI evidence is either observed successful or explicitly still unobserved because of a stated tooling limitation;
- repository visibility remains private during this audit;
- no GitHub Release has been created;
- no package has been published to PyPI;
- no billing or paid external service is required for the test suite.

## Known intentional limitations

The initial release does not claim:

- transparent arbitrary-process auto-instrumentation;
- async OpenAI SDK capture;
- Anthropic, Ollama, LangGraph, CrewAI, AutoGen, or OpenAI Agents SDK integration;
- live provider replay;
- side-effecting recorded-tool replay;
- sandboxing of caller-supplied local replay code;
- differential replay execution;
- semantic-model diff;
- dedicated diff/test CLI commands;
- guaranteed secret or PII removal;
- hosted storage, dashboard, database, or SaaS control plane.

These are not release blockers unless README, package metadata, or architecture documents claim they exist.

## Owner-only publication steps

Only after every gate above is verified against final `main` and any unobserved CI/security evidence is resolved by the owner:

1. Review repository visibility and collaborator settings.
2. Review GitHub security settings and secret-scanning results available to the repository owner.
3. Confirm the final push-triggered `main` workflow result in GitHub Actions when connector evidence cannot expose it.
4. Re-read `README.md`, `SECURITY.md`, `CONTRIBUTING.md`, and this checklist from final `main`.
5. Change repository visibility to public in GitHub settings.
6. Confirm the public repository renders README, license, and the default branch correctly.
7. Optionally create a GitHub Release only after deciding tag/version policy.
8. Optionally publish to PyPI only as a separate explicit action after verifying package ownership and release credentials.

ReproAgent automation must not perform visibility changes, GitHub Release creation, or PyPI publication without an explicit owner decision.
