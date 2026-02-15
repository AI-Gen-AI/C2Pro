"""
I10 Stakeholders Domain Services
Test Suite ID: TS-I10-STKH-DOM-001
"""

from uuid import uuid4

from src.modules.stakeholders.domain.entities import (
    PartyResolutionResult,
    RACIActivity,
    RACIRole,
    Stakeholder,
)


class StakeholderResolver:
    """Resolves stakeholder mentions to canonical entities."""

    def resolve_entity(
        self,
        entity_name: str,
        existing_stakeholders: list[Stakeholder],
    ) -> PartyResolutionResult:
        query = entity_name.strip().lower()
        matches = []
        for stakeholder in existing_stakeholders:
            names = {stakeholder.name.strip().lower(), *{alias.strip().lower() for alias in stakeholder.aliases}}
            if query in names:
                matches.append(stakeholder)

        if len(matches) == 1:
            stakeholder = matches[0]
            return PartyResolutionResult(
                original_name=entity_name,
                resolved_stakeholder_id=stakeholder.id,
                canonical_id=stakeholder.canonical_id,
                ambiguity_flag=False,
                action="merged",
            )

        if len(matches) > 1:
            return PartyResolutionResult(
                original_name=entity_name,
                resolved_stakeholder_id=None,
                canonical_id=uuid4(),
                ambiguity_flag=True,
                action="new_with_canonical",
                warning_message="Ambiguous stakeholder mapping; human validation required.",
            )

        return PartyResolutionResult(
            original_name=entity_name,
            resolved_stakeholder_id=None,
            canonical_id=uuid4(),
            ambiguity_flag=False,
            action="new",
        )


class RACIValidator:
    """Validates RACI constraints per activity."""

    def validate_activity_raci(self, activity: RACIActivity) -> list[str]:
        violations: list[str] = []
        accountable_count = sum(1 for r in activity.responsibilities if r.role == RACIRole.ACCOUNTABLE)
        if accountable_count != 1:
            violations.append("Exactly one Accountable assignment is required per activity.")
        return violations

