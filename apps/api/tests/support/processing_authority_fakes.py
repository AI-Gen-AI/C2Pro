"""A permissive, in-memory #711 processing-authority double for DB-less tests.

DB-less unit tests drive ingestion/analysis against fake sessions, where the
real authority SQL has nothing to run on. This double grants every invocation
ownership so those tests keep exercising what they are about (status
truthfulness, redelivery short-circuits, retry flags, loop lifecycles).

It proves NOTHING about fencing. The stale-writer fence is proven against a
real PostgreSQL in tests/integration/document_flow/
test_711_processing_attempt_fence.py.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from src.core import processing_authority as real
from src.core.processing_authority import (
    AcquireOutcome,
    AcquireResult,
    ProcessingAuthority,
    ProcessingStage,
)


class PermissiveProcessingAuthority:
    @staticmethod
    def bound_authority(_authority: Any) -> Any:
        # Bind nothing: graph seams stay unfenced in these tests (their
        # fake grants have no row to verify against).
        return real.bound_authority(None)

    def __init__(self) -> None:
        self.grants: list[ProcessingAuthority] = []
        self.settled: list[dict[str, Any]] = []

    async def acquire(
        self,
        _session: Any,
        *,
        tenant_id: UUID,
        document_id: UUID,
        stage: ProcessingStage,
        revision_id: UUID | None = None,
        generation: int | None = None,
    ) -> AcquireResult:
        authority = ProcessingAuthority(
            tenant_id=tenant_id,
            document_id=document_id,
            revision_id=revision_id,
            generation=generation or 1,
            stage=stage,
            attempt_id=uuid4(),
            owner_token=uuid4(),
            fencing_token=len(self.grants) + 1,
        )
        self.grants.append(authority)
        return AcquireResult(AcquireOutcome.ACQUIRED, authority, authority.generation)

    async def adopt(self, _session: Any, _authority: ProcessingAuthority) -> bool:
        return True

    async def heartbeat(self, _session: Any, _authority: ProcessingAuthority) -> bool:
        return True

    async def verify_in_transaction(self, _session: Any, _authority: ProcessingAuthority) -> None:
        return None

    async def finish_ingestion(self, _session: Any, _authority: ProcessingAuthority) -> None:
        return None

    async def settle(self, _session: Any, _authority: ProcessingAuthority, **kwargs: Any) -> None:
        self.settled.append(kwargs)


def install_permissive_authority(monkeypatch: Any) -> PermissiveProcessingAuthority:
    """Replace ``ingestion_tasks.processing_authority`` for a mock-session test."""
    from src.core.tasks import ingestion_tasks

    double = PermissiveProcessingAuthority()
    monkeypatch.setattr(ingestion_tasks, "processing_authority", double)
    return double
