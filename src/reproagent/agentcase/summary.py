"""Human-readable summaries for validated AgentCase files."""

from reproagent.domain import AgentCase


def summarize_agentcase(case: AgentCase) -> str:
    provider = case.metadata.provider.provider_id if case.metadata.provider else "unknown"
    model = case.metadata.model.model_id if case.metadata.model else "unknown"

    lines = [
        f"Case ID: {case.case_id}",
        f"Format version: {case.format_version}",
        f"Outcome: {case.outcome.value}",
        f"Completeness: {case.completeness.value}",
        f"Provider: {provider}",
        f"Model: {model}",
        f"Event count: {len(case.events)}",
        f"Created at: {case.created_at.isoformat()}",
        f"Redaction status: {case.redaction.status.value}",
        "Potentially sensitive unredacted content: "
        + ("yes" if case.redaction.potentially_sensitive_unredacted else "no"),
    ]
    return "\n".join(lines)
