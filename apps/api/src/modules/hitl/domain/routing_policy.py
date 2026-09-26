"""
Routing policy domain model (ADR-020, TASK-V3-020-02).

Replaces hardcoded confidence/impact thresholds with a per-tenant /
per-doc-type configurable policy. The default values preserve the
existing behaviour so migrating callers is a no-op.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RoutingPolicy:
    """Confidence + impact thresholds and automation-boundary rules for HITL routing."""

    low_confidence_threshold: float = 0.3
    high_confidence_threshold: float = 0.8
    high_impact_threshold: float = 0.5
    auto_approve_item_types: frozenset[str] = field(default_factory=frozenset)


DEFAULT_ROUTING_POLICY = RoutingPolicy()

__all__ = ["DEFAULT_ROUTING_POLICY", "RoutingPolicy"]
