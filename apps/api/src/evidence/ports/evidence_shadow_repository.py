"""
Port for shadow-mode persistence of the Evidence Intelligence Layer (ADR-011 2A.3).

Write-only by design: there is intentionally NO read method that the Coherence
Engine could use. Reading evidence claims into the engine before the Phase 5
cutover would bypass the v1 stub and falsify the shadow comparison. A separate
inspection/read port may be added later for dashboards/tests, but never wired
into the engine in this phase.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.evidence.legal.adapter import AdapterResult


class IEvidenceShadowRepository(Protocol):
    """Persists the adapter's three output channels in shadow mode.

    Implementations MUST NOT commit the session — transaction boundaries are
    owned by the caller (Unit of Work / service), per the repo-wide pattern.
    """

    async def add_batch(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        extraction_run_id: UUID,
        adapter_result: AdapterResult,
    ) -> None:
        """Stage all claims + events of one extractor run for persistence.

        Uses session.add + flush; the caller commits.
        """
        ...
