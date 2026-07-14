# Initial public release readiness

This checklist is the final gate before changing the repository visibility from private to public.

It is deliberately conservative. Passing CI configuration is not enough: the final `main` commit must have an observed successful GitHub Actions run.

## Product journey

The release candidate must preserve this complete local journey:

```text
Record -> AgentCase / Failure Capsule -> Mock Replay -> Diff -> Regression Test
```

Verify that:

- manual `CaptureSession` produces a valid AgentCase
- capture completeness is distinct from execution outcome
- instrumentation failure does not replace an original application/provider exception
- the opt-in OpenAI Python SDK wrapper remains instance-local and explicit
- `responses.create` and `chat.completions.create` are covered by offline fake-client tests
- mock replay fails closed for an incomplete or contract-invalid source by default
- mock replay performs no provider calls, tool execution, recorded-code imports, or live side effects
- exact, structural, and normalized diff modes remain deterministic
- regression assertions report stable difference paths
- the pytest fixture is auto-discovered when the package is installed

## AgentCase and compatibility

Verify that:

- format `0.1` remains documented accurately
- unsupported format versions are rejected rather than silently reinterpreted
- malformed event identity, ordering, and parent references are rejected
- bounded input loading remains enforced
- `.agentcase` loading remains UTF-8 JSON data-only
- no `pickle`, `eval`, dynamic recorded-code import, or arbitrary object deserialization is introduced

Any future incompatible format change requires an explicit version and migration/compatibility decision.

## Security and privacy

Verify that:

- no real API keys, tokens, customer data, private prompts, or production traces are committed
- the sensitive-key redaction regression suite covers casing and separator variants
- nearby non-sensitive keys are not broadly over-redacted by the default matcher
- documentation states that redaction is a baseline, not a secrecy or PII-removal guarantee
- documentation states that capture is not authorization for replay side effects
- no hidden telemetry or provider calls are introduced by ReproAgent
- no live side-effecting replay is enabled

Before publication, use GitHub's repository secret-scanning/security controls available to the owner and manually inspect the final diff/history for obvious credentials or private data.

## Packaging

Verify that:

- `python -m build` passes on the final release candidate
- the wheel and sdist are created from a clean checkout
- package metadata names the correct project, Python requirement, license, and version
- `LICENSE` is included in package metadata
- `README.md` is valid package long-description content
- `py.typed` is included
- the console entry point `reproagent` is installed
- optional extras `openai` and `pytest` remain explicit

Do not publish to PyPI as part of this checklist. PyPI publication is a separate owner action.

## Documentation and examples

Verify that:

- README describes implemented behavior, not stale planned milestones
- README clearly separates mock replay from live replay
- README states that diff/regression are Python APIs when no dedicated CLI exists
- OpenAI integration documentation matches the supported SDK surfaces
- examples use synthetic data only
- install, test, build, replay, diff, and regression instructions are internally consistent
- `SECURITY.md` and `CONTRIBUTING.md` are present and accurate

## CI and clean-checkout verification

On the final `main` commit, observe a successful GitHub Actions run containing:

- Ruff lint
- Ruff format check
- strict Mypy check for `src/reproagent`
- package build
- offline pytest suite on Python 3.11
- offline pytest suite on Python 3.12
- offline pytest suite on Python 3.13
- offline pytest suite on Python 3.14

The tested source must equal the committed source. Do not claim a local or CI result for changes that were not persisted in the tested commit.

## Repository state

Before publication:

- final release candidate is on `main`
- no release milestone PR remains open
- the final `main` GitHub Actions run is observed successful
- repository visibility is still private during this audit
- no GitHub Release has been created
- no package has been published to PyPI
- no billing or paid external service is required for the test suite

## Known intentional limitations

The initial release does not claim:

- transparent arbitrary-process auto-instrumentation
- Anthropic, Ollama, LangGraph, CrewAI, AutoGen, or OpenAI Agents SDK integration
- live provider replay
- side-effecting tool replay
- semantic-model diff
- dedicated diff/test CLI commands
- guaranteed secret or PII removal
- hosted storage, dashboard, database, or SaaS control plane

These are not release blockers unless the README or package metadata incorrectly claims they exist.

## Owner-only publication steps

Only after every gate above is verified against the final `main` commit:

1. Review the final repository visibility and collaborator settings.
2. Review GitHub security settings and any secret-scanning results available to the repository.
3. Re-read `README.md`, `SECURITY.md`, `CONTRIBUTING.md`, and this checklist from the final `main` commit.
4. Change repository visibility to public in GitHub settings.
5. Confirm the public repository renders the README, license, and default branch correctly.
6. Optionally create a GitHub Release only after deciding the release tag/version policy.
7. Optionally publish to PyPI only as a separate, explicit release action after verifying package ownership and release credentials.

ReproAgent automation must not perform steps 4, 6, or 7 without an explicit owner decision.
