"""
RACI matrix generation service.

Refers to Suite ID: TS-UD-STK-RAC-002.
"""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from src.stakeholders.domain.models import RaciAssignment
from src.stakeholders.domain.services.raci_validator import validate_raci_row


def generate_raci_matrix(
    assignments: list[RaciAssignment],
) -> dict[UUID, list[RaciAssignment]]:
    """Group assignments by WBS item and validate each row."""
    matrix: dict[UUID, list[RaciAssignment]] = defaultdict(list)
    for assignment in assignments:
        matrix[assignment.wbs_item_id].append(assignment)

    for row_assignments in matrix.values():
        validate_raci_row([assignment.raci_role for assignment in row_assignments])

    return dict(matrix)
