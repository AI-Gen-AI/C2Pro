"""
RACI assignments generation from clause payloads.

Refers to Suite ID: TS-UD-STK-RAC-003.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from src.stakeholders.domain.models import RACIRole, RaciAssignment


def generate_raci_assignments_from_clauses(
    clauses: list[dict],
) -> list[RaciAssignment]:
    """Create RACI assignments from extracted clause payloads."""
    assignments: list[RaciAssignment] = []

    for clause in clauses:
        if not isinstance(clause, dict):
            continue
        project_id = clause.get("project_id")
        full_text = clause.get("full_text")
        extracted = clause.get("extracted_entities") or {}
        raw_assignments = extracted.get("raci_assignments")
        if not isinstance(raw_assignments, list):
            continue
        for raw in raw_assignments:
            if not isinstance(raw, dict):
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
            assignments.append(
                RaciAssignment(
                    id=uuid4(),
                    project_id=project_id,
                    stakeholder_id=stakeholder_id,
                    wbs_item_id=wbs_item_id,
                    raci_role=role,
                    created_at=datetime.utcnow(),
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
