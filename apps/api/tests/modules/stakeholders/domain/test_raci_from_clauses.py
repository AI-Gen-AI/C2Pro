"""
RACI assignments from clauses tests.

Refers to Suite ID: TS-UD-STK-RAC-003.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from src.stakeholders.domain.models import RACIRole
from src.stakeholders.domain.services.raci_from_clauses import (
    generate_raci_assignments_from_clauses,
)


def _clause_payload(*, project_id: UUID, full_text: str, assignments: list[dict] | None) -> dict:
    payload = {
        "project_id": project_id,
        "full_text": full_text,
        "extracted_entities": {},
    }
    if assignments is not None:
        payload["extracted_entities"]["raci_assignments"] = assignments
    return payload


class TestRaciFromClauses:
    """Refers to Suite ID: TS-UD-STK-RAC-003."""

    def test_001_builds_assignments_from_clause_payload(self) -> None:
        project_id = uuid4()
        stakeholder_id = uuid4()
        wbs_item_id = uuid4()
        clauses = [
            _clause_payload(
                project_id=project_id,
                full_text="Clause evidence",
                assignments=[
                    {
                        "stakeholder_id": stakeholder_id,
                        "wbs_item_id": wbs_item_id,
                        "role": "A",
                    }
                ],
            )
        ]

        assignments = generate_raci_assignments_from_clauses(clauses)

        assert len(assignments) == 1
        assignment = assignments[0]
        assert assignment.project_id == project_id
        assert assignment.stakeholder_id == stakeholder_id
        assert assignment.wbs_item_id == wbs_item_id
        assert assignment.raci_role == RACIRole.ACCOUNTABLE
        assert assignment.evidence_text == "Clause evidence"
        assert assignment.generated_automatically is True
        assert isinstance(assignment.created_at, datetime)

    def test_002_skips_invalid_roles(self) -> None:
        project_id = uuid4()
        clauses = [
            _clause_payload(
                project_id=project_id,
                full_text="Clause evidence",
                assignments=[
                    {
                        "stakeholder_id": uuid4(),
                        "wbs_item_id": uuid4(),
                        "role": "X",
                    }
                ],
            )
        ]

        assignments = generate_raci_assignments_from_clauses(clauses)

        assert assignments == []

    def test_003_handles_missing_assignments(self) -> None:
        clauses = [
            _clause_payload(
                project_id=uuid4(),
                full_text="Clause evidence",
                assignments=None,
            )
        ]

        assignments = generate_raci_assignments_from_clauses(clauses)

        assert assignments == []
