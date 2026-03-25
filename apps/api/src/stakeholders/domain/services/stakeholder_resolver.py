"""
Stakeholder entity resolution logic.

Refers to Suite ID: TS-I10-STK-DOM-001.
"""

from __future__ import annotations

from uuid import uuid4

from src.stakeholders.domain.models import PartyResolutionResult, Stakeholder


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
            # Check primary name
            names = {stakeholder.name.strip().lower() if stakeholder.name else ""}
            # Check aliases
            names.update({alias.strip().lower() for alias in stakeholder.aliases})
            
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
