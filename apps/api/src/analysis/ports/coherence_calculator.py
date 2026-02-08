"""
Port contract for Coherence calculation triggered by Analysis.

Refers to Suite ID: TS-INT-MOD-ANA-001.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


class CoherenceCalculatorPort(Protocol):
    async def calculate_from_analysis(
        self, *, project_id: UUID, tenant_id: UUID, analysis_payload: dict
    ) -> dict:
        ...
