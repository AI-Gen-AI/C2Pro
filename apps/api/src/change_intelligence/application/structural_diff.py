"""ADR-016 L1 structural contract diff.

TS-UT-CI-DIFF-001 / TS-UT-CI-IDENT-001

Every emitted change records how its pairing was established (``match_basis``)
and why (``match_rationale``). Similarity-proposed and ambiguous outcomes are
always ``needs_review``; positional clause codes never pair clauses.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from enum import Enum
from typing import Any, cast
from uuid import UUID, uuid4

from src.change_intelligence.application.anchor_resolver import (
    AnchorMatch,
    display_anchor,
    resolve_clause_anchors,
    split_source_label,
)
from src.change_intelligence.domain.contracts import ChangeSet, ChangeType, SemanticChange
from src.documents.domain.models import Clause
from src.evidence.domain.runtime_trust import EvidenceRef, EvidenceTier


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _jsonable(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def _clause_snapshot(clause: Clause) -> dict[str, Any]:
    return cast(dict[str, Any], _jsonable(asdict(clause)))


def _evidence_for_clause(
    *,
    clause: Clause,
    revision_id: UUID,
    side: str,
) -> EvidenceRef:
    locator = f"clause_code={clause.clause_code}"
    label, _ = split_source_label(clause.full_text)
    if label is not None:
        locator = f"{locator};source_label={label}"
    if clause.text_start_offset is not None and clause.text_end_offset is not None:
        locator = f"{locator};chars={clause.text_start_offset}-{clause.text_end_offset}"
    return EvidenceRef(
        ref_id=f"{revision_id}:{clause.clause_code}:{side}",
        source="contract_clause",
        tier=EvidenceTier.WEAK,
        locator=locator,
    )


def _paired_change(
    *,
    match: AnchorMatch,
    from_revision_id: UUID,
    to_revision_id: UUID,
) -> SemanticChange | None:
    old_label, old_body = split_source_label(match.old.full_text)
    new_label, new_body = split_source_label(match.new.full_text)
    if old_body == new_body:
        if old_label == new_label:
            return None
        change_type: ChangeType = "renumbered"
        summary = (
            f"clause renumbered from {old_label or 'unnumbered'} to "
            f"{new_label or 'unnumbered'}; text unchanged"
        )
    else:
        change_type = "modified"
        summary = f"clause {match.anchor} text modified"
    return SemanticChange(
        object_type="clause",
        change_type=change_type,
        anchor=match.anchor,
        before=_clause_snapshot(match.old),
        after=_clause_snapshot(match.new),
        semantic_summary=summary,
        match_confidence=match.match_confidence,
        needs_review=match.needs_review,
        match_basis=match.basis,
        match_rationale=match.rationale,
        evidence_refs=[
            _evidence_for_clause(
                clause=match.old,
                revision_id=from_revision_id,
                side="before",
            ),
            _evidence_for_clause(
                clause=match.new,
                revision_id=to_revision_id,
                side="after",
            ),
        ],
    )


_NO_COUNTERPART = (
    "no counterpart with identical text, a stable source identifier or similar text "
    "exists in the other revision"
)
_AMBIGUOUS = (
    "more than one similar counterpart exists across the revisions, so identity is "
    "ambiguous; no pairing is asserted and the change requires review"
)


def _unpaired_fields(ambiguous: bool) -> dict[str, Any]:
    if ambiguous:
        return {
            "match_confidence": 0.0,
            "needs_review": True,
            "match_basis": "ambiguous",
            "match_rationale": _AMBIGUOUS,
        }
    return {
        "match_confidence": 1.0,
        "needs_review": False,
        "match_basis": "no_counterpart",
        "match_rationale": _NO_COUNTERPART,
    }


def _added_change(*, clause: Clause, to_revision_id: UUID, ambiguous: bool) -> SemanticChange:
    anchor = display_anchor(clause)
    return SemanticChange(
        object_type="clause",
        change_type="added",
        anchor=anchor,
        before=None,
        after=_clause_snapshot(clause),
        semantic_summary=f"clause {anchor} added",
        **_unpaired_fields(ambiguous),
        evidence_refs=[
            _evidence_for_clause(clause=clause, revision_id=to_revision_id, side="after")
        ],
    )


def _removed_change(*, clause: Clause, from_revision_id: UUID, ambiguous: bool) -> SemanticChange:
    anchor = display_anchor(clause)
    return SemanticChange(
        object_type="clause",
        change_type="removed",
        anchor=anchor,
        before=_clause_snapshot(clause),
        after=None,
        semantic_summary=f"clause {anchor} removed",
        **_unpaired_fields(ambiguous),
        evidence_refs=[
            _evidence_for_clause(
                clause=clause,
                revision_id=from_revision_id,
                side="before",
            )
        ],
    )


def diff_contract_revisions(
    project_id: UUID,
    tenant_id: UUID,
    from_revision_id: UUID,
    to_revision_id: UUID,
    old_clauses: list[Clause],
    new_clauses: list[Clause],
    *,
    fuzzy_threshold: float = 0.8,
) -> ChangeSet:
    resolution = resolve_clause_anchors(
        old_clauses,
        new_clauses,
        fuzzy_threshold=fuzzy_threshold,
    )
    changes: list[SemanticChange] = []
    for match in resolution.matched:
        change = _paired_change(
            match=match,
            from_revision_id=from_revision_id,
            to_revision_id=to_revision_id,
        )
        if change is not None:
            changes.append(change)

    ambiguous_old = {id(clause) for clause in resolution.ambiguous_old}
    ambiguous_new = {id(clause) for clause in resolution.ambiguous_new}
    changes.extend(
        _removed_change(
            clause=clause,
            from_revision_id=from_revision_id,
            ambiguous=id(clause) in ambiguous_old,
        )
        for clause in resolution.unmatched_old
    )
    changes.extend(
        _added_change(
            clause=clause,
            to_revision_id=to_revision_id,
            ambiguous=id(clause) in ambiguous_new,
        )
        for clause in resolution.unmatched_new
    )

    return ChangeSet(
        changeset_id=uuid4(),
        project_id=project_id,
        tenant_id=tenant_id,
        from_revision_id=from_revision_id,
        to_revision_id=to_revision_id,
        changes=changes,
        created_at=_utcnow(),
    )


__all__ = ["diff_contract_revisions"]
