"""
In-memory routing policy repository (ADR-020, TASK-V3-020-02).

Holds a default policy and optional per-(tenant_id, doc_type) overrides.
Suitable for testing and single-tenant deployments; a database-backed
implementation can be substituted later without changing callers.
"""

from __future__ import annotations

from uuid import UUID

from src.modules.hitl.domain.routing_policy import DEFAULT_ROUTING_POLICY, RoutingPolicy


class InMemoryRoutingPolicyRepository:
    def __init__(
        self,
        default_policy: RoutingPolicy = DEFAULT_ROUTING_POLICY,
        overrides: dict[tuple[UUID, str], RoutingPolicy] | None = None,
    ) -> None:
        self._default = default_policy
        self._overrides: dict[tuple[UUID, str], RoutingPolicy] = overrides or {}

    async def get_policy(self, tenant_id: UUID, doc_type: str) -> RoutingPolicy:
        return self._overrides.get((tenant_id, doc_type), self._default)


__all__ = ["InMemoryRoutingPolicyRepository"]
