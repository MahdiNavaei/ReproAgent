# Security Policy

ReproAgent handles execution records that may contain secrets, credentials, personal data, private prompts, retrieved documents, and sensitive tool output. Treat every `.agentcase` as sensitive unless you have independently verified otherwise.

## Reporting a vulnerability

Report suspected vulnerabilities privately to the repository owner. Use GitHub private vulnerability reporting when it is available for this repository; otherwise use an available private communication channel to contact the maintainer.

Do not open a public issue containing exploit details, real secrets, customer data, or private execution traces before the maintainer has had a reasonable opportunity to investigate.

Use synthetic reproductions whenever possible.

## Current security boundary

The current implementation loads bounded UTF-8 JSON data only. It does not use `pickle`, `eval`, dynamic imports, or arbitrary object deserialization for `.agentcase` files. Validation rejects malformed or unsupported cases.

Mock replay never imports an entrypoint from AgentCase data, calls a model provider, or executes a recorded tool. Explicit local replay code is supplied directly by the caller and is ordinary unsandboxed Python; the replay safety guarantee applies to interactions routed through `MockReplayContext`.

These controls reduce risk; they do not make untrusted files harmless and they do not guarantee redaction of every secret or PII class. Capturing data is not permission to replay side effects.
