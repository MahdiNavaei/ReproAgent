# Support and project sustainability

ReproAgent is an independent open-source project focused on reproducible AI-agent failures and regression prevention.

## Getting help

For a reproducible bug, open a GitHub issue and include the smallest synthetic example that demonstrates the behavior.

Before attaching an `.agentcase`, inspect it independently. AgentCases may contain credentials, private prompts, customer content, filesystem paths, exception text, and sensitive tool output. Do not upload real secrets or private production traces.

For suspected vulnerabilities, follow [`SECURITY.md`](SECURITY.md) instead of opening a public issue with sensitive details.

## The most useful ways to support ReproAgent

At this stage, the highest-value support is:

- trying the project on difficult agent failures;
- reporting minimal reproducible problems;
- contributing independently sanitized or synthetic failure shapes;
- improving compatibility tests and documentation;
- sharing the project with engineers who debug agent systems;
- contributing focused fixes that preserve the safety contracts.

## Sponsoring maintenance

Long-term maintenance work includes SDK compatibility, security review, AgentCase compatibility, regression fixtures, documentation, and carefully scoped integrations.

If ReproAgent becomes useful to you or your team, sponsorship can help sustain that maintenance and make focused compatibility work easier to prioritize.

Only funding links displayed by GitHub for this repository or committed in `.github/FUNDING.yml` should be treated as official ReproAgent funding destinations. The repository does not advertise an unverified funding destination.

Sponsorship never buys unsafe replay behavior, access to private user data, hidden product telemetry, or exceptions to the project's compatibility and security boundaries.

## Feature priority is not pay-to-merge

Sponsors and users are welcome to describe real maintenance pressure and integration needs, but changes still require a clear fit with the project charter, tests, and reviewable safety boundaries.

See [`docs/ROADMAP.md`](docs/ROADMAP.md) for the current maintenance priorities.
