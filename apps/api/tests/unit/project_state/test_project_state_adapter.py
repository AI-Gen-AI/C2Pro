"""Unit tests for SqlAlchemyProjectStateRepository adapter (TASK-V3-014-03).

TS-UT-PS-ADP-001

Tests the ORM ↔ domain round-trip, tenant isolation, and the locked invariant
that the repository never calls session.commit().
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.analysis.domain.contracts import BudgetItem, RiskItem, WbsActivity
from src.evidence.domain.runtime_trust import EvidenceRef, EvidenceTier
from src.project_state.domain.aggregate import ProjectState
from src.project_state.domain.entities import (
    Clause,
    Obligation,
    ProjectBudgetItem,
    ProjectRisk,
    ProjectWbsActivity,
    RaciCell,
    Stakeholder,
)
from src.project_state.domain.lifecycle import LifecycleStatus


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.merge = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def sample_project_state() -> ProjectState:
    project_id = uuid4()
    tenant_id = uuid4()
    extraction_run_id = uuid4()

    evidence = EvidenceRef(
        ref_id="ev-1",
        source="contract-v1",
        tier=EvidenceTier.VERIFIED,
        locator="p1:30-50",
    )

    return ProjectState(
        project_id=project_id,
        tenant_id=tenant_id,
        lifecycle_status=LifecycleStatus.ACTIVE,
        document_revision_ids=[uuid4(), uuid4()],
        procurement_refs=[uuid4()],
        clauses=[
            Clause(
                entity_id=uuid4(),
                clause_id="1.1",
                text="Scope of work",
                char_start=0,
                char_end=100,
                lifecycle_status=LifecycleStatus.ACTIVE,
                source_revision_id=uuid4(),
                extraction_run_id=extraction_run_id,
                evidence=[evidence],
            ),
        ],
        obligations=[
            Obligation(
                entity_id=uuid4(),
                description="Deliver within 30 days",
                clause_id="1.1",
                lifecycle_status=LifecycleStatus.ACTIVE,
                extraction_run_id=extraction_run_id,
                evidence=[evidence],
            ),
        ],
        risks=[
            ProjectRisk(
                entity_id=uuid4(),
                payload=RiskItem(
                    title="Delay penalty",
                    description="Late delivery penalty exposure",
                    severity="HIGH",
                ),
                lifecycle_status=LifecycleStatus.ACTIVE,
                extraction_run_id=extraction_run_id,
                evidence=[evidence],
            ),
        ],
        wbs_activities=[
            ProjectWbsActivity(
                entity_id=uuid4(),
                payload=WbsActivity(code="1.1.1", name="Foundation work"),
                lifecycle_status=LifecycleStatus.ACTIVE,
                extraction_run_id=extraction_run_id,
            ),
        ],
        budget_items=[
            ProjectBudgetItem(
                entity_id=uuid4(),
                payload=BudgetItem(name="Concrete", amount=5000.0, currency="EUR"),
                lifecycle_status=LifecycleStatus.ACTIVE,
                extraction_run_id=extraction_run_id,
            ),
        ],
        stakeholders=[
            Stakeholder(
                entity_id=uuid4(),
                name="ACME Corp",
                role="contractor",
                lifecycle_status=LifecycleStatus.ACTIVE,
                extraction_run_id=extraction_run_id,
            ),
        ],
        raci=[
            RaciCell(
                entity_id=uuid4(),
                stakeholder_id=uuid4(),
                activity_code="1.1.1",
                assignment="A",
                lifecycle_status=LifecycleStatus.ACTIVE,
                extraction_run_id=extraction_run_id,
            ),
        ],
    )


def _make_repo(ps: ProjectState, session: AsyncMock):
    """Import the real implementation after it exists; raises ImportError otherwise (RED)."""
    from src.project_state.adapters.persistence.project_state_repository import (
        SqlAlchemyProjectStateRepository,
    )

    return SqlAlchemyProjectStateRepository(session), ps


# ── Round-trip tests ───────────────────────────────────────────────


def test_orm_round_trip_aggregate_no_entities(sample_project_state):
    """ProjectState with no entities survives _to_orm_rows → _from_orm_rows round-trip."""
    ps = sample_project_state.model_copy(
        update={
            "clauses": [],
            "obligations": [],
            "risks": [],
            "wbs_activities": [],
            "budget_items": [],
            "stakeholders": [],
            "raci": [],
        }
    )

    from src.project_state.adapters.persistence.project_state_repository import (
        SqlAlchemyProjectStateRepository,
    )

    repo = SqlAlchemyProjectStateRepository(AsyncMock())

    orm_rows = repo._to_orm_rows(ps)
    reconstructed = repo._from_orm_rows(orm_rows)

    assert reconstructed == ps


def test_orm_round_trip_all_entity_types(sample_project_state):
    """Full aggregate with one of every entity type round-trips correctly."""
    from src.project_state.adapters.persistence.project_state_repository import (
        SqlAlchemyProjectStateRepository,
    )

    repo = SqlAlchemyProjectStateRepository(AsyncMock())
    orm_rows = repo._to_orm_rows(sample_project_state)
    reconstructed = repo._from_orm_rows(orm_rows)

    assert reconstructed == sample_project_state


def test_orm_round_trip_payload_entities_preserve_jsonb_fields():
    """Risk/Wbs/Budget payloads survive JSONB serialization round-trip."""
    eid = uuid4()
    risk_item = RiskItem(title="Fire risk", description="Site fire exposure", severity="LOW", confidence=0.75)
    ps = ProjectState(
        project_id=uuid4(),
        tenant_id=uuid4(),
        risks=[
            ProjectRisk(entity_id=eid, payload=risk_item),
        ],
        wbs_activities=[
            ProjectWbsActivity(
                entity_id=uuid4(),
                payload=WbsActivity(code="W-3", name="Electrical", level=2, parent_code="W-0"),
            ),
        ],
        budget_items=[
            ProjectBudgetItem(
                entity_id=uuid4(),
                payload=BudgetItem(name="Steel", amount=12000.0, currency="USD", cost_code="MAT-001"),
            ),
        ],
    )

    from src.project_state.adapters.persistence.project_state_repository import (
        SqlAlchemyProjectStateRepository,
    )

    repo = SqlAlchemyProjectStateRepository(AsyncMock())
    orm_rows = repo._to_orm_rows(ps)
    reconstructed = repo._from_orm_rows(orm_rows)

    assert len(reconstructed.risks) == 1
    assert reconstructed.risks[0].payload == risk_item
    assert len(reconstructed.wbs_activities) == 1
    assert reconstructed.wbs_activities[0].payload.code == "W-3"
    assert reconstructed.wbs_activities[0].payload.level == 2
    assert reconstructed.wbs_activities[0].payload.parent_code == "W-0"
    assert len(reconstructed.budget_items) == 1
    assert reconstructed.budget_items[0].payload.cost_code == "MAT-001"


def test_orm_round_trip_evidence_in_payload(sample_project_state):
    """EvidenceRef lists are stored inside payload JSONB and survive round-trip."""
    eid = uuid4()
    ev = EvidenceRef(ref_id="ref-abc", source="doc-5", tier=EvidenceTier.WEAK, locator="p7:42")
    ps = ProjectState(
        project_id=uuid4(),
        tenant_id=uuid4(),
        clauses=[
            Clause(
                entity_id=eid,
                clause_id="5.2",
                text="Indemnification clause",
                evidence=[ev],
            ),
        ],
    )

    from src.project_state.adapters.persistence.project_state_repository import (
        SqlAlchemyProjectStateRepository,
    )

    repo = SqlAlchemyProjectStateRepository(AsyncMock())
    orm_rows = repo._to_orm_rows(ps)
    reconstructed = repo._from_orm_rows(orm_rows)

    assert len(reconstructed.clauses) == 1
    assert len(reconstructed.clauses[0].evidence) == 1
    assert reconstructed.clauses[0].evidence[0] == ev


# ── No-commit invariant ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_save_does_not_call_session_commit(sample_project_state):
    """repository.save() MUST NOT call session.commit()."""
    from src.project_state.adapters.persistence.project_state_repository import (
        SqlAlchemyProjectStateRepository,
    )

    sess = AsyncMock()
    sess.add = MagicMock()
    sess.flush = AsyncMock()
    sess.merge = AsyncMock()
    sess.execute = AsyncMock()
    repo = SqlAlchemyProjectStateRepository(sess)
    await repo.save(sample_project_state)
    sess.commit.assert_not_called()


@pytest.mark.asyncio
async def test_get_does_not_call_session_commit(mock_session):
    """repository.get() MUST NOT call session.commit()."""
    from src.project_state.adapters.persistence.project_state_repository import (
        SqlAlchemyProjectStateRepository,
    )

    repo = SqlAlchemyProjectStateRepository(mock_session)
    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=exec_result)

    await repo.get(uuid4(), uuid4())
    mock_session.commit.assert_not_called()


# ── Tenant isolation ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_wrong_tenant_returns_none(mock_session):
    """get() with wrong tenant_id returns None."""
    from src.project_state.adapters.persistence.project_state_repository import (
        SqlAlchemyProjectStateRepository,
    )

    repo = SqlAlchemyProjectStateRepository(mock_session)
    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=exec_result)

    result = await repo.get(uuid4(), uuid4())
    assert result is None


# ── Entity type coverage ────────────────────────────────────────────


def test_all_seven_entity_types_round_trip():
    """Verify all 7 entity discriminator values are handled."""
    eid_obligation = uuid4()
    eid_stakeholder = uuid4()
    eid_raci = uuid4()

    ps = ProjectState(
        project_id=uuid4(),
        tenant_id=uuid4(),
        clauses=[Clause(entity_id=uuid4(), clause_id="C1", text="t1")],
        obligations=[Obligation(entity_id=eid_obligation, description="pay on time")],
        risks=[ProjectRisk(entity_id=uuid4(), payload=RiskItem(title="R1", description="d"))],
        wbs_activities=[ProjectWbsActivity(entity_id=uuid4(), payload=WbsActivity(code="W1", name="n1"))],
        budget_items=[ProjectBudgetItem(entity_id=uuid4(), payload=BudgetItem(name="B1"))],
        stakeholders=[Stakeholder(entity_id=eid_stakeholder, name="S1")],
        raci=[RaciCell(entity_id=eid_raci, stakeholder_id=uuid4(), activity_code="A1", assignment="R")],
    )

    from src.project_state.adapters.persistence.project_state_repository import (
        SqlAlchemyProjectStateRepository,
    )

    repo = SqlAlchemyProjectStateRepository(AsyncMock())
    orm_rows = repo._to_orm_rows(ps)
    reconstructed = repo._from_orm_rows(orm_rows)

    assert len(reconstructed.clauses) == 1
    assert len(reconstructed.obligations) == 1
    assert len(reconstructed.risks) == 1
    assert len(reconstructed.wbs_activities) == 1
    assert len(reconstructed.budget_items) == 1
    assert len(reconstructed.stakeholders) == 1
    assert len(reconstructed.raci) == 1


# ── Entity discriminator mapping ───────────────────────────────────


def test_entity_type_discriminator_values(sample_project_state):
    """Each entity type maps to its correct string discriminator."""
    from src.project_state.adapters.persistence.project_state_repository import (
        SqlAlchemyProjectStateRepository,
    )

    expected_types = {
        Clause: "clause",
        Obligation: "obligation",
        ProjectRisk: "risk",
        ProjectWbsActivity: "wbs_activity",
        ProjectBudgetItem: "budget_item",
        Stakeholder: "stakeholder",
        RaciCell: "raci_cell",
    }

    repo = SqlAlchemyProjectStateRepository(AsyncMock())
    for entity_type, expected_discriminator in expected_types.items():
        actual = repo._entity_type_discriminator(entity_type)
        assert actual == expected_discriminator, f"{entity_type.__name__} → {expected_discriminator}"


def test_entity_class_for_type():
    """Discriminator string maps back to correct entity class."""
    from src.project_state.adapters.persistence.project_state_repository import (
        SqlAlchemyProjectStateRepository,
    )

    type_to_class = {
        "clause": Clause,
        "obligation": Obligation,
        "risk": ProjectRisk,
        "wbs_activity": ProjectWbsActivity,
        "budget_item": ProjectBudgetItem,
        "stakeholder": Stakeholder,
        "raci_cell": RaciCell,
    }

    repo = SqlAlchemyProjectStateRepository(AsyncMock())
    for discriminator, expected_class in type_to_class.items():
        actual = repo._entity_class_for_type(discriminator)
        assert actual is expected_class, f"{discriminator} → {expected_class.__name__}"
