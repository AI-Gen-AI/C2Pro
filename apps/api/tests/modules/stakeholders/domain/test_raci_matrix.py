"""
Stakeholders & Graph Analysis Tests (TDD - RED Phase)

Refers to Suite IDs: TS-UD-STK-CLS-001, TS-UD-STK-RAC-001, TS-UD-ANA-GRP-001.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.stakeholders.domain.models import (
    InterestLevel,
    PowerLevel,
    RACIRole,
    StakeholderQuadrant,
)
from src.stakeholders.domain.services.quadrant_assignment import assign_quadrant
from src.stakeholders.domain.services.raci_validator import validate_raci_row
from src.analysis.domain.graph import GraphNode


class TestPowerInterestQuadrant:
    """Refers to Suite ID: TS-UD-STK-CLS-001."""

    def test_high_power_low_interest_is_keep_satisfied(self):
        quadrant = assign_quadrant(PowerLevel.HIGH, InterestLevel.LOW)
        assert quadrant == StakeholderQuadrant.KEEP_SATISFIED

    def test_low_power_high_interest_is_keep_informed(self):
        quadrant = assign_quadrant(PowerLevel.LOW, InterestLevel.HIGH)
        assert quadrant == StakeholderQuadrant.KEEP_INFORMED


class TestRaciMatrixRules:
    """Refers to Suite ID: TS-UD-STK-RAC-001."""

    def test_raci_row_with_two_accountables_is_invalid(self):
        roles = [RACIRole.ACCOUNTABLE, RACIRole.RESPONSIBLE, RACIRole.ACCOUNTABLE]
        with pytest.raises(ValueError):
            validate_raci_row(roles)

    def test_raci_row_with_zero_accountables_is_invalid(self):
        roles = [RACIRole.RESPONSIBLE, RACIRole.CONSULTED, RACIRole.INFORMED]
        with pytest.raises(ValueError):
            validate_raci_row(roles)


class TestGraphNodeEntity:
    """Refers to Suite ID: TS-UD-ANA-GRP-001."""

    def test_graph_node_requires_id_and_label(self):
        with pytest.raises(ValueError):
            GraphNode(node_id=None, label="Clause", properties={})

        with pytest.raises(ValueError):
            GraphNode(node_id=uuid4(), label="", properties={})

    def test_graph_node_is_neo4j_compatible(self):
        node = GraphNode(node_id=uuid4(), label="Clause", properties={"type": "legal"})
        assert node.label == "Clause"
        assert isinstance(node.properties, dict)
