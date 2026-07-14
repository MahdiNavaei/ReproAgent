# Contributing to ReproAgent

ReproAgent is early-stage and the public contribution workflow is intentionally lightweight.

## Before contributing

- Read `docs/architecture/PROJECT_CHARTER.md` and `docs/architecture/MVP_SCOPE.md`.
- Check `docs/ROADMAP.md` for current maintenance priorities.
- Keep changes focused on reproducible agent execution failures and regression prevention.
- Prefer a minimal reproducible failure over broad framework-support proposals.
- Preserve the replay safety boundary: mock interaction substitution must remain fail closed and must never fall back to live providers or recorded-tool execution.
- Never import or execute application code from AgentCase data. Explicit local replay code must be supplied directly by the caller.
- Do not add hosted infrastructure, hidden network calls, or provider-specific assumptions to the core domain model.
- Never commit real secrets, customer data, production prompts, or private execution traces.
- Do not let instrumentation failures replace original application or provider exceptions.

## Reporting useful failures

The most valuable issue is a small synthetic reproduction that shows where capture, replay, diff, or regression behavior becomes incorrect or hard to use.

Before attaching an AgentCase, inspect it independently and remove sensitive content. Default redaction is a baseline, not proof that an artifact is safe to publish.

Use the bug and feature issue forms when they fit. Security reports belong in the private process described by `SECURITY.md`.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
```

## Required checks

```bash
python -m pytest
ruff check .
ruff format --check .
mypy src/reproagent
python -m build
```

Add tests for behavior changes. Contract changes to `.agentcase` require corresponding specification and compatibility updates.

Provider integrations must be testable offline with fakes or controlled local doubles. Do not require real API keys, paid APIs, or live provider calls in the automated test suite.

## Pull requests

Keep pull requests small enough to review. Explain the user-visible or contract-level impact and call out compatibility or security implications explicitly.

Before claiming a check passed, verify that the tested working tree is the same source persisted in the commit or branch under review.

For support and project-sustainability guidance, see `SUPPORT.md`. Sponsorship or user demand can surface maintenance pressure, but it is never a substitute for project fit, tests, or safety review.
