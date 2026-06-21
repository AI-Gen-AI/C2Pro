"""TS-QA-SWAGGER-ANALYSIS-004: /analyze returns an honest preview contract."""

from __future__ import annotations

from src.analysis.adapters.http.router import AnalyzeResponse


def test_analyze_response_marks_non_persisted_preview() -> None:
    response = AnalyzeResponse(
        project_id="project-1",
        analysis_id=None,
        risks=[],
        wbs=[],
        human_approval_required=True,
        doc_type="contract",
        confidence_score=0.42,
        critique_notes="Critique retry required",
        retry_count=1,
        messages=[],
    )

    assert response.persisted is False
    assert response.mode == "preview"
    assert "not persisted" in response.persistence_message.lower()
    assert "alerts" in response.persistence_message.lower()
