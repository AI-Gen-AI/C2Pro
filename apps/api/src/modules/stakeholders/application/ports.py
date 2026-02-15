"""
I10 Stakeholders Application Service
Test Suite ID: TS-I10-STKH-APP-001
"""

import hashlib
from abc import ABC, abstractmethod
from typing import Any, Protocol
from uuid import UUID

from src.modules.extraction.domain.entities import ExtractedClause
from src.modules.stakeholders.domain.entities import (
    RACIActivity,
    RACIResponsibility,
    RACIRole,
    Stakeholder,
)
from src.modules.stakeholders.domain.services import RACIValidator, StakeholderResolver


class LLMGeneratorAdapter(Protocol):
    async def generate_structured_output(self, prompt: str, schema: dict[str, Any], context: str) -> dict[str, Any]:
        ...


class StakeholderRepository(ABC):
    @abstractmethod
    async def get_all_stakeholders(self, tenant_id: UUID) -> list[Stakeholder]:
        raise NotImplementedError

    @abstractmethod
    async def add_stakeholder(self, stakeholder: Stakeholder) -> Stakeholder:
        raise NotImplementedError

    @abstractmethod
    async def update_stakeholder(self, stakeholder: Stakeholder) -> Stakeholder:
        raise NotImplementedError


class RACIInferenceService:
    """Generates RACI activities with stakeholder resolution and validation gates."""

    _result_cache: dict[str, tuple[list[RACIActivity], list[dict[str, Any]]]] = {}

    def __init__(
        self,
        llm_generator: LLMGeneratorAdapter,
        stakeholder_repo: StakeholderRepository,
        stakeholder_resolver: StakeholderResolver,
        raci_validator: RACIValidator,
    ):
        self.llm_generator = llm_generator
        self.stakeholder_repo = stakeholder_repo
        self.stakeholder_resolver = stakeholder_resolver
        self.raci_validator = raci_validator

    def _build_cache_key(
        self,
        contract_statements: list[ExtractedClause],
        tenant_id: UUID,
        project_id: UUID | None,
    ) -> str:
        payload = "\n".join(clause.text for clause in contract_statements)
        raw = f"{tenant_id}|{project_id}|{payload}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    async def generate_raci_matrix(
        self,
        contract_statements: list[ExtractedClause],
        tenant_id: UUID,
        project_id: UUID | None = None,
    ) -> tuple[list[RACIActivity], list[dict[str, Any]]]:
        cache_key = self._build_cache_key(contract_statements, tenant_id, project_id)
        if cache_key in self._result_cache:
            cached_matrix, cached_ambiguities = self._result_cache[cache_key]
            return (
                [item.model_copy(deep=True) for item in cached_matrix],
                [dict(entry) for entry in cached_ambiguities],
            )

        existing_stakeholders = await self.stakeholder_repo.get_all_stakeholders(tenant_id)
        context_text = "\n".join([c.text for c in contract_statements])
        llm_output = await self.llm_generator.generate_structured_output(
            prompt="Infer RACI activities and responsibilities.",
            schema={},
            context=context_text,
        )

        activities: list[RACIActivity] = []
        ambiguities: list[dict[str, Any]] = []

        for activity_data in llm_output.get("raci_activities", []):
            responsibilities: list[RACIResponsibility] = []
            activity_has_ambiguity = False

            for responsibility_data in activity_data.get("responsibilities", []):
                stakeholder_name = responsibility_data["stakeholder_name"]
                resolution = self.stakeholder_resolver.resolve_entity(stakeholder_name, existing_stakeholders)

                if resolution.ambiguity_flag:
                    activity_has_ambiguity = True
                    ambiguities.append(
                        {
                            "entity_name": stakeholder_name,
                            "reason": resolution.warning_message or "ambiguous_mapping",
                        }
                    )

                stakeholder_id = resolution.resolved_stakeholder_id or resolution.canonical_id
                responsibilities.append(
                    RACIResponsibility(
                        stakeholder_id=stakeholder_id,
                        role=RACIRole(responsibility_data["role"]),
                        confidence=float(activity_data.get("confidence", 0.0)),
                    )
                )

            activity = RACIActivity(
                description=activity_data["description"],
                responsibilities=responsibilities,
                confidence=float(activity_data.get("confidence", 0.0)),
                metadata={},
            )

            violations = self.raci_validator.validate_activity_raci(activity)
            if violations:
                raise ValueError("; ".join(violations))

            if activity_has_ambiguity:
                activity.metadata["requires_pmo_legal_validation"] = True
                activity.metadata["validation_reason"] = "ambiguous_stakeholder_mapping"

            activities.append(activity)

        self._result_cache[cache_key] = (
            [item.model_copy(deep=True) for item in activities],
            [dict(entry) for entry in ambiguities],
        )
        return activities, ambiguities

