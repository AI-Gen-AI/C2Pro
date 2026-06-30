"""ProjectGraph change-impact node tests (ADR-016 L3 / ADR-017 Tier-2).

TS-UT-ADR016-L3-001
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from src.analysis.domain.contracts import (
    BudgetItem,
    Citation,
    DocumentArtifact,
    RiskItem,
    WbsActivity,
)
from src.analysis.domain.node_result import NodeStatus
from src.change_intelligence.domain.change_impact_report import ChangeImpactReport


def _artifact(
    *,
    document_id: UUID,
    revision_id: UUID,
    risk_title: str = "Foundation risk",
    risk_description: str = "Existing risk",
    wbs_name: str = "Excavation",
    budget_amount: float = 100.0,
    citation_quote: str = "Original citation",
) -> DocumentArtifact:
    return DocumentArtifact(
        document_id=str(document_id),
        document_revision_id=str(revision_id),
        doc_type="contract",
        document_category="LEGAL",
        extracted_risks=[
            RiskItem(
                title=risk_title,
                description=risk_description,
                category="LEGAL",
                source="R-1",
                confidence=0.9,
            )
        ],
        extracted_wbs=[
            WbsActivity(
                code="WBS-1",
                name=wbs_name,
                description="Main work package",
            )
        ],
        bom_items=[
            BudgetItem(
                cost_code="B-1",
                name="Concrete",
                amount=budget_amount,
                currency="EUR",
            )
        ],
        citations=[
            Citation(
                type="clause",
                item="C-1",
                quote=citation_quote,
                found_in_source=True,
            )
        ],
    )


def _state(
    *,
    artifact: DocumentArtifact,
    repo: object,
    previous_snapshot_id: UUID | None = None,
) -> dict[str, object]:
    return {
        "project_id": uuid4(),
        "tenant_id": uuid4(),
        "trigger_event_id": None,
        "previous_snapshot_id": previous_snapshot_id,
        "changed_artifact_ids": [],
        "artifacts": [artifact],
        "artifact_repository": repo,
        "coherence_result": None,
        "impact_result": None,
        "health_result": None,
        "snapshot_id": None,
        "node_results": [],
    }


def _report_from_changeset(changeset) -> ChangeImpactReport:
    return ChangeImpactReport(
        report_id=uuid4(),
        project_id=changeset.project_id,
        tenant_id=changeset.tenant_id,
        from_revision_id=changeset.from_revision_id,
        to_revision_id=changeset.to_revision_id,
        changes=changeset.changes,
        conflicts=[],
        impact_estimate=None,
        insufficient_data_reasons=["numeric impact estimate pending ADR-017"],
        overall_confidence=None,
        evidence_refs=[],
        recommended_actions=[],
        hitl_routing="auto",
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )


class FakeArtifactRepository:
    def __init__(self, superseded: list[DocumentArtifact] | Exception) -> None:
        self.superseded = superseded
        self.calls: list[dict[str, object]] = []

    async def list_superseded_for_document(self, *, project_id, tenant_id, document_id):
        self.calls.append(
            {
                "project_id": project_id,
                "tenant_id": tenant_id,
                "document_id": document_id,
            }
        )
        if isinstance(self.superseded, Exception):
            raise self.superseded
        return self.superseded


@pytest.mark.asyncio
async def test_change_impact_no_prior_snapshot_is_honest_null_skipped() -> None:
    """TS-UT-ADR016-L3-001: no prior snapshot skips without fabricating a ChangeSet."""

    from src.analysis.adapters.graph import project_graph

    current = _artifact(document_id=uuid4(), revision_id=uuid4())
    repo = FakeArtifactRepository([])

    result = await project_graph.change_impact(
        _state(artifact=current, repo=repo, previous_snapshot_id=None)
    )

    assert result["impact_result"] is None
    assert repo.calls == []
    node_result = result["node_results"][0]
    assert node_result.status is NodeStatus.SKIPPED
    assert "no prior snapshot" in (node_result.degradation_reason or "")


@pytest.mark.asyncio
async def test_change_impact_compares_prior_and_current_extraction_payloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TS-UT-ADR016-L3-001: prior/current artifacts produce object-level changes."""

    from src.analysis.adapters.graph import project_graph

    document_id = uuid4()
    prior = _artifact(document_id=document_id, revision_id=uuid4())
    current = _artifact(
        document_id=document_id,
        revision_id=uuid4(),
        risk_description="Risk wording changed",
        wbs_name="Excavation updated",
        budget_amount=125.0,
        citation_quote="Updated citation",
    )
    captured = {}

    async def _fake_build_report(changeset, tenant_id):
        captured["changeset"] = changeset
        captured["tenant_id"] = tenant_id
        return _report_from_changeset(changeset)

    monkeypatch.setattr(project_graph, "build_change_impact_report", _fake_build_report)
    repo = FakeArtifactRepository([prior])

    result = await project_graph.change_impact(
        _state(artifact=current, repo=repo, previous_snapshot_id=uuid4())
    )

    report = result["impact_result"]
    assert isinstance(report, ChangeImpactReport)
    assert result["node_results"][0].status is NodeStatus.OK
    assert captured["changeset"].from_revision_id == UUID(prior.document_revision_id)
    assert captured["changeset"].to_revision_id == UUID(current.document_revision_id)
    assert captured["tenant_id"] == captured["changeset"].tenant_id
    changes = captured["changeset"].changes
    assert {change.object_type for change in changes} == {
        "risk",
        "wbs_activity",
        "budget_item",
        "citation",
    }
    assert {change.change_type for change in changes} == {"modified"}
    assert {change.anchor for change in changes} == {"R-1", "WBS-1", "B-1", "C-1"}


@pytest.mark.asyncio
async def test_change_impact_identical_prior_yields_empty_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TS-UT-ADR016-L3-001: identical artifacts compare honestly as an empty ChangeSet."""

    from src.analysis.adapters.graph import project_graph

    document_id = uuid4()
    prior = _artifact(document_id=document_id, revision_id=uuid4())
    current = prior.model_copy(update={"document_revision_id": str(uuid4())})

    async def _fake_build_report(changeset, tenant_id):
        return _report_from_changeset(changeset)

    monkeypatch.setattr(project_graph, "build_change_impact_report", _fake_build_report)

    result = await project_graph.change_impact(
        _state(
            artifact=current,
            repo=FakeArtifactRepository([prior]),
            previous_snapshot_id=uuid4(),
        )
    )

    report = result["impact_result"]
    assert isinstance(report, ChangeImpactReport)
    assert report.changes == []
    assert result["node_results"][0].status is NodeStatus.OK


@pytest.mark.asyncio
async def test_change_impact_uses_report_builder_for_l2_enrichment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TS-UT-ADR016-L3-001: modified changes flow through the ADR-016 report builder."""

    from src.analysis.adapters.graph import project_graph

    document_id = uuid4()
    prior = _artifact(document_id=document_id, revision_id=uuid4())
    current = _artifact(
        document_id=document_id,
        revision_id=uuid4(),
        risk_description="Materially worse risk allocation",
    )

    async def _fake_build_report(changeset, tenant_id):
        enriched = [
            change.model_copy(update={"severity": "high", "confidence": 0.82})
            for change in changeset.changes
        ]
        return _report_from_changeset(changeset.model_copy(update={"changes": enriched}))

    monkeypatch.setattr(project_graph, "build_change_impact_report", _fake_build_report)

    result = await project_graph.change_impact(
        _state(
            artifact=current,
            repo=FakeArtifactRepository([prior]),
            previous_snapshot_id=uuid4(),
        )
    )

    report = result["impact_result"]
    assert isinstance(report, ChangeImpactReport)
    assert report.changes[0].severity == "high"
    assert report.changes[0].confidence == 0.82


@pytest.mark.asyncio
async def test_change_impact_load_failure_returns_failed_node_result() -> None:
    """TS-UT-ADR016-L3-001: repository failures are explicit ErrorRecord failures."""

    from src.analysis.adapters.graph import project_graph

    current = _artifact(document_id=uuid4(), revision_id=uuid4())

    result = await project_graph.change_impact(
        _state(
            artifact=current,
            repo=FakeArtifactRepository(RuntimeError("artifact store down")),
            previous_snapshot_id=uuid4(),
        )
    )

    assert result["impact_result"] is None
    node_result = result["node_results"][0]
    assert node_result.status is NodeStatus.FAILED
    assert node_result.error is not None
    assert node_result.error.node == "change_impact"
    assert node_result.error.error_type == "RuntimeError"
    assert "artifact store down" in node_result.error.message
