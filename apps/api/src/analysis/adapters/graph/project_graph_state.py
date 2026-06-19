"""Typed ProjectGraph state for ADR-017 Tier-2 skeleton.

TS-UT-ADR017-PG-001
"""

from __future__ import annotations

from typing import Annotated, TypedDict
from uuid import UUID

from src.analysis.adapters.graph.project_coherence_result import ProjectCoherenceResult
from src.analysis.adapters.graph.schema import merge_node_results
from src.analysis.domain.contracts import DocumentArtifact
from src.analysis.domain.node_result import NodeResult


class ProjectGraphState(TypedDict):
    """Small Tier-2 state, separate from the Tier-1 document graph state."""

    project_id: UUID
    tenant_id: UUID
    trigger_event_id: UUID | None
    previous_snapshot_id: UUID | None
    changed_artifact_ids: list[UUID | str]
    artifacts: list[DocumentArtifact]
    coherence_result: ProjectCoherenceResult | dict[str, object] | None
    impact_result: dict[str, object] | None
    health_result: dict[str, object] | None
    snapshot_id: UUID | None
    node_results: Annotated[list[NodeResult], merge_node_results]


__all__ = ["ProjectGraphState"]
