"""
Module Boundary Handover Tests (TDD - RED Phase)

Refers to Suite IDs: TS-INT-MOD-DOC-001, TS-INT-MOD-STK-001.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import pytest
from unittest.mock import AsyncMock


# ---------------------------------------------------------------------------
# DTO Contract (Stakeholders -> RACI)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StakeholderDTO:
    id: str
    name: str
    role: str


class FakeRaciGenerator:
    """Simulates Analysis RACI Generator consuming StakeholderDTOs."""

    def generate_matrix(self, stakeholders: list[StakeholderDTO]) -> dict:
        columns = [s.id for s in stakeholders]
        return {"columns": columns, "rows": []}


# ---------------------------------------------------------------------------
# Event Bus Contract (Documents -> Analysis)
# ---------------------------------------------------------------------------


class FakeDocumentsProcessor:
    """Simulates Documents module publishing processed event."""

    def __init__(self, event_bus):
        self.event_bus = event_bus

    async def process_completed(self, document_id: str, tenant_id: str) -> None:
        payload = {"document_id": document_id, "tenant_id": tenant_id}
        await self.event_bus.publish("documents.processed", payload)


class TestDocumentsToAnalysisIntegration:
    """Refers to Suite ID: TS-INT-MOD-DOC-001."""

    @pytest.mark.asyncio
    async def test_documents_processed_event_is_published_with_thin_payload(self):
        event_bus = AsyncMock()
        processor = FakeDocumentsProcessor(event_bus)

        document_id = str(uuid4())
        tenant_id = str(uuid4())

        await processor.process_completed(document_id=document_id, tenant_id=tenant_id)

        event_bus.publish.assert_awaited_once_with(
            "documents.processed",
            {"document_id": document_id, "tenant_id": tenant_id},
        )

        payload = event_bus.publish.call_args[0][1]
        assert set(payload.keys()) == {"document_id", "tenant_id"}


class TestStakeholdersToRaciIntegration:
    """Refers to Suite ID: TS-INT-MOD-STK-001."""

    def test_raci_generator_consumes_stakeholder_dtos(self):
        stakeholders = [
            StakeholderDTO(id=str(uuid4()), name="Alice", role="Owner"),
            StakeholderDTO(id=str(uuid4()), name="Bob", role="PM"),
            StakeholderDTO(id=str(uuid4()), name="Carol", role="Engineer"),
        ]

        generator = FakeRaciGenerator()
        matrix = generator.generate_matrix(stakeholders)

        assert matrix["columns"] == [s.id for s in stakeholders]

    def test_stakeholder_dto_is_immutable_and_not_orm(self):
        dto = StakeholderDTO(id=str(uuid4()), name="Alice", role="Owner")

        with pytest.raises(Exception):
            dto.name = "Mutated"

        assert "adapters.persistence.models" not in type(dto).__module__
