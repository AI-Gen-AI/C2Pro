"""PQ-HITL-04B3: source membership must be derived from immutable candidate."""

from uuid import uuid4

import pytest

from src.analysis.domain.contracts import DocumentArtifact, RiskItem
from src.analysis.domain.trust import artifact_digest
from src.modules.hitl.domain.finding_decision import (
    CandidateReviewIdentity,
    FindingDecisionKind,
)
from src.modules.hitl.domain.finding_source_membership import (
    UnverifiedFindingSource,
    resolve_finding_source,
)


def _case():
    tenant, row, document, revision, artifact = (uuid4() for _ in range(5))
    value = DocumentArtifact(
        document_id=str(document),
        document_revision_id=str(revision),
        doc_type="contract",
        extracted_risks=[
            RiskItem(
                title="14-day rectification",
                description="Verify cost and timeframe against clause 5.2",
                category="QUALITY",
            ),
            RiskItem(title="Delay in delivery", description="Unverified impact"),
        ],
    )
    candidate = CandidateReviewIdentity(
        tenant_id=tenant,
        review_row_id=row,
        document_id=document,
        document_revision_id=revision,
        artifact_id=artifact,
        artifact_version=1,
        artifact_hash=artifact_digest(value.model_dump(mode="json")),
        generation=3,
        fencing_token=10,
        thread_id="document:doc:g3:f10:analysis",
        checkpoint_id="cp-1",
    )
    return candidate, value


def test_proves_risk_index_and_immutable_candidate_digest() -> None:
    candidate, value = _case()
    first = resolve_finding_source(
        candidate=candidate,
        artifact=value,
        kind=FindingDecisionKind.RISK,
        ordinal=0,
    )
    assert first.source_item_id.startswith("risk:0:")
    assert first.source_ordinal == 0
    assert first.finding_kind is FindingDecisionKind.RISK
    assert first.source_item_id == resolve_finding_source(
        candidate=candidate,
        artifact=value,
        kind=FindingDecisionKind.RISK,
        ordinal=0,
    ).source_item_id
    second = resolve_finding_source(
        candidate=candidate,
        artifact=value,
        kind=FindingDecisionKind.RISK,
        ordinal=1,
    )
    assert first.source_item_id != second.source_item_id


def test_wrong_revision_document_or_digest_fail_closed() -> None:
    candidate, value = _case()
    for field, invalid in (
        ("document_id", uuid4()),
        ("document_revision_id", uuid4()),
        ("artifact_hash", "f" * 64),
    ):
        modified = candidate.model_copy(update={field: invalid})
        with pytest.raises(UnverifiedFindingSource):
            resolve_finding_source(
                candidate=modified,
                artifact=value,
                kind=FindingDecisionKind.RISK,
                ordinal=0,
            )


def test_out_of_range_and_nonexistent_risks_are_not_invented() -> None:
    candidate, value = _case()
    for index in (-1, 2, 100):
        with pytest.raises(UnverifiedFindingSource):
            resolve_finding_source(
                candidate=candidate,
                artifact=value,
                kind=FindingDecisionKind.RISK,
                ordinal=index,
            )


def test_unstructured_critique_cannot_be_mistaken_for_a_risk() -> None:
    candidate, value = _case()
    with pytest.raises(UnverifiedFindingSource):
        resolve_finding_source(
            candidate=candidate,
            artifact=value,
            kind=FindingDecisionKind.CRITIQUE,
            ordinal=0,
        )
