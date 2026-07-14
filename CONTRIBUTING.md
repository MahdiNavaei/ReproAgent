# Contributing to ReproAgent

ReproAgent is early-stage and the public contribution workflow is intentionally lightweight.

## Before contributing

- Read `docs/architecture/PROJECT_CHARTER.md` and `docs/architecture/MVP_SCOPE.md`.
- Keep changes focused on reproducible agent execution failures and regression prevention.
- Preserve the initial safety boundary: mock replay is data-only and must not become live side-effecting replay by accident.
- Do not add hosted infrastructure, hidden network calls, or provider-specific assumptions to the core domain model.
- Never commit real secrets, customer data, production prompts, or private execution traces.
- Do not let instrumentation failures replace original application or provider exceptions.

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

Keep pull requests small enough to review. Explain the user-visible or contract-level impact, and call out compatibility or security implications explicitly.

Before claiming a check passed, verify that the tested working tree is the same source persisted in the commit or branch under review.
