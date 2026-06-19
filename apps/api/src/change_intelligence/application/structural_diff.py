"""ADR-016 L1 structural contract diff.

TS-UT-CI-DIFF-001
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from src.change_intelligence.application.anchor_resolver import (
    AnchorMatch,
    resolve_clause_anchors,
)
from src.change_intelligence.domain.contracts import ChangeSet, SemanticChange
from src.documents.domain.models import Clause
from src.evidence.domain.runtime_trust import EvidenceRef, EvidenceTier


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _normalize_text(text: str | None) -> str:
    return " ".join((text or "").split())


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
    return _jsonable(asdict(clause))


def _evidence_for_clause(
    *,
    clause: Clause,
    revision_id: UUID,
    side: str,
) -> EvidenceRef:
    locator = f"clause_code={clause.clause_code}"
    if clause.text_start_offset is not None and clause.text_end_offset is not None:
        locator = f"{locator};chars={clause.text_start_offset}-{clause.text_end_offset}"
    return EvidenceRef(
        ref_id=f"{revision_id}:{clause.clause_code}:{side}",
        source="contract_clause",
        tier=EvidenceTier.WEAK,
        locator=locator,
    )


def _modified_change(
    *,
    match: AnchorMatch,
    from_revision_id: UUID,
    to_revision_id: UUID,
) -> SemanticChange:
    return SemanticChange(
        object_type="clause",
        change_type="modified",
        anchor=match.anchor,
        before=_clause_snapshot(match.old),
        after=_clause_snapshot(match.new),
        semantic_summary=f"clause {match.anchor} text modified",
        match_confidence=match.match_confidence,
        needs_review=match.needs_review,
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


def _added_change(*, clause: Clause, to_revision_id: UUID) -> SemanticChange:
    return SemanticChange(
        object_type="clause",
        change_type="added",
        anchor=clause.clause_code,
        before=None,
        after=_clause_snapshot(clause),
        semantic_summary=f"clause {clause.clause_code} added",
        match_confidence=1.0,
        evidence_refs=[
            _evidence_for_clause(clause=clause, revision_id=to_revision_id, side="after")
        ],
    )


def _removed_change(*, clause: Clause, from_revision_id: UUID) -> SemanticChange:
    return SemanticChange(
        object_type="clause",
        change_type="removed",
        anchor=clause.clause_code,
        before=_clause_snapshot(clause),
        after=None,
        semantic_summary=f"clause {clause.clause_code} removed",
        match_confidence=1.0,
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
        if _normalize_text(match.old.full_text) == _normalize_text(match.new.full_text):
            continue
        changes.append(
            _modified_change(
                match=match,
                from_revision_id=from_revision_id,
                to_revision_id=to_revision_id,
            )
        )

    changes.extend(
        _removed_change(clause=clause, from_revision_id=from_revision_id)
        for clause in resolution.unmatched_old
    )
    changes.extend(
        _added_change(clause=clause, to_revision_id=to_revision_id)
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
