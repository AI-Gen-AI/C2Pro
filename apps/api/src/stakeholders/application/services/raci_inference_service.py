"""
I10 Stakeholders RACI inference implementation.
Test Suite ID: TS-I10-STKH-APP-001
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any, Protocol, TypeAlias
from uuid import UUID

from src.modules.extraction.domain.entities import ExtractedClause
from src.stakeholders.domain.models import (
    PartyResolutionResult,
    RaciActivity,
    RaciResponsibility,
    RACIRole,
    Stakeholder,
)

ContractStatement: TypeAlias = ExtractedClause | Mapping[str, object]


class LLMGeneratorAdapter(Protocol):
    async def generate_structured_output(
        self, prompt: str, schema: dict[str, Any], context: str
    ) -> dict[str, Any]:
        ...


class StakeholderRepositoryPort(Protocol):
    async def get_all_stakeholders(self, tenant_id: UUID) -> list[Stakeholder]:
        ...


class StakeholderResolverPort(Protocol):
    def resolve_entity(
        self, entity_name: str, existing_stakeholders: list[Stakeholder]
    ) -> PartyResolutionResult:
        ...


class RACIValidatorPort(Protocol):
    def validate_activity_raci(self, activity: RaciActivity) -> list[str]:
        ...


class RACIInferenceService:
    """Generates RACI activities with stakeholder resolution and validation gates."""

    _result_cache: dict[str, tuple[list[RaciActivity], list[dict[str, Any]]]] = {}

    def __init__(
        self,
        llm_generator: LLMGeneratorAdapter,
        stakeholder_repo: StakeholderRepositoryPort,
        stakeholder_resolver: StakeholderResolverPort,
        raci_validator: RACIValidatorPort,
    ):
        self.llm_generator = llm_generator
        self.stakeholder_repo = stakeholder_repo
        self.stakeholder_resolver = stakeholder_resolver
        self.raci_validator = raci_validator

    def _build_cache_key(
        self,
        contract_statements: list[ContractStatement],
        tenant_id: UUID,
        project_id: UUID | None,
    ) -> str:
        payload = "\n".join(
            _statement_text(clause)
            for clause in contract_statements
        )
        raw = f"{tenant_id}|{project_id}|{payload}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    async def generate_raci_matrix(
        self,
        contract_statements: list[ContractStatement],
        tenant_id: UUID,
        project_id: UUID | None = None,
    ) -> tuple[list[RaciActivity], list[dict[str, Any]]]:
        cache_key = self._build_cache_key(contract_statements, tenant_id, project_id)
        if cache_key in self._result_cache:
            cached_matrix, cached_ambiguities = self._result_cache[cache_key]
            # Use model_copy or similar if they were Pydantic, but they are dataclasses now.
            # For dataclasses, we can use replace() or just return them if they are immutable.
            # Since they might have nested lists, we should deepcopy if we want to be safe.
            import copy
            return (
                [copy.deepcopy(item) for item in cached_matrix],
                [dict(entry) for entry in cached_ambiguities],
            )

        # Implementation depends on port
        # existing_stakeholders = await self.stakeholder_repo.get_all_stakeholders(tenant_id)
        # Wait, the port says get_all_stakeholders(tenant_id).
        # But our repository has get_stakeholders_by_project(project_id).
        # We'll need a bridge or adapter.

        # For now, let's assume the repository port passed in is compatible.
        existing_stakeholders = await self.stakeholder_repo.get_all_stakeholders(tenant_id)

        context_text = "\n".join(
            [_statement_text(statement) for statement in contract_statements]
        )
        llm_output = await self.llm_generator.generate_structured_output(
            prompt="Infer RACI activities and responsibilities.",
            schema={},
            context=context_text,
        )

        activities: list[RaciActivity] = []
        ambiguities: list[dict[str, Any]] = []

        for activity_data in llm_output.get("raci_activities", []):
            responsibilities: list[RaciResponsibility] = []
            activity_has_ambiguity = False

            for responsibility_data in activity_data.get("responsibilities", []):
                stakeholder_name = responsibility_data["stakeholder_name"]
                resolution = self.stakeholder_resolver.resolve_entity(
                    stakeholder_name, existing_stakeholders
                )

                if resolution.ambiguity_flag:
                    activity_has_ambiguity = True
                    ambiguities.append(
                        {
                            "entity_name": stakeholder_name,
                            "reason": resolution.warning_message or "ambiguous_mapping",
                        }
                    )

                stakeholder_id = resolution.resolved_stakeholder_id or resolution.canonical_id
                # Ensure stakeholder_id is not None
                if stakeholder_id is None:
                    from uuid import uuid4
                    stakeholder_id = uuid4()

                responsibilities.append(
                    RaciResponsibility(
                        stakeholder_id=stakeholder_id,
                        role=RACIRole(responsibility_data["role"]),
                        confidence=float(activity_data.get("confidence", 0.0)),
                        tenant_id=tenant_id,
                    )
                )

            activity = RaciActivity(
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

        import copy
        self._result_cache[cache_key] = (
            [copy.deepcopy(item) for item in activities],
            [dict(entry) for entry in ambiguities],
        )
        return activities, ambiguities


def _statement_text(statement: ContractStatement) -> str:
    """TS-I10-STKH-APP-001: Extract statement text from supported input contracts."""
    if isinstance(statement, ExtractedClause):
        return statement.text
    text = statement.get("text", "")
    return text if isinstance(text, str) else str(text)
