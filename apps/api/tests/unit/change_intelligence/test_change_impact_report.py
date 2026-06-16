"""Change-impact report tests (ADR-016 / TASK-V3-016-04).

TS-UT-CI-REPORT-001
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.change_intelligence.domain.contracts import ChangeSet, SemanticChange
from src.evidence.domain.runtime_trust import EvidenceRef, EvidenceTier


def _change(
    change_type: str,
    anchor: str,
    *,
    needs_review: bool = False,
    severity: str | None = None,
    confidence: float | None = None,
) -> SemanticChange:
    before = {"clause_code": anchor, "full_text": "Old clause text."}
    after = {"clause_code": anchor, "full_text": "New clause text."}
    if change_type == "added":
        before = None
    if change_type == "removed":
        after = None
    return SemanticChange(
        object_type="clause",
        change_type=change_type,
        anchor=anchor,
        before=before,
        after=after,
        semantic_summary=f"clause {anchor} {change_type}",
        match_confidence=0.82 if needs_review else 1.0,
        needs_review=needs_review,
        evidence_refs=[
            EvidenceRef(
                ref_id=f"clause:{anchor}",
                source="document_revision",
                tier=EvidenceTier.WEAK,
                locator=f"clause_code:{anchor}",
            )
        ],
        severity=severity,
        confidence=confidence,
    )


def _changeset(changes: list[SemanticChange]) -> ChangeSet:
    return ChangeSet(
        changeset_id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        from_revision_id=uuid4(),
        to_revision_id=uuid4(),
        changes=changes,
        created_at=datetime(2026, 6, 16, 12, 0, 0),
    )


@pytest.mark.asyncio
async def test_report_contract_is_frozen_and_summarizes_changes() -> None:
    from src.change_intelligence.domain.change_impact_report import ChangeImpactReport

    changes = [_change("added", "1.1"), _change("modified", "5.2", needs_review=True)]
    report = ChangeImpactReport(
        report_id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        from_revision_id=uuid4(),
        to_revision_id=uuid4(),
        changes=changes,
        hitl_routing="needs_review",
        created_at=datetime(2026, 6, 16, 12, 0, 0),
    )

    assert report.summary_counts == {
        "added": 1,
        "removed": 0,
        "modified": 1,
        "needs_review": 1,
    }
    with pytest.raises(ValidationError):
        report.project_id = uuid4()  # type: ignore[misc]
    with pytest.raises(ValidationError):
        ChangeImpactReport(
            report_id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            from_revision_id=uuid4(),
            to_revision_id=uuid4(),
            changes=[],
            hitl_routing="auto",
            created_at=datetime(2026, 6, 16, 12, 0, 0),
            unexpected=True,
        )


@pytest.mark.asyncio
async def test_l1_only_report_keeps_honest_nulls_and_routes_review(monkeypatch: Any) -> None:
    from src.change_intelligence.application import change_impact_report as report_module

    async def _enabled(_tenant_id: object) -> bool:
        return True

    async def _no_l2(
        changeset: ChangeSet,
        tenant_id: object,
        *,
        llm: object | None = None,
        anonymizer: object | None = None,
    ) -> ChangeSet:
        return changeset

    monkeypatch.setattr(report_module, "is_change_impact_enabled", _enabled)
    monkeypatch.setattr(report_module, "enrich_modified_changes", _no_l2)

    changeset = _changeset([_change("modified", "5.2", needs_review=True)])
    report = await report_module.build_change_impact_report(changeset, changeset.tenant_id)

    assert report.conflicts == []
    assert report.impact_estimate is None
    assert "ADR-017" in " ".join(report.insufficient_data_reasons)
    assert report.overall_confidence is None
    assert report.hitl_routing == "needs_review"
    assert report.evidence_refs
    assert report.changes[0].severity is None
    assert report.changes[0].confidence is None


@pytest.mark.asyncio
async def test_l2_enriched_high_severity_routes_to_review(monkeypatch: Any) -> None:
    from src.change_intelligence.application import change_impact_report as report_module

    async def _enabled(_tenant_id: object) -> bool:
        return True

    async def _l2(
        changeset: ChangeSet,
        tenant_id: object,
        *,
        llm: object | None = None,
        anonymizer: object | None = None,
    ) -> ChangeSet:
        enriched = [
            change.model_copy(
                update={
                    "semantic_summary": "penalty cap increased materially",
                    "severity": "high",
                    "confidence": 0.8,
                }
            )
            for change in changeset.changes
        ]
        return changeset.model_copy(update={"changes": enriched})

    monkeypatch.setattr(report_module, "is_change_impact_enabled", _enabled)
    monkeypatch.setattr(report_module, "enrich_modified_changes", _l2)

    changeset = _changeset([_change("modified", "5.2")])
    report = await report_module.build_change_impact_report(changeset, changeset.tenant_id)

    assert report.hitl_routing == "needs_review"
    assert report.overall_confidence == 0.8
    assert report.changes[0].severity == "high"
    assert report.changes[0].confidence == 0.8


@pytest.mark.asyncio
async def test_report_never_fabricates_conflicts_or_impact(monkeypatch: Any) -> None:
    from src.change_intelligence.application import change_impact_report as report_module

    async def _enabled(_tenant_id: object) -> bool:
        return True

    async def _no_l2(
        changeset: ChangeSet,
        tenant_id: object,
        *,
        llm: object | None = None,
        anonymizer: object | None = None,
    ) -> ChangeSet:
        return changeset

    monkeypatch.setattr(report_module, "is_change_impact_enabled", _enabled)
    monkeypatch.setattr(report_module, "enrich_modified_changes", _no_l2)

    changeset = _changeset([_change("added", "12.1"), _change("removed", "9.1")])
    report = await report_module.build_change_impact_report(changeset, changeset.tenant_id)

    assert report.conflicts == []
    assert report.impact_estimate is None
    assert report.insufficient_data_reasons == [
        "cross-document impact/conflicts pending ADR-017",
        "numeric impact estimate pending ADR-017",
    ]
