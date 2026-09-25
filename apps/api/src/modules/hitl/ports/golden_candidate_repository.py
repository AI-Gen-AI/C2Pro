"""
Port: golden candidate repository (ADR-020, TASK-V3-020-04).
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.modules.hitl.domain.golden_candidate import GoldenCandidate, GoldenCandidateStatus


class IGoldenCandidateRepository(Protocol):
    async def add_candidate(self, candidate: GoldenCandidate) -> None: ...

    async def get_candidate(self, candidate_id: UUID) -> GoldenCandidate | None: ...

    async def list_by_status(
        self, status: GoldenCandidateStatus
    ) -> list[GoldenCandidate]: ...

    async def list_by_queue_entry(
        self, queue_entry_id: UUID
    ) -> list[GoldenCandidate]: ...


__all__ = ["IGoldenCandidateRepository"]
