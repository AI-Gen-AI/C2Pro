"""Serial ProjectGraph skeleton for ADR-017 Tier-2.

TS-UT-ADR017-PG-001
"""

from __future__ import annotations

from uuid import UUID

import structlog
from langgraph.graph import END, StateGraph

from src.analysis.adapters.graph.project_graph_state import ProjectGraphState
from src.analysis.domain.contracts import DocumentArtifact
from src.analysis.domain.node_result import NodeResult, NodeStatus

logger = structlog.get_logger(__name__)

PROJECT_GRAPH_NODE_ORDER = [
    "load_current_artifacts",
    "align_entities",
    "cross_doc_coherence",
    "change_impact",
    "health",
    "snapshot_delta",
    "write_snapshot",
    "alert_correlation",
    "hitl_routing",
]


def _ok(node: str, data: object = None) -> list[NodeResult]:
    return [NodeResult(node=node, status=NodeStatus.OK, data=data)]


def _skipped(node: str, reason: str) -> list[NodeResult]:
    return [NodeResult(node=node, status=NodeStatus.SKIPPED, degradation_reason=reason)]


def _artifact_key(artifact: DocumentArtifact) -> str:
    return artifact.document_revision_id or artifact.document_id


def load_current_artifacts(state: ProjectGraphState) -> dict[str, object]:
    artifacts = state.get("artifacts", [])
    return {
        "artifacts": artifacts,
        "node_results": _ok("load_current_artifacts", {"artifact_count": len(artifacts)}),
    }


def align_entities(state: ProjectGraphState) -> dict[str, object]:
    anchors_by_doc_type: dict[str, list[str]] = {}
    for artifact in state.get("artifacts", []):
        anchors_by_doc_type.setdefault(artifact.doc_type, []).append(_artifact_key(artifact))
    return {
        "node_results": _ok(
            "align_entities",
            {"doc_type_groups": anchors_by_doc_type},
        )
    }


def cross_doc_coherence(_state: ProjectGraphState) -> dict[str, object]:
    return {
        "coherence_result": None,
        "node_results": _skipped(
            "cross_doc_coherence",
            "pending ADR-017-04 cross-document coherence",
        ),
    }


def change_impact(_state: ProjectGraphState) -> dict[str, object]:
    return {
        "impact_result": None,
        "node_results": _skipped("change_impact", "pending ADR-016-L3 change impact"),
    }


def health(_state: ProjectGraphState) -> dict[str, object]:
    return {
        "health_result": None,
        "node_results": _skipped("health", "pending ADR-018 health computation"),
    }


def snapshot_delta(state: ProjectGraphState) -> dict[str, object]:
    changed_artifact_ids = [_artifact_key(artifact) for artifact in state.get("artifacts", [])]
    return {
        "changed_artifact_ids": changed_artifact_ids,
        "node_results": _ok(
            "snapshot_delta",
            {
                "changed_artifact_count": len(changed_artifact_ids),
                "previous_snapshot_id": str(state.get("previous_snapshot_id"))
                if state.get("previous_snapshot_id") is not None
                else None,
            },
        ),
    }


def write_snapshot(_state: ProjectGraphState) -> dict[str, object]:
    return {
        "snapshot_id": None,
        "node_results": _skipped("write_snapshot", "pending ADR-015 snapshot write"),
    }


def alert_correlation(_state: ProjectGraphState) -> dict[str, object]:
    return {
        "node_results": _skipped("alert_correlation", "pending ADR-019 alert correlation"),
    }


def hitl_routing(_state: ProjectGraphState) -> dict[str, object]:
    return {
        "node_results": _skipped("hitl_routing", "pending ADR-020 HITL routing"),
    }


async def is_project_graph_enabled(tenant_id: UUID) -> bool:
    """Resolve the per-tenant ProjectGraph gate, failing closed."""

    try:
        from src.alerts.adapters.persistence.tenant_repository import (
            SqlAlchemyTenantRepository,
        )
        from src.config import settings
        from src.core.database import get_raw_session
        from src.core.feature_flags import TenantFlagsService

        async with get_raw_session() as session:
            return await TenantFlagsService(
                tenant_repository=SqlAlchemyTenantRepository(session),
                settings=settings,
            ).is_enabled(tenant_id, "feature_v3_project_graph")
    except Exception as exc:  # noqa: BLE001 - live ProjectGraph invocation must fail closed.
        logger.warning(
            "feature_v3_project_graph_resolution_failed",
            tenant_id=str(tenant_id),
            error=str(exc),
        )
        return False


def build_project_graph():
    """Build the serial Tier-2 graph skeleton."""

    workflow = StateGraph(ProjectGraphState)
    workflow.add_node("load_current_artifacts", load_current_artifacts)
    workflow.add_node("align_entities", align_entities)
    workflow.add_node("cross_doc_coherence", cross_doc_coherence)
    workflow.add_node("change_impact", change_impact)
    workflow.add_node("health", health)
    workflow.add_node("snapshot_delta", snapshot_delta)
    workflow.add_node("write_snapshot", write_snapshot)
    workflow.add_node("alert_correlation", alert_correlation)
    workflow.add_node("hitl_routing", hitl_routing)

    workflow.set_entry_point("load_current_artifacts")
    workflow.add_edge("load_current_artifacts", "align_entities")
    workflow.add_edge("align_entities", "cross_doc_coherence")
    workflow.add_edge("cross_doc_coherence", "change_impact")
    workflow.add_edge("change_impact", "health")
    workflow.add_edge("health", "snapshot_delta")
    workflow.add_edge("snapshot_delta", "write_snapshot")
    workflow.add_edge("write_snapshot", "alert_correlation")
    workflow.add_edge("alert_correlation", "hitl_routing")
    workflow.add_edge("hitl_routing", END)
    return workflow.compile()


__all__ = [
    "PROJECT_GRAPH_NODE_ORDER",
    "build_project_graph",
    "is_project_graph_enabled",
]
