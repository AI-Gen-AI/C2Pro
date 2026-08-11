"""
Port: routing policy repository (ADR-020, TASK-V3-020-02).
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.modules.hitl.domain.routing_policy import RoutingPolicy


class IRoutingPolicyRepository(Protocol):
    async def get_policy(self, tenant_id: UUID, doc_type: str) -> RoutingPolicy: ...


__all__ = ["IRoutingPolicyRepository"]
