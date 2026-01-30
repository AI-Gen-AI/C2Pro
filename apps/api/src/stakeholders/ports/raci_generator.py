from __future__ import annotations

from abc import ABC, abstractmethod

from src.stakeholders.application.dtos import (
    RaciGenerationResult,
    RaciStakeholderInput,
    RaciWBSItemInput,
)


class RaciGeneratorPort(ABC):
    @abstractmethod
    async def generate_assignments(
        self,
        *,
        wbs_items: list[RaciWBSItemInput],
        stakeholders: list[RaciStakeholderInput],
    ) -> RaciGenerationResult:
        ...
