from pathlib import Path

from reproagent.agentcase import load_agentcase, summarize_agentcase

FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_summary_reports_core_case_fields() -> None:
    case = load_agentcase(FIXTURES / "valid_minimal.agentcase")
    summary = summarize_agentcase(case)

    assert "Outcome: failure" in summary
    assert "Completeness: complete" in summary
    assert "Provider: example-provider" in summary
    assert "Model: example-model-v1" in summary
    assert "Event count: 7" in summary
    assert "Redaction status: redacted" in summary
