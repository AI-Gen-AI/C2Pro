"""TS-UT-P0C-TEMPORAL-005 - fail-closed clause identity through the P0c projection.

The P0c orchestrator compares a revision with its parent's immutable snapshot.
These tests drive the real orchestrator so the identity policy is proven at the
event that the What Changed? read model serves, not only in the L1 diff.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from src.change_intelligence.domain.contracts import ChangeSet, SemanticChange
from src.core.tasks.ingestion_tasks import _extract_contract_clauses
from src.temporal.application.change_projection import build_change_projection_event
from src.temporal.application.revision_change_orchestrator import build_revision_analysis_events
from src.temporal.domain.document_revision import DocumentRevision
from src.temporal.domain.project_event import ProjectEvent

DOCUMENT, PROJECT, TENANT = uuid4(), uuid4(), uuid4()
SCOPE = "1. Scope. The Contractor shall execute the civil works described in Annex A in full."
PRICE = "2. Price. The contract price is EUR 1,000,000 payable in monthly instalments against valuations."
PENALTIES = "3. Penalties. Delay penalties are 0.5% of the contract price per day, capped at 10% in total."
INSURANCE = "2. Insurance. The Contractor shall maintain all-risk insurance for the full duration of works."


def _revision(number: int, parent: UUID | None, blob: str) -> DocumentRevision:
    now = datetime.now(UTC).replace(tzinfo=None)
    return DocumentRevision(
        revision_id=uuid4(), document_id=DOCUMENT, project_id=PROJECT, tenant_id=TENANT,
        rev_no=number, parent_revision_id=parent, blob_hash=blob * 64,
        blob_key=f"revisions/{blob}", valid_from=now, created_at=now,
    )


def _clauses(text: str, revision: DocumentRevision):  # noqa: ANN202
    return _extract_contract_clauses(
        document_id=DOCUMENT, project_id=PROJECT, tenant_id=TENANT,
        parsed_text=text, parsed_payload=None, revision_id=revision.revision_id,
    )


async def _v1_v2(v1_text: str, v2_text: str) -> tuple[DocumentRevision, DocumentRevision, list[ProjectEvent], list[ProjectEvent]]:
    v1 = _revision(1, None, "a")
    v1_events = await build_revision_analysis_events(
        revision=v1, clauses=_clauses(v1_text, v1), existing_events=[]
    )
    v2 = _revision(2, v1.revision_id, "b")
    v2_events = await build_revision_analysis_events(
        revision=v2, clauses=_clauses(v2_text, v2), existing_events=v1_events
    )
    return v1, v2, v1_events, v2_events


@pytest.mark.asyncio
async def test_p0_repro_projection_has_no_fabricated_modifications() -> None:
    v1_text = "\n\n".join([SCOPE, PRICE, PENALTIES])
    v2_text = "\n\n".join(
        [SCOPE, INSURANCE, PRICE.replace("2.", "3.", 1), PENALTIES.replace("3.", "4.", 1)]
    )

    v1, v2, _, events = await _v1_v2(v1_text, v2_text)

    change = next(event for event in events if event.event_type == "revision.changed")
    changes = change.payload["changeset"]["changes"]
    assert sorted(item["change_type"] for item in changes) == ["added", "renumbered", "renumbered"]
    assert change.payload["changeset"]["summary_counts"]["modified"] == 0
    assert change.payload["provenance"]["diff_engine_version"] == "p0c-structural-l1-v2"
    for item in changes:
        assert item["match_basis"] in {"exact_content", "no_counterpart"}
        assert item["match_rationale"]
    # Before evidence is the parent revision's, after evidence the new revision's.
    for ref in change.evidence_refs:
        side = ref.ref_id.rsplit(":", 1)[-1]
        expected = v1.revision_id if side == "before" else v2.revision_id
        assert ref.ref_id.startswith(f"{expected}:")
    assert change.source_revision_id == v2.revision_id


@pytest.mark.asyncio
async def test_ambiguous_identity_projects_needs_review_with_no_false_certainty() -> None:
    v1_text = "\n\n".join(
        [
            "The Contractor shall submit the monthly progress report to the Engineer for approval.",
            "The Contractor shall submit the monthly safety report to the Engineer for approval.",
        ]
    )
    v2_text = "The Contractor shall submit the monthly quality report to the Engineer for approval."

    _, _, _, events = await _v1_v2(v1_text, v2_text)

    change = next(event for event in events if event.event_type == "revision.changed")
    assert change.payload["state"] == "needs_review"
    assert change.confidence == 0.0
    assert {item["match_basis"] for item in change.payload["changeset"]["changes"]} == {"ambiguous"}


@pytest.mark.asyncio
async def test_similarity_candidate_projects_needs_review() -> None:
    v1_text = "Delay penalties are 0.5% of the contract price per day, capped at 10% in total value."
    v2_text = "Delay penalties are 1.0% of the contract price per day, capped at 10% in total value."

    _, _, _, events = await _v1_v2(v1_text, v2_text)

    change = next(event for event in events if event.event_type == "revision.changed")
    assert change.payload["state"] == "needs_review"
    (item,) = change.payload["changeset"]["changes"]
    assert item["change_type"] == "modified"
    assert item["match_basis"] == "similarity_candidate"
    assert item["needs_review"] is True
    assert change.confidence is not None and change.confidence < 1.0


@pytest.mark.asyncio
async def test_reprocessing_a_compared_revision_emits_nothing_new() -> None:
    v1_text = "\n\n".join([SCOPE, PRICE])
    v2_text = "\n\n".join([SCOPE, INSURANCE, PRICE.replace("2.", "3.", 1)])
    _, v2, v1_events, v2_events = await _v1_v2(v1_text, v2_text)

    retry = await build_revision_analysis_events(
        revision=v2, clauses=_clauses(v2_text, v2), existing_events=[*v1_events, *v2_events]
    )

    assert retry == []


def test_semantic_confidence_cannot_mask_an_inferred_pairing() -> None:
    change = SemanticChange(
        object_type="clause", change_type="modified", anchor="AUTO-003",
        before={"full_text": "a"}, after={"full_text": "b"}, semantic_summary="s",
        match_confidence=0.82, needs_review=True, confidence=0.99,
        match_basis="similarity_candidate", match_rationale="similarity 0.82",
    )
    changeset = ChangeSet(
        changeset_id=uuid4(), project_id=PROJECT, tenant_id=TENANT,
        from_revision_id=uuid4(), to_revision_id=uuid4(), changes=[change],
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )

    event = build_change_projection_event(
        changeset=changeset, document_id=DOCUMENT, source_blob_hash="a" * 64, target_blob_hash="b" * 64
    )

    assert event.confidence == 0.82
    assert event.payload["state"] == "needs_review"


def test_payload_persisted_before_match_basis_still_validates() -> None:
    legacy = {
        "changeset_id": str(uuid4()), "project_id": str(PROJECT), "tenant_id": str(TENANT),
        "from_revision_id": str(uuid4()), "to_revision_id": str(uuid4()),
        "object_scope": "contract", "layer": "L1", "created_at": "2026-09-14T10:00:00",
        "changes": [{
            "object_type": "clause", "change_type": "modified", "anchor": "AUTO-002",
            "before": {"full_text": "a"}, "after": {"full_text": "b"},
            "semantic_summary": "clause AUTO-002 text modified", "match_confidence": 1.0,
            "needs_review": False, "evidence_refs": [], "severity": None, "confidence": None,
        }],
    }

    changeset = ChangeSet.model_validate(legacy)

    assert changeset.changes[0].match_basis is None
