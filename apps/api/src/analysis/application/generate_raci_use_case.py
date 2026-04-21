"""
Application use case: generate a RACI matrix from extracted stakeholders
and WBS items.

Refers to EPIC-CORE-DECOUPLE / TASK-IMPL-010 Phase 2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

from src.analysis.domain.ai_extraction import (
    AIExtractionPort,
    RaciGenerationService,
)

logger = structlog.get_logger()


@dataclass(frozen=True)
class GenerateRaciCommand:
    stakeholders: list[dict[str, Any]]
    wbs_items: list[dict[str, Any]]


@dataclass(frozen=True)
class GenerateRaciUseCase:
    ai: AIExtractionPort
    service: RaciGenerationService = field(default_factory=RaciGenerationService)

    async def execute(self, cmd: GenerateRaciCommand) -> list[dict[str, Any]]:
        if not cmd.stakeholders or not cmd.wbs_items:
            return []
        try:
            matrix = await self.service.generate(
                stakeholders=cmd.stakeholders,
                wbs_items=cmd.wbs_items,
                ai=self.ai,
            )
        except Exception:
            logger.warning("generate_raci_use_case_failed", exc_info=True)
            return []
        return matrix if isinstance(matrix, list) else [matrix]
