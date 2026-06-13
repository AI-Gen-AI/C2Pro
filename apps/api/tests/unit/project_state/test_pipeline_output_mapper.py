"""Unit tests for the pipeline_output_mapper (TASK-V3-014-05).

TS-UT-PS-MAP-001

Tests the pure function that converts the legacy per-document pipeline output
(a graph state dict) into a ProjectState aggregate. No DB.
"""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

import pytest

from src.analysis.domain.contracts import BudgetItem, RiskItem, WbsActivity
from src.project_state.domain.lifecycle import LifecycleStatus


@pytest.fixture
def mapper():
    from src.project_state.application.pipeline_output_mapper import (
        map_pipeline_output_to_project_state,
    )

    return map_pipeline_output_to_project_state


@pytest.fixture
def project_id():
    return uuid4()


@pytest.fixture
def tenant_id():
    return uuid4()


@pytest.fixture
def full_pipeline_output():
    return {
        "risks": [
            {"title": "Delay penalty", "description": "LD exposure", "severity": "HIGH"},
            {"title": "Budget overrun", "description": "Overspend risk", "severity": "MEDIUM", "confidence": 0.6},
        ],
        "wbs_activities": [
            {"code": "1.1", "name": "Foundation", "level": 1},
            {"code": "1.1.1", "name": "Excavation", "level": 2, "parent_code": "1.1"},
        ],
        "budget_items": [
            {"name": "Concrete", "amount": 5000.0, "currency": "EUR", "cost_code": "C-100"},
            {"name": "Steel", "amount": 12000.0, "currency": "USD"},
        ],
        "clauses": [
            {"clause_id": "1.1", "text": "Scope of work"},
            {"clause_id": "1.2", "text": "Payment terms", "char_start": 200, "char_end": 500},
        ],
        "obligations": [
            {"description": "Deliver within 30 days", "clause_id": "1.1"},
            {"description": "Provide weekly reports", "due_date": "2026-12-31"},
        ],
        "stakeholders": [
            {"name": "ACME Corp", "role": "contractor", "is_legal_entity": True},
            {"name": "Jane Doe", "role": "project manager"},
        ],
        "raci": [
            {"stakeholder_id": str(uuid4()), "activity_code": "1.1", "assignment": "A"},
        ],
    }


# ── Full mapping ────────────────────────────────────────────────────


def test_maps_all_populated_entity_types(mapper, project_id, tenant_id, full_pipeline_output):
    result = mapper(project_id, tenant_id, full_pipeline_output)

    assert result.project_id == project_id
    assert result.tenant_id == tenant_id
    assert result.lifecycle_status == LifecycleStatus.ACTIVE
    assert len(result.risks) == 2
    assert len(result.wbs_activities) == 2
    assert len(result.budget_items) == 2
    assert len(result.clauses) == 2
    assert len(result.obligations) == 2
    assert len(result.stakeholders) == 2
    assert len(result.raci) == 1


def test_all_entity_ids_are_uuids(mapper, project_id, tenant_id, full_pipeline_output):
    result = mapper(project_id, tenant_id, full_pipeline_output)

    for risk in result.risks:
        assert isinstance(risk.entity_id, UUID)
    for wbs in result.wbs_activities:
        assert isinstance(wbs.entity_id, UUID)
    for budget in result.budget_items:
        assert isinstance(budget.entity_id, UUID)
    for clause in result.clauses:
        assert isinstance(clause.entity_id, UUID)
    for obligation in result.obligations:
        assert isinstance(obligation.entity_id, UUID)
    for stakeholder in result.stakeholders:
        assert isinstance(stakeholder.entity_id, UUID)
    for raci_cell in result.raci:
        assert isinstance(raci_cell.entity_id, UUID)


def test_risk_payload_is_validated_risk_item(mapper, project_id, tenant_id, full_pipeline_output):
    result = mapper(project_id, tenant_id, full_pipeline_output)
    assert isinstance(result.risks[0].payload, RiskItem)
    assert result.risks[0].payload.title == "Delay penalty"
    assert result.risks[0].payload.severity.value == "HIGH"


def test_wbs_payload_is_validated_wbs_activity(mapper, project_id, tenant_id, full_pipeline_output):
    result = mapper(project_id, tenant_id, full_pipeline_output)
    assert isinstance(result.wbs_activities[0].payload, WbsActivity)
    assert result.wbs_activities[0].payload.code == "1.1"


def test_budget_payload_is_validated_budget_item(mapper, project_id, tenant_id, full_pipeline_output):
    result = mapper(project_id, tenant_id, full_pipeline_output)
    assert isinstance(result.budget_items[0].payload, BudgetItem)
    assert result.budget_items[0].payload.name == "Concrete"


# ── Partial mapping (missing keys) ─────────────────────────────────


def test_partial_mapping_missing_entity_keys_does_not_raise(mapper, project_id, tenant_id):
    """If a key is missing from the pipeline output, no error — just empty lists."""
    result = mapper(project_id, tenant_id, {})
    assert result.risks == []
    assert result.clauses == []
    assert result.stakeholders == []
    assert result.raci == []
    assert result.procurement_refs == []


def test_partial_mapping_only_risks(mapper, project_id, tenant_id):
    result = mapper(
        project_id,
        tenant_id,
        {"risks": [{"title": "T", "description": "D"}]},
    )
    assert len(result.risks) == 1
    assert result.wbs_activities == []
    assert result.budget_items == []
    assert result.clauses == []
    assert result.obligations == []


# ── Invalid entity handling (logged, not raised) ───────────────────


def test_invalid_risk_dict_skipped_with_warning(mapper, project_id, tenant_id, caplog):
    """Invalid risk dict is skipped with a warning, not raised."""
    with caplog.at_level(logging.WARNING):
        result = mapper(
            project_id,
            tenant_id,
            {
                "risks": [
                    {"title": "Valid risk", "description": "OK"},
                    {"bogus": "invalid"},  # missing required fields
                    {"title": "Another valid", "description": "Also OK"},
                ],
            },
        )

    assert len(result.risks) == 2  # invalid one skipped
    assert result.risks[0].payload.title == "Valid risk"
    assert result.risks[1].payload.title == "Another valid"


def test_invalid_wbs_skipped_with_warning(mapper, project_id, tenant_id, caplog):
    with caplog.at_level(logging.WARNING):
        result = mapper(
            project_id,
            tenant_id,
            {
                "wbs_activities": [
                    {"code": "W-1", "name": "Good"},
                    {"bad": True},
                ],
            },
        )

    assert len(result.wbs_activities) == 1
    assert result.wbs_activities[0].payload.code == "W-1"


# ── Extraction run ID propagation ──────────────────────────────────


def test_extraction_run_id_propagated_to_all_entities(mapper, project_id, tenant_id):
    run_id = uuid4()
    result = mapper(
        project_id,
        tenant_id,
        {"risks": [{"title": "R", "description": "D"}], "clauses": [{"clause_id": "C1", "text": "T"}]},
        extraction_run_id=run_id,
    )

    assert result.risks[0].extraction_run_id == run_id
    assert result.clauses[0].extraction_run_id == run_id


def test_extraction_run_id_none_by_default(mapper, project_id, tenant_id):
    result = mapper(
        project_id,
        tenant_id,
        {"clauses": [{"clause_id": "C1", "text": "T"}]},
    )

    assert result.clauses[0].extraction_run_id is None


# ── Evidence defaults ──────────────────────────────────────────────


def test_entities_have_empty_evidence_by_default(mapper, project_id, tenant_id):
    result = mapper(
        project_id,
        tenant_id,
        {"clauses": [{"clause_id": "C1", "text": "T"}]},
    )

    assert result.clauses[0].evidence == []


# ── Stakeholder field mapping ──────────────────────────────────────


def test_stakeholder_fields_mapped_correctly(mapper, project_id, tenant_id):
    result = mapper(
        project_id,
        tenant_id,
        {
            "stakeholders": [
                {
                    "name": "ACME Corp",
                    "role": "contractor",
                    "company_name": "ACME Ltd",
                    "is_legal_entity": True,
                },
            ],
        },
    )

    s = result.stakeholders[0]
    assert s.name == "ACME Corp"
    assert s.role == "contractor"
    assert s.company_name == "ACME Ltd"
    assert s.is_legal_entity is True


# ── RaciCell field mapping ─────────────────────────────────────────


def test_raci_cell_assignment_mapped_correctly(mapper, project_id, tenant_id):
    sid = str(uuid4())
    result = mapper(
        project_id,
        tenant_id,
        {"raci": [{"stakeholder_id": sid, "activity_code": "1.2.3", "assignment": "R"}]},
    )

    assert result.raci[0].stakeholder_id == UUID(sid)
    assert result.raci[0].activity_code == "1.2.3"
    assert result.raci[0].assignment == "R"
