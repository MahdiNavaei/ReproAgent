## What problem does this solve?

Describe the user-visible or contract-level problem.

## What changed?

Summarize the smallest coherent change.

## Safety and compatibility

- [ ] I did not add live provider/tool fallback to mock replay.
- [ ] I did not import or execute code from AgentCase data.
- [ ] Instrumentation failures cannot replace original application/provider exceptions.
- [ ] AgentCase format or compatibility implications are documented when applicable.
- [ ] Tests and examples use synthetic data and no real secrets or customer traces.

## Verification

- [ ] `python -m pytest`
- [ ] `ruff check .`
- [ ] `ruff format --check .`
- [ ] `mypy src/reproagent`
- [ ] `python -m build`
- [ ] The tested source is persisted in the branch under review.
