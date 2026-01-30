from __future__ import annotations

from src.analysis.adapters.ai.agents.raci_generator import (
    RaciGeneratorAgent,
    StakeholderInput as AgentStakeholderInput,
    WBSItemInput as AgentWBSItemInput,
)
from src.stakeholders.application.dtos import (
    RaciGenerationAssignment,
    RaciGenerationResult,
    RaciStakeholderInput,
    RaciWBSItemInput,
)
from src.stakeholders.ports.raci_generator import RaciGeneratorPort


class RaciGeneratorAdapter(RaciGeneratorPort):
    def __init__(self, *, tenant_id: str | None) -> None:
        self._agent = RaciGeneratorAgent(tenant_id=tenant_id)

    async def generate_assignments(
        self,
        *,
        wbs_items: list[RaciWBSItemInput],
        stakeholders: list[RaciStakeholderInput],
    ) -> RaciGenerationResult:
        agent_wbs = [
            AgentWBSItemInput(
                id=item.id,
                name=item.name,
                description=item.description,
                clause_text=item.clause_text,
            )
            for item in wbs_items
        ]
        agent_stakeholders = [
            AgentStakeholderInput(
                id=item.id,
                name=item.name,
                role=item.role,
                company=item.company,
                stakeholder_type=item.stakeholder_type,
            )
            for item in stakeholders
        ]
        result = await self._agent.generate_assignments(
            wbs_items=agent_wbs,
            stakeholders=agent_stakeholders,
        )
        return RaciGenerationResult(
            assignments=[
                RaciGenerationAssignment(
                    wbs_item_id=assignment.wbs_item_id,
                    stakeholder_id=assignment.stakeholder_id,
                    role=assignment.role,
                    evidence_text=assignment.evidence_text,
                )
                for assignment in result.assignments
            ],
            warnings=list(result.warnings),
        )
