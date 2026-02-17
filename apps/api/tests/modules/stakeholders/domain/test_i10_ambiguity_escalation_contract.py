"""
I10 - Stakeholder Ambiguity Escalation Contract (Domain, RED)
Test Suite ID: TS-I10-STK-DOM-002
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from src.stakeholders.domain.services.raci_from_clauses import (
    generate_raci_assignments_from_clauses,
)


def _clause_payload(*, project_id: UUID, assignments: list[dict]) -> dict:
    return {
        "project_id": project_id,
        "full_text": "Clause evidence for stakeholder mapping.",
        "extracted_entities": {
            "raci_assignments": assignments,
        },
    }


class TestI10AmbiguityEscalationContractRed:
    """Refers to Suite ID: TS-I10-STK-DOM-002."""

    def test_001_rejects_unresolved_stakeholder_identity_in_strict_mode_red(self) -> None:
        """
        I10.6 strict contract:
        unresolved stakeholder IDs must be rejected instead of silently persisted.
        """
        known_stakeholder_id = uuid4()
        unknown_stakeholder_id = uuid4()
        clauses = [
            _clause_payload(
                project_id=uuid4(),
                assignments=[
                    {
                        "stakeholder_id": known_stakeholder_id,
                        "wbs_item_id": uuid4(),
                        "role": "A",
                    },
                    {
                        "stakeholder_id": unknown_stakeholder_id,
                        "wbs_item_id": uuid4(),
                        "role": "R",
                    },
                ],
            )
        ]

        with pytest.raises(ValueError, match="unresolved stakeholder identity"):
            generate_raci_assignments_from_clauses(
                clauses,
                known_stakeholder_ids={known_stakeholder_id},
                strict_identity=True,
            )

    def test_002_rejects_ambiguous_mapping_candidates_in_strict_mode_red(self) -> None:
        """
        I10.6 strict contract:
        ambiguous candidate mappings must be escalated and rejected in strict mode.
        """
        stakeholder_id = uuid4()
        clauses = [
            _clause_payload(
                project_id=uuid4(),
                assignments=[
                    {
                        "stakeholder_id": stakeholder_id,
                        "wbs_item_id": uuid4(),
                        "role": "C",
                        "ambiguity_flag": True,
                        "ambiguity_reason": "multiple candidate aliases",
                    }
                ],
            )
        ]

        with pytest.raises(ValueError, match="ambiguous stakeholder mapping"):
            generate_raci_assignments_from_clauses(
                clauses,
                known_stakeholder_ids={stakeholder_id},
                strict_identity=True,
            )

