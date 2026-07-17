"""
RACI assignments generation from clause payloads.

Refers to Suite ID: TS-UD-STK-RAC-003.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from src.stakeholders.domain.models import RaciAssignment, RACIRole


def generate_raci_assignments_from_clauses(
    clauses: Sequence[Mapping[str, object]],
    *,
    tenant_id: UUID,
    known_stakeholder_ids: set[UUID] | None = None,
    strict_identity: bool = False,
) -> list[RaciAssignment]:
    """Create RACI assignments from extracted clause payloads."""
    assignments: list[RaciAssignment] = []
    known_ids = known_stakeholder_ids or set()

    for clause in clauses:
        project_id = clause.get("project_id")
        full_text = cast(str | None, clause.get("full_text"))
        extracted = cast(Mapping[str, object], clause.get("extracted_entities") or {})
        raw_assignments = extracted.get("raci_assignments")
        if not isinstance(raw_assignments, list):
            continue
        for raw in raw_assignments:
            if not isinstance(raw, Mapping):
                continue
            stakeholder_id = raw.get("stakeholder_id")
            wbs_item_id = raw.get("wbs_item_id")
            role = _parse_role(raw.get("role"))
            if (
                role is None
                or not isinstance(project_id, UUID)
                or not isinstance(stakeholder_id, UUID)
                or not isinstance(wbs_item_id, UUID)
            ):
                continue

            _validate_identity_constraints(
                raw=raw,
                stakeholder_id=stakeholder_id,
                known_ids=known_ids,
                strict_identity=strict_identity,
            )

            assignments.append(
                RaciAssignment(
                    id=uuid4(),
                    project_id=project_id,
                    tenant_id=tenant_id,
                    stakeholder_id=stakeholder_id,
                    wbs_item_id=wbs_item_id,
                    raci_role=role,
                    created_at=datetime.now(UTC),
                    evidence_text=full_text,
                    generated_automatically=True,
                )
            )

    return assignments


def _parse_role(value: object) -> RACIRole | None:
    if isinstance(value, RACIRole):
        return value
    if isinstance(value, str):
        normalized = value.strip().upper()
        for role in RACIRole:
            if role.value == normalized or role.name == normalized:
                return role
    return None


def _validate_identity_constraints(
    *,
    raw: Mapping[str, object],
    stakeholder_id: UUID,
    known_ids: set[UUID],
    strict_identity: bool,
) -> None:
    if not strict_identity:
        return
    if bool(raw.get("ambiguity_flag")):
        raise ValueError("ambiguous stakeholder mapping")
    if stakeholder_id not in known_ids:
        raise ValueError("unresolved stakeholder identity")
