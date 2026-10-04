"""Provenance-backed impact assessment for stored temporal changes (PR-C2).

For each change in a change event, the source entity is the one that existed
in the earlier revision (``before``), referenced generically as a
``TemporalEntityRef``. A resolver registered for its ``entity_type`` follows
*persisted* relationships to the entities that depend on it. Text similarity
and generated labels never establish a relationship.

Classification:

* CONFIRMED -- the change's identity is verified and deterministic (current
  matcher, no review needed) AND the relationship is a direct persisted link;
* CANDIDATE -- the change needs review or its matcher is unverified, or the
  relationship is an indirect hop;
* UNKNOWN   -- no resolver for the entity type, the source entity was never
  persisted or cannot be proven to belong to the revision, or no persisted
  relationship exists. UNKNOWN carries no items.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, cast
from uuid import UUID

from src.change_intelligence.domain.contracts import ObjectType
from src.evidence.domain.confidence import compose_confidence
from src.evidence.domain.runtime_trust import EvidenceRef
from src.temporal.application.change_qualification import ChangeQualification
from src.temporal.domain.entity_ref import TemporalEntityRef
from src.temporal.domain.impact import (
    ChangeImpact,
    ImpactAssessment,
    ImpactItem,
    ImpactRelationship,
    ImpactStatus,
    ImpactTarget,
)
from src.temporal.domain.project_event import ProjectEvent

# A change whose pairing is deterministic: identity was established, not inferred.
_DETERMINISTIC_BASES = frozenset({"exact_content", "source_identifier", "no_counterpart"})


@dataclass(frozen=True)
class ResolvedLink:
    target: ImpactTarget
    relationship: ImpactRelationship


@dataclass(frozen=True)
class ResolverResult:
    links: list[ResolvedLink] = field(default_factory=list)
    # The source entity provably exists as this revision's entity of this document.
    source_verified: bool = False
    reason: str | None = None


class ImpactResolver(Protocol):
    """Follows persisted relationships from one source entity type."""

    entity_type: str

    async def resolve(self, source: TemporalEntityRef) -> ResolverResult: ...


def _uuid(value: Any) -> UUID | None:
    try:
        return UUID(str(value)) if value else None
    except ValueError:
        return None


def _side_evidence(change: Mapping[str, Any], revision_id: UUID, side: str) -> list[EvidenceRef]:
    refs: list[EvidenceRef] = []
    for raw in change.get("evidence_refs") or []:
        if not isinstance(raw, Mapping):
            continue
        ref_id = str(raw.get("ref_id") or "")
        if ref_id.startswith(f"{revision_id}:") and ref_id.endswith(f":{side}"):
            refs.append(EvidenceRef.model_validate(raw))
    return refs


def _source_ref(
    change: Mapping[str, Any],
    *,
    document_id: UUID,
    from_revision: UUID,
    to_revision: UUID,
    artifact_type: str | None,
) -> TemporalEntityRef:
    """The changed entity as it existed before; an added entity has no prior identity."""
    before = change.get("before")
    if isinstance(before, Mapping):
        revision, snapshot, side = from_revision, before, "before"
    else:
        after = change.get("after")
        revision, snapshot, side = to_revision, after if isinstance(after, Mapping) else {}, "after"
    entity_id = snapshot.get("id") if side == "before" else None
    return TemporalEntityRef(
        artifact_type=artifact_type,
        document_id=document_id,
        revision_id=revision,
        entity_type=cast(ObjectType, change.get("object_type")),
        entity_id=str(entity_id) if entity_id else None,
        evidence=_side_evidence(change, revision, side),
    )


def _unknown(reason: str) -> ImpactAssessment:
    return ImpactAssessment(status=ImpactStatus.UNKNOWN, items=[], confidence=None, reason=reason)


def _identity_confidence(
    change: Mapping[str, Any], qualification: ChangeQualification
) -> float | None:
    if not qualification.identity_verified:
        return None
    match = change.get("match_confidence")
    semantic = change.get("confidence")
    values: list[float | None] = [float(match) if isinstance(match, int | float) else None]
    if semantic is not None:
        values.append(float(semantic) if isinstance(semantic, int | float) else None)
    return compose_confidence(*values)


def _deterministic(change: Mapping[str, Any], qualification: ChangeQualification) -> bool:
    return (
        qualification.identity_verified
        and change.get("needs_review") is False
        and change.get("match_basis") in _DETERMINISTIC_BASES
    )


def _assess(
    change: Mapping[str, Any],
    result: ResolverResult,
    qualification: ChangeQualification,
) -> ImpactAssessment:
    if not result.source_verified:
        return _unknown(
            result.reason or "the source entity cannot be proven to belong to this revision"
        )
    if not result.links:
        return _unknown(result.reason or "no persisted relationship to any project entity")

    identity = _identity_confidence(change, qualification)
    deterministic = _deterministic(change, qualification)
    items: list[ImpactItem] = []
    for link in result.links:
        direct = link.relationship.kind == "direct"
        status: Literal[ImpactStatus.CONFIRMED, ImpactStatus.CANDIDATE] = (
            ImpactStatus.CONFIRMED if direct and deterministic else ImpactStatus.CANDIDATE
        )
        items.append(
            ImpactItem(
                target=link.target,
                relationship=link.relationship,
                status=status,
                confidence=compose_confidence(identity, link.relationship.link_confidence),
            )
        )
    direct_links = [link for link in result.links if link.relationship.kind == "direct"]
    return ImpactAssessment(
        status=(
            ImpactStatus.CONFIRMED
            if any(item.status is ImpactStatus.CONFIRMED for item in items)
            else ImpactStatus.CANDIDATE
        ),
        items=items,
        confidence=(
            compose_confidence(
                identity, *(link.relationship.link_confidence for link in direct_links)
            )
            if direct_links
            else None
        ),
        reason=None,
    )


async def assess_change_impacts(
    *,
    event: ProjectEvent,
    qualification: ChangeQualification,
    resolvers: Mapping[str, ImpactResolver],
    artifact_type: str | None,
) -> list[ChangeImpact]:
    payload = event.payload
    raw_provenance = payload.get("provenance")
    provenance: dict[str, Any] = raw_provenance if isinstance(raw_provenance, dict) else {}
    document_id = _uuid(payload.get("document_id"))
    from_revision = _uuid(provenance.get("source_revision_id"))
    to_revision = _uuid(provenance.get("target_revision_id"))
    changeset = payload.get("changeset")
    changes = changeset.get("changes") if isinstance(changeset, dict) else None
    if (
        document_id is None
        or from_revision is None
        or to_revision is None
        or not isinstance(changes, list)
    ):
        return []

    impacts: list[ChangeImpact] = []
    for index, change in enumerate(changes):
        if not isinstance(change, Mapping) or not isinstance(change.get("object_type"), str):
            continue
        source = _source_ref(
            change,
            document_id=document_id,
            from_revision=from_revision,
            to_revision=to_revision,
            artifact_type=artifact_type,
        )
        resolver = resolvers.get(source.entity_type)
        if source.entity_id is None:
            assessment = _unknown("the source entity has no persisted identity in this revision")
        elif resolver is None:
            assessment = _unknown(
                f"no impact resolver is registered for entity type {source.entity_type}"
            )
        else:
            assessment = _assess(change, await resolver.resolve(source), qualification)
        impacts.append(
            ChangeImpact(
                change_index=index,
                change_type=str(change.get("change_type") or ""),
                source=source,
                assessment=assessment,
            )
        )
    return impacts


__all__ = [
    "ImpactResolver",
    "ResolvedLink",
    "ResolverResult",
    "assess_change_impacts",
]
