"""
In-memory golden candidate repository (ADR-020, TASK-V3-020-04).
"""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from src.modules.hitl.domain.golden_candidate import GoldenCandidate, GoldenCandidateStatus


class InMemoryGoldenCandidateRepository:
    def __init__(self) -> None:
        self._by_id: dict[UUID, GoldenCandidate] = {}
        self._by_queue: dict[UUID, list[GoldenCandidate]] = defaultdict(list)

    async def add_candidate(self, candidate: GoldenCandidate) -> None:
        self._by_id[candidate.candidate_id] = candidate
        self._by_queue[candidate.queue_entry_id].append(candidate)

    async def get_candidate(self, candidate_id: UUID) -> GoldenCandidate | None:
        return self._by_id.get(candidate_id)

    async def list_by_status(self, status: GoldenCandidateStatus) -> list[GoldenCandidate]:
        return [c for c in self._by_id.values() if c.status == status]

    async def list_by_queue_entry(self, queue_entry_id: UUID) -> list[GoldenCandidate]:
        return list(self._by_queue.get(queue_entry_id, []))


__all__ = ["InMemoryGoldenCandidateRepository"]
