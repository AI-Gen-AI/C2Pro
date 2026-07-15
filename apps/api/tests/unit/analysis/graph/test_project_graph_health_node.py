"""TS-UD-HEALTH-018-005 - Tier-2 ProjectGraph health node wiring."""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.analysis.adapters.graph.project_coherence_result import ProjectCoherenceResult
from src.analysis.domain.contracts import DocumentArtifact, RiskItem, Severity
from src.analysis.domain.documentation_health import DocumentationHealthSignal
from src.analysis.domain.node_result import NodeStatus
from src.health.domain.health_vector import HealthDimension


def _artifact(
    documentation_health_signal: DocumentationHealthSignal | None = None,
) -> DocumentArtifact:
    return DocumentArtifact(
        document_id="doc-1",
        document_revision_id=str(uuid4()),
        doc_type="contract",
        document_category="LEGAL",
        documentation_health_signal=documentation_health_signal,
        extracted_risks=[
            RiskItem(
                title="Risk",
                description="Risk description",
                severity=Severity.LOW,
            )
        ],
    )


@pytest.mark.asyncio
async def test_project_graph_health_node_populates_health_result_from_artifacts() -> None:
    from src.analysis.adapters.graph.project_graph import health

    result = health(
        {
            "project_id": uuid4(),
            "tenant_id": uuid4(),
            "artifacts": [_artifact()],
            "coherence_result": ProjectCoherenceResult(
                overall_score=80,
                category_scores={},
                signal_count=1,
                finding_count=0,
                artifact_count=1,
                llm_on=False,
            ),
            "node_results": [],
        }
    )

    health_result = result["health_result"]
    assert health_result["composite_score"] is not None
    dimensions = {item["dimension"]: item for item in health_result["dimensions"]}
    assert dimensions[HealthDimension.RISK.value]["score"] is not None
    assert dimensions[HealthDimension.CONTRACT.value]["score"] is None
    assert dimensions[HealthDimension.DOCUMENTATION.value]["score"] is None
    assert dimensions[HealthDimension.GOVERNANCE.value]["score"] is None
    assert result["node_results"][0].status is NodeStatus.OK


@pytest.mark.asyncio
async def test_project_graph_health_node_consumes_documentation_health_signal() -> None:
    """TS-ADR-013-GRAPH-001 - Degraded Tier-1 signal reaches Tier-2 documentation health."""
    from src.analysis.adapters.graph.project_graph import health

    result = health(
        {
            "project_id": uuid4(),
            "tenant_id": uuid4(),
            "artifacts": [
                _artifact(
                    DocumentationHealthSignal(
                        total_count=2,
                        failed_count=0,
                        degraded_count=1,
                        skipped_count=0,
                        degraded_nodes=["human_interrupt"],
                    )
                )
            ],
            "coherence_result": None,
            "node_results": [],
        }
    )

    dimensions = {
        item["dimension"]: item for item in result["health_result"]["dimensions"]
    }
    documentation = dimensions[HealthDimension.DOCUMENTATION.value]
    assert documentation["score"] is not None
    assert documentation["band"] != "unknown"
    assert documentation["missing_data"] == []


@pytest.mark.asyncio
async def test_project_graph_health_node_degrades_without_crashing(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.analysis.adapters.graph import project_graph

    def _explode(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("health engine unavailable")

    monkeypatch.setattr(project_graph, "assemble_health_vector", _explode, raising=False)
    result = project_graph.health(
        {
            "project_id": uuid4(),
            "tenant_id": uuid4(),
            "artifacts": [_artifact()],
            "coherence_result": None,
            "node_results": [],
        }
    )

    assert result["health_result"] is None
    assert result["node_results"][0].status is NodeStatus.DEGRADED
