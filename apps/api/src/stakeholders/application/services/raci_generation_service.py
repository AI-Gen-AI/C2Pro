from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import structlog

from src.documents.ports.document_repository import IDocumentRepository
from src.procurement.ports.wbs_repository import IWBSRepository
from src.stakeholders.application.dtos import (
    RaciGenerationAssignment,
    RaciGenerationResult,
    RaciStakeholderInput,
    RaciWBSItemInput,
)
from src.stakeholders.application.list_project_stakeholders_use_case import (
    ListProjectStakeholdersUseCase,
)
from src.stakeholders.domain.models import RaciAssignment
from src.stakeholders.ports.raci_generator import RaciGeneratorPort
from src.stakeholders.ports.raci_inference_service import IRaciInferenceService
from src.stakeholders.ports.stakeholder_repository import IStakeholderRepository

logger = structlog.get_logger()


class RaciGenerationService:
    def __init__(
        self,
        *,
        tenant_id: UUID,
        list_stakeholders_use_case: ListProjectStakeholdersUseCase,
        wbs_repository: IWBSRepository,
        document_repository: IDocumentRepository,
        raci_generator: RaciGeneratorPort,
        stakeholder_repository: IStakeholderRepository,
        raci_inference_service: IRaciInferenceService | None = None,
    ) -> None:
        self.tenant_id = tenant_id
        self.list_stakeholders_use_case = list_stakeholders_use_case
        self.wbs_repository = wbs_repository
        self.document_repository = document_repository
        self.raci_generator = raci_generator
        self.stakeholder_repository = stakeholder_repository
        self.raci_inference_service = raci_inference_service

    async def generate_and_persist(self, project_id: UUID) -> RaciGenerationResult:
        wbs_items = await self._load_leaf_wbs_items(project_id)
        stakeholders = await self._load_stakeholders(project_id)

        if not wbs_items or not stakeholders:
            return RaciGenerationResult(assignments=[], warnings=[])

        i10_warnings = await self._run_optional_i10_inference(
            project_id=project_id,
            wbs_items=wbs_items,
        )
        if i10_warnings:
            raise ValueError("requires PMO/legal validation")

        result = await self.raci_generator.generate_assignments(
            wbs_items=wbs_items,
            stakeholders=stakeholders,
        )
        result.warnings = _merge_warnings(result.warnings, i10_warnings)

        try:
            await self._persist_assignments(
                project_id=project_id,
                assignments=result.assignments,
                known_stakeholder_ids={stakeholder.id for stakeholder in stakeholders},
            )
        # Persistence failures are sanitized before they cross the application boundary.
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "raci_assignments_persist_failed",
                project_id=str(project_id),
                error_type=type(exc).__name__,
            )
            raise ValueError("unable to persist raci assignments") from None

        return result

    async def _load_leaf_wbs_items(self, project_id: UUID) -> list[RaciWBSItemInput]:
        items = await self.wbs_repository.get_by_project(project_id, self.tenant_id)
        if not items:
            return []

        parent_codes = {item.parent_code for item in items if item.parent_code}
        leaf_items = [item for item in items if item.code not in parent_codes]

        clause_map = await self._load_clause_text_map(
            item.source_clause_id for item in leaf_items
        )

        return [
            RaciWBSItemInput(
                id=item.id,
                name=item.name,
                description=item.description,
                clause_text=clause_map.get(item.source_clause_id),
            )
            for item in leaf_items
        ]

    async def _load_clause_text_map(self, clause_ids: Iterable[UUID | None]) -> dict[UUID, str]:
        clause_id_list = [clause_id for clause_id in clause_ids if clause_id is not None]
        return await self.document_repository.get_clause_text_map(clause_id_list)

    async def _load_stakeholders(self, project_id: UUID) -> list[RaciStakeholderInput]:
        stakeholders, _ = await self.list_stakeholders_use_case.execute(
            project_id=project_id,
            tenant_id=self.tenant_id,
        )
        return [
            RaciStakeholderInput(
                id=stakeholder.id,
                name=stakeholder.name,
                role=stakeholder.role,
                company=stakeholder.organization,
                stakeholder_type=cast(
                    str | None, stakeholder.stakeholder_metadata.get("type")
                ),
            )
            for stakeholder in stakeholders
        ]

    async def _persist_assignments(
        self,
        project_id: UUID,
        assignments: list[RaciGenerationAssignment],
        known_stakeholder_ids: set[UUID] | None = None,
    ) -> None:
        if not assignments:
            return

        if known_stakeholder_ids is None:
            known_stakeholder_ids = set()

        existing_rows = await self.stakeholder_repository.list_raci_assignments(
            project_id,
            tenant_id=self.tenant_id,
        )
        existing_keys = {
            (row.wbs_item_id, row.stakeholder_id, row.raci_role) for row in existing_rows
        }

        new_rows: list[RaciAssignment] = []
        for assignment in assignments:
            if assignment.stakeholder_id not in known_stakeholder_ids:
                raise ValueError("unresolved stakeholder identity")
            key = (assignment.wbs_item_id, assignment.stakeholder_id, assignment.role)
            if key in existing_keys:
                continue
            new_rows.append(
                RaciAssignment(
                    id=uuid4(),
                    project_id=project_id,
                    tenant_id=self.tenant_id,
                    stakeholder_id=assignment.stakeholder_id,
                    wbs_item_id=assignment.wbs_item_id,
                    raci_role=assignment.role,
                    evidence_text=assignment.evidence_text,
                    generated_automatically=True,
                    manually_verified=False,
                    verified_by=None,
                    verified_at=None,
                    created_at=datetime.now(UTC),
                )
            )

        if not new_rows:
            return

        for row in new_rows:
            await self.stakeholder_repository.add_raci_assignment(
                row,
                tenant_id=self.tenant_id,
            )
        await self.stakeholder_repository.commit()
        logger.info(
            "raci_assignments_persisted",
            project_id=str(project_id),
            assignments=len(new_rows),
        )

    async def _run_optional_i10_inference(
        self,
        *,
        project_id: UUID,
        wbs_items: list[RaciWBSItemInput],
    ) -> list[str]:
        if self.raci_inference_service is None:
            return []

        contract_statements = [
            {"text": item.clause_text}
            for item in wbs_items
            if item.clause_text is not None
        ]
        _, ambiguities = await self.raci_inference_service.generate_raci_matrix(
            contract_statements=contract_statements,
            tenant_id=self.tenant_id,
            project_id=project_id,
        )
        return _build_ambiguity_warnings(ambiguities)


def _build_ambiguity_warnings(ambiguities: list[dict[str, Any]]) -> list[str]:
    labels: set[str] = set()
    for item in ambiguities:
        name = item.get("entity_name")
        if isinstance(name, str):
            normalized = " ".join(name.split()).strip().lower()
            if normalized:
                labels.add(normalized)
    return [f"ambiguous stakeholder mapping: {name}" for name in sorted(labels)]


def _merge_warnings(existing: list[str], inferred: list[str]) -> list[str]:
    """Append inferred warnings without duplicates, preserving existing order."""
    merged = list(existing)
    seen = set(existing)
    for warning in inferred:
        if warning in seen:
            continue
        merged.append(warning)
        seen.add(warning)
    return merged
