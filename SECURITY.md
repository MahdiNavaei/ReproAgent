# Security Policy

ReproAgent handles execution records that may contain secrets, credentials, personal data, private prompts, retrieved documents, and sensitive tool output. Treat every `.agentcase` as sensitive unless you have verified otherwise.

## Reporting a vulnerability

The project is still in an early private-repository phase and does not yet operate a dedicated security mailbox or bounty program. Until a public reporting channel exists, report suspected vulnerabilities privately to the repository owner through an available private communication channel. Do not disclose a suspected vulnerability publicly before the maintainer has had a reasonable opportunity to investigate.

Do not include real secrets or customer data in a vulnerability report. Use synthetic reproductions whenever possible.

## Current security boundary

The current implementation loads UTF-8 JSON data only. It does not use `pickle`, `eval`, dynamic imports, or arbitrary object deserialization for `.agentcase` files. Validation limits file size and rejects malformed or unsupported cases.

These controls reduce risk; they do not make untrusted files harmless. Do not assume a captured case is safe to replay. Capturing data is not permission to replay side effects.
