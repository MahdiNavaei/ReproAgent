# Initial public release readiness

This document defined the final gate used before ReproAgent's initial repository visibility change from private to public. The repository is now public; retain this file as the launch-audit baseline for the `0.1.x` line and re-apply its technical gates to future release candidates where relevant.

It is deliberately conservative. Passing CI configuration is not enough: the tested source must equal the committed release source, product and documentation contracts must agree, public-facing project metadata must be truthful, and CI evidence must be reported exactly as observed.

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
- the opt-in OpenAI wrapper remains instance local and explicit;
- real declared OpenAI SDK surfaces `OpenAI.responses.create` and `OpenAI.chat.completions.create` are covered offline through a deterministic fake HTTP transport;
- OpenAI provider calls execute exactly once and ReproAgent creates no extra provider calls;
- unsupported OpenAI request/response values are omitted without arbitrary `repr` retention and degrade completeness honestly;
- `stream=True` passes through unchanged, is not eagerly consumed, produces no fake complete `model.response`, and degrades capture completeness;
- `run_mock_replay` executes only an explicitly caller-supplied local callable;
- replay never imports or executes an entrypoint from AgentCase data;
- mock replay interaction substitution performs no provider calls, recorded-tool execution, or live fallback;
- missing, mismatched, extra, out-of-order, or unconsumed interactions fail closed;
- exact, structural, and normalized diff modes remain deterministic;
- AgentCase regression default volatility normalization is schema-location aware and does not hide payload fields named `timestamp`, `event_id`, or `replay`;
- the pytest fixture is auto-discovered when the package is installed.

## AgentCase and compatibility

Verify that:

- format `0.1` remains documented accurately;
- `case_id` identifies an artifact and `execution_id` identifies the underlying represented execution;
- data-only replay-provenance projection preserves the source `execution_id` because it does not represent a new application execution;
- unsupported format versions are rejected rather than silently reinterpreted;
- malformed event identity, ordering, and parent references are rejected;
- bounded input loading remains enforced;
- `.agentcase` loading remains UTF-8 JSON data only;
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
- no live side-effecting replay is enabled;
- `SECURITY.md` reporting language remains valid for a public repository.

Before a release, use repository security controls available to the owner and manually inspect the final diff/history for obvious credentials or private data. Connector/API visibility limitations must be stated rather than treated as evidence that a security control passed.

## Packaging and project metadata

Verify that:

- `python -m build` passes on the final release candidate;
- wheel and sdist are built from the committed candidate;
- package metadata names the correct project, Python requirement, Apache-2.0 license, and version;
- package author and maintainer identity are intentional and accurate;
- project URLs point to the canonical repository, issue tracker, and documentation entry point;
- the development-status classifier matches the actual maturity claim in README;
- `LICENSE` is included in package metadata;
- `README.md` is valid package long-description content;
- `py.typed` is included;
- console entry point `reproagent` is installed;
- optional runtime extras `openai` and `pytest` remain explicit;
- the development extra installs the declared OpenAI SDK so advertised SDK compatibility tests actually run in CI.

Do not publish to PyPI as part of this checklist. PyPI publication is a separate owner action.

## Documentation, discovery, and examples

Verify that:

- README, PROJECT_CHARTER, MVP_SCOPE, SYSTEM_ARCHITECTURE, REPLAY_SAFETY_MODEL, AgentCase spec, and OpenAI integration docs describe the same implemented boundary;
- replay artifact projection is not described as application re-execution;
- replay-projection identity semantics agree with AgentCase `case_id` and `execution_id` definitions;
- explicit local `run_mock_replay` execution and its unsandboxed caller-code limitation are documented;
- mock replay is clearly separated from future live replay;
- README states diff/regression are Python APIs when no dedicated CLI exists;
- README explains the problem before presenting the full implementation inventory;
- README clearly distinguishes ReproAgent from logs/tracing without claiming to replace observability;
- project status, roadmap, intentional limitations, maintainer identity, and support paths are visible without overclaiming maturity;
- examples use synthetic data only;
- install, test, build, replay, diff, and regression instructions are internally consistent;
- `SECURITY.md`, `CONTRIBUTING.md`, `SUPPORT.md`, and `docs/ROADMAP.md` are present and accurate;
- issue forms warn against uploading real secrets or private AgentCases;
- no dead or unverified funding destination is advertised.

## Sustainability and sponsorship readiness

The project should make ongoing maintenance legible without turning the README into a fundraising page.

Verify that:

- the README communicates a concrete recurring developer problem and the value of turning failures into regression assets;
- the roadmap shows focused maintenance work rather than an unbounded framework checklist;
- support guidance explains how sanitized failure reports and compatibility work help the project;
- sponsorship is described as support for maintenance, SDK compatibility, security review, AgentCase compatibility, regression fixtures, and carefully scoped integrations;
- sponsorship is not described as pay-to-merge or permission to bypass safety and compatibility contracts;
- `.github/FUNDING.yml` references only an official maintainer-approved funding destination;
- only GitHub-displayed or repository-committed funding links are described as official.

## CI and committed-source verification

For a release-candidate PR, observe a successful GitHub Actions run containing:

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

A successful PR merge and tested-source ancestry are not permission to falsify a checklist item that specifically requires observed evidence.

## Repository state

For the initial publication audit, verify that:

- the final release candidate is on `main`;
- no release milestone PR remains open;
- successful release-candidate PR CI is observed;
- tested PR source equals the source merged to `main`;
- final-main push CI evidence is either observed successful or explicitly still unobserved because of a stated tooling limitation;
- repository visibility remained private while the pre-publication audit was still in progress;
- no GitHub Release was created as part of the audit;
- no package was published to PyPI as part of the audit;
- no billing or paid external service was required for the test suite.

After the owner changes visibility, verify that the repository is public, the default branch remains `main`, README and license render from the intended branch, funding configuration is committed, and no accidental release PR remains open.

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

## Owner actions outside repository automation

Repository automation must not silently perform account, billing, credential, or package-registry actions that require separate owner intent.

For the initial publication and future release administration, the owner is responsible for:

1. Reviewing repository visibility and collaborator settings.
2. Reviewing GitHub security settings and secret-scanning results available to the repository owner.
3. Confirming push-triggered `main` workflow results in GitHub Actions when connector evidence cannot expose them.
4. Re-reading public-facing policy and support files from the final default branch.
5. Confirming the public repository renders README, badges, license, issue forms, and default branch correctly.
6. Verifying the GitHub Sponsors profile/payment destination associated with `.github/FUNDING.yml` before relying on sponsorship revenue.
7. Optionally creating a GitHub Release only after deciding tag/version policy.
8. Optionally publishing to PyPI only as a separate explicit action after verifying package ownership and release credentials.

ReproAgent automation must not perform billing changes, funding-account activation, GitHub Release creation, or PyPI publication without an explicit owner decision and a tool that safely supports the requested action.
