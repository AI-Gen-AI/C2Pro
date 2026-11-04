"""ProjectGraph source evidence handoff: verified quotes only, PII protected."""
from __future__ import annotations

from uuid import uuid4

import pytest

from src.analysis.domain.contracts import Citation, DocumentArtifact, RiskItem
from src.coherence.models import EnrichedCoherenceResult


@pytest.mark.asyncio
async def test_projectgraph_passes_cross_document_verified_quotes_to_engine(monkeypatch):
    from src.analysis.adapters.graph import project_graph

    captured = {}

    async def fake_engine(clauses, project_id, *, config, seed_signals, seed_coverage):
        captured["clauses"] = clauses
        captured["project_id"] = project_id
        captured["config"] = config
        return EnrichedCoherenceResult(
            overall_score=None,
            score_reason="insufficient_verified_dimensions",
            score_missing_dimensions=["BUDGET"],
        )

    monkeypatch.setattr(project_graph, "evaluate_coherence_async", fake_engine)
    project_id, tenant_id = uuid4(), uuid4()
    contract_id, schedule_id = str(uuid4()), str(uuid4())
    artifacts = [
        DocumentArtifact(
            document_id=contract_id,
            document_revision_id=str(uuid4()),
            doc_type="contract",
            citations=[
                Citation(
                    type="clause", item="5.2", found_in_source=True,
                    quote="Contractor shall deliver by 1 April 2027. Contact: director@example.com.",
                ),
                Citation(
                    type="summary", item="summary", found_in_source=False,
                    quote="The contractor may be penalized.",
                ),
            ],
            extracted_risks=[
                RiskItem(
                    title="Late delivery", description="Potential delay",
                    clause_ref="5.2", source_quote_status="VERIFIED",
                    source_quote="Contractor shall deliver by 1 April 2027. Contact: director@example.com.",
                )
            ],
        ),
        DocumentArtifact(
            document_id=schedule_id,
            document_revision_id=str(uuid4()),
            doc_type="schedule",
            citations=[
                Citation(
                    type="activity", item="Schedule!45", found_in_source=True,
                    quote="Installation completion scheduled for 26 April 2027.",
                )
            ],
        ),
    ]

    evaluation = await project_graph.evaluate_artifact_set(
        artifacts, project_id=project_id, tenant_id=tenant_id, llm_on=True
    )

    assert evaluation.summary.overall_score is None
    assert evaluation.summary.artifact_count == 2
    clauses = captured["clauses"]
    assert len(clauses) == 2  # Verified duplicate quote deduplicated; false quote omitted.
    assert {clause.data["document_id"] for clause in clauses} == {contract_id, schedule_id}
    assert all(clause.data["source_verified"] is True for clause in clauses)
    assert all("director@example.com" not in clause.text for clause in clauses)
    assert captured["config"].low_budget_mode is False


@pytest.mark.asyncio
async def test_projectgraph_rejects_unverified_extractor_prose(monkeypatch):
    from src.analysis.adapters.graph import project_graph

    async def fake_engine(clauses, project_id, *, config, seed_signals, seed_coverage):
        assert clauses == []
        return EnrichedCoherenceResult(overall_score=None, score_reason="no_source_evidence")

    monkeypatch.setattr(project_graph, "evaluate_coherence_async", fake_engine)
    artifact = DocumentArtifact(
        document_id=str(uuid4()),
        doc_type="contract",
        citations=[
            Citation(type="clause", item="4.1", found_in_source=False, quote="Unverified text")
        ],
        extracted_risks=[
            RiskItem(
                title="Risk", description="Model statement",
                source_quote_status="UNVERIFIED", source_quote="Unverified generated text",
            )
        ],
    )
    result = await project_graph.evaluate_artifact_set(
        [artifact], project_id=uuid4(), tenant_id=uuid4(), llm_on=False
    )
    assert result.summary.overall_score is None
