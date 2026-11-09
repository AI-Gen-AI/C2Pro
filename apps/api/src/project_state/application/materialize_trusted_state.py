"""Idempotent bootstrap of canonical ProjectState from trusted source evidence.

The caller owns the transaction; this service NEVER commits or approves HITL.
It will NOT update or replace existing canonical state without an explicit
revision reconciliation plan. Fails closed rather than silently overwriting.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from src.project_state.application.trusted_artifact_projector import (
    TrustedRevisionBundle,
    build_trusted_state_candidate,
)
from src.project_state.ports.project_state_repository import ProjectStateRepository

MaterializationStatus = Literal[
    "no_trusted_artifacts",
    "source_provenance_unavailable",
    "created",
    "unchanged",
    "reconciliation_required",
]


@dataclass(frozen=True)
class MaterializationOutcome:
    status: MaterializationStatus
    clause_count: int
    risk_count: int
    trusted_revisions: int
    rejected_unverified_risks: int


async def materialize_trusted_state_if_absent(
    *,
    project_id: UUID,
    tenant_id: UUID,
    bundles: Sequence[TrustedRevisionBundle],
    repository: ProjectStateRepository,
) -> MaterializationOutcome:
    """Bootstrap only. Existing state is read, not overwritten.

    This is intentionally NOT called by an HTTP endpoint. Source bundles must
    have been obtained from the trusted-current repository inside the existing
    tenant-bound transaction; a boolean trust marker alone grants no authority.
    """
    candidate = build_trusted_state_candidate(
        project_id=project_id,
        tenant_id=tenant_id,
        bundles=bundles,
    )
    if candidate is None:
        return MaterializationOutcome("no_trusted_artifacts", 0, 0, 0, 0)
    diagnostics = candidate.diagnostics
    # A subset of the input risks cannot be presented as a complete risk
    # assessment: risk_scorer would otherwise assign 90 (clean assessment)
    # to an empty list or under-penalize an incomplete set. Do not persist
    # *any* canonical state from this provisional/partial evidence.
    if (
        diagnostics.revision_bound_clauses == 0
        or diagnostics.source_bound_risks == 0
        or diagnostics.rejected_unverified_risks != 0
        or diagnostics.missing_clause_source_revisions != 0
        or any(not bundle.source_clauses for bundle in bundles)
    ):
        return MaterializationOutcome(
            "source_provenance_unavailable",
            0,
            0,
            diagnostics.input_bundles,
            diagnostics.rejected_unverified_risks,
        )

    state = candidate.state
    insert_if_absent = getattr(repository, "insert_if_absent", None)
    if not callable(insert_if_absent):
        raise RuntimeError("TRUSTED_STATE_ATOMIC_INSERT_REQUIRED")
    # Never race between get() and destructive save(): the DB PK arbitrates.
    # Never call ProjectStateRepository.save() during bootstrap.
    created = await insert_if_absent(state)
    if created:
        return MaterializationOutcome(
            "created",
            len(state.clauses),
            len(state.risks),
            diagnostics.input_bundles,
            diagnostics.rejected_unverified_risks,
        )

    existing = await repository.get(project_id, tenant_id)
    if existing is None:
        # Example: conflicting row exists for a different tenant under RLS.
        raise RuntimeError("TRUSTED_STATE_ATOMIC_CONFLICT_NOT_VISIBLE")
    if existing.model_dump(mode="json") == state.model_dump(mode="json"):
        return MaterializationOutcome(
            "unchanged",
            len(state.clauses),
            len(state.risks),
            diagnostics.input_bundles,
            diagnostics.rejected_unverified_risks,
        )
    # Different trusted set OR manual edits require an explicit,
    # revision-aware reconciliation. Do not overwrite existing state.
    return MaterializationOutcome(
        "reconciliation_required",
        len(state.clauses),
        len(state.risks),
        diagnostics.input_bundles,
        diagnostics.rejected_unverified_risks,
    )


__all__ = [
    "MaterializationOutcome",
    "MaterializationStatus",
    "materialize_trusted_state_if_absent",
]
