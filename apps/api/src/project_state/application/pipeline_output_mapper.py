"""Pipeline output to ProjectState aggregate mapper (ADR-014 / TASK-V3-014-05).

TS-UT-PS-MAP-001

Converts the legacy per-document pipeline output dict into a ProjectState aggregate.
Pure function — no DB, no I/O. Bridges the old single-doc model to the canonical
project-level aggregate.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import structlog
from pydantic import BaseModel, ValidationError

from src.analysis.domain.contracts import BudgetItem, RiskItem, WbsActivity
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

logger = structlog.get_logger()


def _parse_entities(
    raw_items: list[Any],
    entity_class: type[BaseModel],
    extraction_run_id: UUID | None,
) -> list[Any]:
    entities: list[Any] = []
    for item in raw_items:
        if not isinstance(item, dict):
            logger.warning(
                "skipping_non_dict_item",
                entity_type=entity_class.__name__,
                item_type=type(item).__name__,
            )
            continue
        try:
            entity = entity_class.model_validate(
                {"entity_id": uuid4(), "extraction_run_id": extraction_run_id, **item}
            )
            entities.append(entity)
        except ValidationError:
            logger.warning(
                "skipping_invalid_entity",
                entity_type=entity_class.__name__,
                item_preview=str(item)[:200],
            )
    return entities


def _parse_payload_entities(
    raw_items: list[Any],
    wrapper_class: type[BaseModel],
    payload_class: type[BaseModel],
    extraction_run_id: UUID | None,
) -> list[Any]:
    entities: list[Any] = []
    for item in raw_items:
        if not isinstance(item, dict):
            logger.warning(
                "skipping_non_dict_item",
                entity_type=wrapper_class.__name__,
                item_type=type(item).__name__,
            )
            continue
        try:
            payload = payload_class.model_validate(item)
            entity = wrapper_class.model_validate(
                {
                    "entity_id": uuid4(),
                    "extraction_run_id": extraction_run_id,
                    "payload": payload.model_dump(),
                }
            )
            entities.append(entity)
        except ValidationError:
            logger.warning(
                "skipping_invalid_payload_entity",
                entity_type=wrapper_class.__name__,
                item_preview=str(item)[:200],
            )
    return entities


def map_pipeline_output_to_project_state(
    project_id: UUID,
    tenant_id: UUID,
    pipeline_state: dict[str, Any],
    extraction_run_id: UUID | None = None,
) -> ProjectState:
    return ProjectState(
        project_id=project_id,
        tenant_id=tenant_id,
        lifecycle_status=LifecycleStatus.ACTIVE,
        clauses=_parse_entities(
            pipeline_state.get("clauses", []), Clause, extraction_run_id
        ),
        obligations=_parse_entities(
            pipeline_state.get("obligations", []), Obligation, extraction_run_id
        ),
        risks=_parse_payload_entities(
            pipeline_state.get("risks", []),
            ProjectRisk,
            RiskItem,
            extraction_run_id,
        ),
        wbs_activities=_parse_payload_entities(
            pipeline_state.get("wbs_activities", []),
            ProjectWbsActivity,
            WbsActivity,
            extraction_run_id,
        ),
        budget_items=_parse_payload_entities(
            pipeline_state.get("budget_items", []),
            ProjectBudgetItem,
            BudgetItem,
            extraction_run_id,
        ),
        stakeholders=_parse_entities(
            pipeline_state.get("stakeholders", []), Stakeholder, extraction_run_id
        ),
        raci=_parse_entities(
            pipeline_state.get("raci", []), RaciCell, extraction_run_id
        ),
    )
