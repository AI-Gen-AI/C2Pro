"""
I10 Stakeholders application contracts (ports) and compatibility exports.
Test Suite ID: TS-I10-STKH-APP-001
"""

from abc import ABC, abstractmethod
from typing import Any, Protocol
from uuid import UUID

from src.modules.stakeholders.domain.entities import (
    Stakeholder,
)
from src.modules.stakeholders.application.raci_inference_service import RACIInferenceService


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


__all__ = [
    "LLMGeneratorAdapter",
    "StakeholderRepository",
    "RACIInferenceService",
]
