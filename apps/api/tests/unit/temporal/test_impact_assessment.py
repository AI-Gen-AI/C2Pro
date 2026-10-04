"""TS-UT-P0C-TEMPORAL-008 - provenance-backed impact assessment (PR-C2).

Impact follows persisted relationships from a revision-bound source entity.
CONFIRMED needs a deterministic temporal identity AND a direct relationship;
an inferred or review-required pairing is at most CANDIDATE; without a
defensible relationship the assessment is UNKNOWN with no items at all.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from src.temporal.application.change_qualification import qualify_event
from src.temporal.application.impact_assessment import (
    ResolvedLink,
    ResolverResult,
    assess_change_impacts,
)
from src.temporal.domain.entity_ref import TemporalEntityRef
from src.temporal.domain.impact import (
    EpistemicBasis,
    ImpactAssessment,
    ImpactRelationship,
    ImpactStatus,
    ImpactTarget,
)
from src.temporal.domain.project_event import ProjectEvent

DOCUMENT = uuid4()
FROM_REV = uuid4()
TO_REV = uuid4()
CLAUSE = uuid4()


def _change(**overrides: Any) -> dict[str, Any]:
    change: dict[str, Any] = {
        "object_type": "clause",
        "change_type": "modified",
        "anchor": "3",
        "before": {"id": str(CLAUSE), "full_text": "3. Penalties are 0.5% per day."},
        "after": {"id": str(uuid4()), "full_text": "3. Penalties are 1.0% per day."},
        "semantic_summary": "clause 3 text modified",
        "match_confidence": 1.0,
        "needs_review": False,
        "evidence_refs": [
            {
                "ref_id": f"{FROM_REV}:AUTO-003:before",
                "source": "contract_clause",
                "tier": "weak",
                "locator": None,
            },
            {
                "ref_id": f"{TO_REV}:AUTO-003:after",
                "source": "contract_clause",
                "tier": "weak",
                "locator": None,
            },
        ],
        "severity": None,
        "confidence": None,
        "match_basis": "source_identifier",
        "match_rationale": "stable source identifier",
    }
    change.update(overrides)
    return change


def _event(changes: list[dict[str, Any]], *, engine: str = "p0c-structural-l1-v2") -> ProjectEvent:
    now = datetime.now(UTC).replace(tzinfo=None)
    return ProjectEvent(
        event_id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        event_type="revision.changed",
        payload={
            "schema_version": 1,
            "state": "needs_review" if any(c["needs_review"] for c in changes) else "ready",
            "document_id": str(DOCUMENT),
            "change_cause": "BUSINESS_STATE_CHANGED",
            "changeset": {"changes": changes},
            "provenance": {
                "diff_engine_version": engine,
                "source_revision_id": str(FROM_REV),
                "target_revision_id": str(TO_REV),
            },
            "l3_impact": None,
        },
        source_revision_id=TO_REV,
        occurred_at=now,
        created_at=now,
    )


def _alert(status: str = "open", stale: bool | None = True) -> ImpactTarget:
    return ImpactTarget(
        entity_type="alert",
        entity_id=uuid4(),
        label="Penalty exposure",
        status=status,
        potentially_stale=stale,
    )


class _Resolver:
    """In-memory resolver for the clause entity type (port contract only)."""

    entity_type = "clause"

    def __init__(
        self, links: list[ResolvedLink], *, verified: bool = True, reason: str | None = None
    ) -> None:
        self.links = links
        self.verified = verified
        self.reason = reason
        self.seen: list[TemporalEntityRef] = []

    async def resolve(self, source: TemporalEntityRef) -> ResolverResult:
        self.seen.append(source)
        return ResolverResult(
            links=self.links if self.verified else [],
            source_verified=self.verified,
            reason=self.reason,
        )


def _direct(target: ImpactTarget, via: str = "alerts.source_clause_id") -> ResolvedLink:
    return ResolvedLink(
        target=target, relationship=ImpactRelationship(kind="direct", via=via, link_confidence=1.0)
    )


def _indirect(target: ImpactTarget) -> ResolvedLink:
    return ResolvedLink(
        target=target,
        relationship=ImpactRelationship(
            kind="indirect", via="stakeholder_wbs_raci", link_confidence=None
        ),
    )


async def _assess(event: ProjectEvent, resolver: Any) -> list[Any]:
    return await assess_change_impacts(
        event=event,
        qualification=qualify_event(event),
        resolvers={resolver.entity_type: resolver} if resolver is not None else {},
        artifact_type="contract",
    )


# --- 5-9 -----------------------------------------------------------------------


async def test_deterministic_change_with_direct_fk_is_confirmed() -> None:
    resolver = _Resolver([_direct(_alert())])

    (impact,) = await _assess(_event([_change()]), resolver)

    assert impact.assessment.status is ImpactStatus.CONFIRMED
    assert impact.assessment.basis is EpistemicBasis.DERIVED
    assert impact.assessment.confidence == 1.0
    (item,) = impact.assessment.items
    assert item.status is ImpactStatus.CONFIRMED
    assert item.relationship.kind == "direct"


async def test_review_required_change_with_same_fk_is_only_candidate() -> None:
    resolver = _Resolver([_direct(_alert())])
    change = _change(match_basis="similarity_candidate", needs_review=True, match_confidence=0.86)

    (impact,) = await _assess(_event([change]), resolver)

    assert impact.assessment.status is ImpactStatus.CANDIDATE
    assert all(item.status is ImpactStatus.CANDIDATE for item in impact.assessment.items)
    assert impact.assessment.confidence == pytest.approx(0.86)


async def test_no_relationship_is_unknown_without_items() -> None:
    (impact,) = await _assess(_event([_change()]), _Resolver([]))

    assert impact.assessment.status is ImpactStatus.UNKNOWN
    assert impact.assessment.items == []
    assert impact.assessment.confidence is None
    assert impact.assessment.reason


async def test_wrong_revision_provenance_cannot_be_confirmed() -> None:
    resolver = _Resolver(
        [_direct(_alert())], verified=False, reason="source entity is not bound to revision"
    )

    (impact,) = await _assess(_event([_change()]), resolver)

    assert impact.assessment.status is ImpactStatus.UNKNOWN
    assert impact.assessment.items == []


async def test_legacy_matcher_change_never_confirms_impact() -> None:
    resolver = _Resolver([_direct(_alert())])
    event = _event([_change(match_basis=None)], engine="p0c-structural-l1-v1")

    (impact,) = await _assess(event, resolver)

    assert impact.assessment.status is ImpactStatus.CANDIDATE
    assert impact.assessment.confidence is None


async def test_indirect_hop_is_never_confirmed_and_has_unknown_confidence() -> None:
    stakeholder = ImpactTarget(
        entity_type="stakeholder",
        entity_id=uuid4(),
        label="Engineer",
        status=None,
        potentially_stale=None,
    )
    wbs = ImpactTarget(
        entity_type="wbs_node",
        entity_id=uuid4(),
        label="1.2 Foundations",
        status=None,
        potentially_stale=None,
    )
    resolver = _Resolver([_direct(stakeholder, "stakeholders.source_clause_id"), _indirect(wbs)])

    (impact,) = await _assess(_event([_change()]), resolver)

    by_type = {item.target.entity_type: item for item in impact.assessment.items}
    assert by_type["stakeholder"].status is ImpactStatus.CONFIRMED
    assert by_type["wbs_node"].status is ImpactStatus.CANDIDATE
    assert by_type["wbs_node"].confidence is None


# --- 18-20 alert staleness --------------------------------------------------------


async def test_affected_open_alert_is_potentially_stale_and_unchanged() -> None:
    alert = _alert(status="open", stale=True)
    resolver = _Resolver([_direct(alert)])

    (impact,) = await _assess(_event([_change()]), resolver)

    (item,) = impact.assessment.items
    assert item.target.potentially_stale is True
    # Read-time only: the alert's own lifecycle status is reported, never changed.
    assert item.target.status == "open"


async def test_resolved_alert_is_not_flagged_stale() -> None:
    resolver = _Resolver([_direct(_alert(status="resolved", stale=False))])

    (impact,) = await _assess(_event([_change()]), resolver)

    assert impact.assessment.items[0].target.potentially_stale is False


async def test_unrelated_alert_is_not_in_the_assessment() -> None:
    linked = _alert()
    resolver = _Resolver([_direct(linked)])

    (impact,) = await _assess(_event([_change()]), resolver)

    assert [item.target.entity_id for item in impact.assessment.items] == [linked.entity_id]


# --- 25, 26, 30 generic contract ------------------------------------------------


async def test_source_is_a_generic_temporal_entity_ref() -> None:
    resolver = _Resolver([_direct(_alert())])

    (impact,) = await _assess(_event([_change()]), resolver)

    source = impact.source
    assert isinstance(source, TemporalEntityRef)
    assert source.entity_type == "clause"
    assert source.entity_id == str(CLAUSE)
    assert source.revision_id == FROM_REV
    assert source.document_id == DOCUMENT
    assert source.artifact_type == "contract"
    assert {ref.ref_id for ref in source.evidence} == {f"{FROM_REV}:AUTO-003:before"}
    assert resolver.seen == [source]
    assert "clause_id" not in TemporalEntityRef.model_fields


async def test_unsupported_entity_type_is_unknown_without_fabricated_target() -> None:
    change = _change(object_type="milestone", match_basis="exact_content")

    (impact,) = await _assess(_event([change]), _Resolver([_direct(_alert())]))

    assert impact.source.entity_type == "milestone"
    assert impact.assessment.status is ImpactStatus.UNKNOWN
    assert impact.assessment.items == []
    assert "milestone" in (impact.assessment.reason or "")


async def test_another_entity_type_plugs_in_without_contract_change() -> None:
    class _MilestoneResolver(_Resolver):
        entity_type = "milestone"

    target = ImpactTarget(
        entity_type="wbs_node", entity_id=uuid4(), label="M1", status=None, potentially_stale=None
    )
    resolver = _MilestoneResolver([_direct(target, "future.milestone_link")])
    change = _change(
        object_type="milestone", match_basis="exact_content", before={"id": str(uuid4())}
    )

    (impact,) = await _assess(_event([change]), resolver)

    assert impact.assessment.status is ImpactStatus.CONFIRMED
    assert impact.source.entity_type == "milestone"


async def test_added_entity_without_persisted_source_is_unknown() -> None:
    change = _change(change_type="added", before=None, match_basis="no_counterpart")

    (impact,) = await _assess(_event([change]), _Resolver([_direct(_alert())]))

    assert impact.assessment.status is ImpactStatus.UNKNOWN
    assert impact.assessment.items == []


def test_unknown_assessment_cannot_carry_items_or_confidence() -> None:
    with pytest.raises(ValueError):
        ImpactAssessment(
            status=ImpactStatus.UNKNOWN,
            items=[],
            confidence=0.5,
            reason="x",
        )


# --- PR #823 adversarial review ------------------------------------------------


async def test_direct_reference_of_unknown_strength_is_only_a_candidate() -> None:
    """A persisted reference without established strength (e.g. a rule's
    aggregated ``related_clause_ids``) proposes, never confirms, an impact."""
    related = ResolvedLink(
        target=_alert(),
        relationship=ImpactRelationship(
            kind="direct", via="alerts.related_clause_ids", link_confidence=None
        ),
    )

    (impact,) = await _assess(_event([_change()]), _Resolver([related]))

    (item,) = impact.assessment.items
    assert item.status is ImpactStatus.CANDIDATE
    assert item.confidence is None
    assert impact.assessment.status is ImpactStatus.CANDIDATE


async def test_unknown_identity_confidence_cannot_confirm() -> None:
    """A deterministic pairing with no recorded match confidence is not proven enough to confirm."""
    change = _change(match_confidence=None)

    (impact,) = await _assess(_event([change]), _Resolver([_direct(_alert())]))

    assert impact.assessment.status is ImpactStatus.CANDIDATE
    assert impact.assessment.confidence is None


async def test_confirmed_assessment_confidence_rests_on_its_confirmed_items() -> None:
    """A weaker candidate link beside a confirmed one neither confirms nor erases the confirmation."""
    related = ResolvedLink(
        target=_alert(),
        relationship=ImpactRelationship(
            kind="direct", via="alerts.related_clause_ids", link_confidence=None
        ),
    )

    (impact,) = await _assess(_event([_change()]), _Resolver([_direct(_alert()), related]))

    assert impact.assessment.status is ImpactStatus.CONFIRMED
    assert impact.assessment.confidence == 1.0
    assert [item.status for item in impact.assessment.items] == [
        ImpactStatus.CONFIRMED,
        ImpactStatus.CANDIDATE,
    ]


def test_confirmed_or_candidate_assessment_requires_an_impacted_entity() -> None:
    with pytest.raises(ValueError):
        ImpactAssessment(status=ImpactStatus.CANDIDATE, items=[], confidence=None, reason=None)


async def test_event_without_revision_provenance_yields_no_impact_claims() -> None:
    event = _event([_change()])
    event = event.model_copy(update={"payload": {**event.payload, "provenance": {}}})

    assert await _assess(event, _Resolver([_direct(_alert())])) == []


async def test_malformed_change_entries_are_skipped_not_guessed() -> None:
    event = _event([_change()])
    changes = ["not-a-change", {"change_type": "modified"}, _change()]
    event = event.model_copy(
        update={"payload": {**event.payload, "changeset": {"changes": changes}}}
    )

    impacts = await _assess(event, _Resolver([]))

    assert [impact.change_index for impact in impacts] == [2]
