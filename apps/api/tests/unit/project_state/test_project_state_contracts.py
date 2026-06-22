"""Freeze-lock tests for the ADR-014 ProjectState aggregate + entities (TASK-V3-014-01/-06).

Independently verifies the frozen contracts before Codex builds adapters/migration:
immutability (frozen), drift rejection (extra=forbid), honest defaults, lifecycle,
INV-1 evidence provenance, composition of the ADR-013 payloads, and the reserved
future-domain seams (Procurement / Stakeholder) being nullable + logic-free.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.analysis.domain.contracts import RiskItem
from src.evidence.domain.runtime_trust import EvidenceRef, EvidenceTier
from src.project_state.domain.aggregate import ProjectState
from src.project_state.domain.entities import (
    Clause,
    Obligation,
    ProjectRisk,
    RaciCell,
    Stakeholder,
)
from src.project_state.domain.lifecycle import LifecycleStatus


def test_lifecycle_status_values():
    assert {s.value for s in LifecycleStatus} == {"draft", "active", "superseded", "archived"}


class TestEntities:
    def test_project_risk_composes_riskitem_payload(self):
        r = ProjectRisk(
            entity_id=uuid4(),
            payload=RiskItem(title="Delay penalty", description="LD exposure", impact="HIGH"),
        )
        assert r.lifecycle_status is LifecycleStatus.ACTIVE  # default
        assert r.evidence == []  # honest default, not fabricated
        assert r.payload.severity is not None and r.payload.severity.value == "HIGH"

    def test_entity_is_frozen(self):
        c = Clause(entity_id=uuid4(), clause_id="12.3", text="...")
        with pytest.raises(ValidationError):
            c.text = "x"

    def test_entity_forbids_extra_keys(self):
        with pytest.raises(ValidationError):
            Clause(entity_id=uuid4(), clause_id="1", text="t", bogus=1)

    def test_inv1_evidence_provenance(self):
        ev = EvidenceRef(ref_id="r1", source="contract-rev-4", tier=EvidenceTier.VERIFIED, locator="p3:120-140")
        o = Obligation(entity_id=uuid4(), description="pay within 30d", evidence=[ev])
        assert o.evidence[0].tier is EvidenceTier.VERIFIED

    def test_stakeholder_reserved_seams_nullable(self):
        s = Stakeholder(entity_id=uuid4(), name="ACME Corp")
        assert s.authority_level is None
        assert s.escalation_role is None
        assert s.communication_preference is None

    def test_raci_cell(self):
        rc = RaciCell(entity_id=uuid4(), stakeholder_id=uuid4(), activity_code="1.1", assignment="A")
        assert rc.assignment == "A"


class TestAggregate:
    def test_empty_aggregate_defaults(self):
        ps = ProjectState(project_id=uuid4(), tenant_id=uuid4())
        assert ps.lifecycle_status is LifecycleStatus.ACTIVE
        assert ps.risks == [] and ps.clauses == [] and ps.procurement_refs == []

    def test_with_lifecycle_returns_new_immutable_instance(self):
        ps = ProjectState(project_id=uuid4(), tenant_id=uuid4())
        superseded = ps.with_lifecycle(LifecycleStatus.SUPERSEDED)
        assert superseded is not ps
        assert superseded.lifecycle_status is LifecycleStatus.SUPERSEDED
        assert ps.lifecycle_status is LifecycleStatus.ACTIVE  # original untouched

    def test_aggregate_frozen_and_forbids_extra(self):
        ps = ProjectState(project_id=uuid4(), tenant_id=uuid4())
        with pytest.raises(ValidationError):
            ps.tenant_id = uuid4()
        with pytest.raises(ValidationError):
            ProjectState(project_id=uuid4(), tenant_id=uuid4(), bogus=1)

    def test_aggregate_holds_typed_entities(self):
        ps = ProjectState(
            project_id=uuid4(),
            tenant_id=uuid4(),
            risks=[ProjectRisk(entity_id=uuid4(), payload=RiskItem(title="T", description="D"))],
        )
        assert isinstance(ps.risks[0], ProjectRisk)
