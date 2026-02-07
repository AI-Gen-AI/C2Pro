"""
RACI matrix generation tests.

Refers to Suite ID: TS-UD-STK-RAC-002.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest

from src.stakeholders.domain.models import RACIRole, RaciAssignment
from src.stakeholders.domain.services.raci_matrix_generator import generate_raci_matrix


class TestRaciMatrixGeneration:
    """Refers to Suite ID: TS-UD-STK-RAC-002."""

    def _assignment(self, *, wbs_item_id, raci_role: RACIRole) -> RaciAssignment:
        return RaciAssignment(
            id=uuid4(),
            project_id=uuid4(),
            stakeholder_id=uuid4(),
            wbs_item_id=wbs_item_id,
            raci_role=raci_role,
            created_at=datetime.utcnow(),
        )

    def test_001_groups_assignments_by_wbs_item(self) -> None:
        wbs_a = uuid4()
        wbs_b = uuid4()
        assignments = [
            self._assignment(wbs_item_id=wbs_a, raci_role=RACIRole.ACCOUNTABLE),
            self._assignment(wbs_item_id=wbs_a, raci_role=RACIRole.RESPONSIBLE),
            self._assignment(wbs_item_id=wbs_b, raci_role=RACIRole.ACCOUNTABLE),
            self._assignment(wbs_item_id=wbs_b, raci_role=RACIRole.INFORMED),
        ]

        matrix = generate_raci_matrix(assignments)

        assert set(matrix.keys()) == {wbs_a, wbs_b}
        assert len(matrix[wbs_a]) == 2
        assert len(matrix[wbs_b]) == 2

    def test_002_rejects_rows_without_accountable(self) -> None:
        wbs_id = uuid4()
        assignments = [
            self._assignment(wbs_item_id=wbs_id, raci_role=RACIRole.RESPONSIBLE),
            self._assignment(wbs_item_id=wbs_id, raci_role=RACIRole.CONSULTED),
        ]

        with pytest.raises(ValueError, match="accountable"):
            generate_raci_matrix(assignments)

    def test_003_rejects_rows_with_multiple_accountables(self) -> None:
        wbs_id = uuid4()
        assignments = [
            self._assignment(wbs_item_id=wbs_id, raci_role=RACIRole.ACCOUNTABLE),
            self._assignment(wbs_item_id=wbs_id, raci_role=RACIRole.ACCOUNTABLE),
        ]

        with pytest.raises(ValueError, match="accountable"):
            generate_raci_matrix(assignments)
