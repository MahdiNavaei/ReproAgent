# Contributing to ReproAgent

ReproAgent is early-stage and the public contribution workflow is intentionally lightweight.

## Before contributing

- Read `docs/architecture/PROJECT_CHARTER.md` and `docs/architecture/MVP_SCOPE.md`.
- Keep changes focused on reproducible agent execution failures and regression prevention.
- Do not add hosted infrastructure, hidden network calls, or provider-specific assumptions to the core domain model.
- Never commit real secrets, customer data, production prompts, or private execution traces.

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
```

Add tests for behavior changes. Contract changes to `.agentcase` require corresponding specification and compatibility updates.

## Pull requests

Keep pull requests small enough to review. Explain the user-visible or contract-level impact, and call out compatibility or security implications explicitly.
