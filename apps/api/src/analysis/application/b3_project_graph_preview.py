"""Read-only B3 candidate source preview with two actual ProjectGraph nodes.

Never changes Celery, database, runtime upload policy or Coherence. Intentionally
supplies no TRUSTED artifacts and no source-unit payload. This evaluates
source inventory plumbing, NOT a full document journey or cross-document score.
"""
from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Any
from uuid import UUID

from src.analysis.application.b3_source_inventory_bridge import B3SourceBridgeError

_SHA = re.compile(r"[0-9a-f]{64}")


def _validated_b3_refs(packet: Mapping[str, Any], *, project_id: UUID, tenant_id: UUID) -> list[dict[str, Any]]:
    if packet.get("tenant_id") != str(tenant_id) or packet.get("project_id") != str(project_id):
        raise B3SourceBridgeError("B3 packet tenant/project mismatch")
    if (
        packet.get("source_authority") != "CANDIDATE_UNVALIDATED"
        or packet.get("effects_allowed") is not False
        or packet.get("trusted_promotions") != 0
        or packet.get("coherence_score") is not None
        or packet.get("projectgraph_scoring") != "BLOCKED_NO_TRUSTED_PROJECTION"
    ):
        raise B3SourceBridgeError("B3 packet improperly claims trusted authority")
    refs = packet.get("structured_source_refs")
    if not isinstance(refs, list) or not refs or packet.get("source_count") != len(refs):
        raise B3SourceBridgeError("invalid B3 source inventory")
    output = []
    seen: set[tuple[str, str, str]] = set()
    for ref in refs:
        if not isinstance(ref, dict) or ref.get("family") not in {"contract", "schedule", "budget"}:
            raise B3SourceBridgeError("unknown B3 source family")
        if (
            ref.get("tenant_id") != str(tenant_id)
            or ref.get("project_id") != str(project_id)
            or ref.get("role") != "SOURCE_EVIDENCE_ONLY_NOT_PROJECTED"
        ):
            raise B3SourceBridgeError("source reference crosses scope or authority")
        document_id, revision_id = ref.get("document_id"), ref.get("revision_id")
        try:
            UUID(document_id)
            UUID(revision_id)
        except (TypeError, ValueError, AttributeError) as exc:
            raise B3SourceBridgeError("invalid B3 document/revision UUID") from exc
        sha = ref.get("blob_sha256")
        if not isinstance(sha, str) or not _SHA.fullmatch(sha):
            raise B3SourceBridgeError("B3 source SHA missing")
        identity = (ref["family"], document_id, revision_id)
        if identity in seen:
            raise B3SourceBridgeError("duplicate B3 source revision")
        seen.add(identity)
        safe = {
            key: ref[key] for key in (
                "family", "tenant_id", "project_id", "document_id",
                "revision_id", "blob_sha256", "role",
            )
        }
        if "observed_source_rows" in ref:
            count = ref["observed_source_rows"]
            if not isinstance(count, int) or isinstance(count, bool) or count < 1:
                raise B3SourceBridgeError("invalid B3 source row count")
            safe["observed_source_rows"] = count
        output.append(safe)
    if sum(r["family"] == "contract" for r in output) != 1:
        raise B3SourceBridgeError("exactly one contract source required")
    return output


async def preview_b3_sources_in_project_graph(
    *,
    packet: Mapping[str, Any],
    project_id: UUID,
    tenant_id: UUID,
    graph_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Execute two source-only nodes reused from the real ProjectGraph.

    A separate compiled graph includes ONLY load_current_artifacts and
    align_entities. No health, Coherence, snapshot or alert nodes can run.
    Inject graph_factory in tests only.
    """
    refs = _validated_b3_refs(packet, project_id=project_id, tenant_id=tenant_id)
    if graph_factory is None:
        # Build a narrowly scoped graph from the ACTUAL read-only core nodes.
        # Never run the full ProjectGraph: its later nodes may acquire
        # persistence/alert side effects as the product evolves.
        from langgraph.graph import END, StateGraph
        from src.analysis.adapters.graph.project_graph import (
            load_current_artifacts, align_entities,
        )
        from src.analysis.adapters.graph.project_graph_state import ProjectGraphState

        def _read_only_graph():
            workflow = StateGraph(ProjectGraphState)
            workflow.add_node("load_current_artifacts", load_current_artifacts)
            workflow.add_node("align_entities", align_entities)
            workflow.set_entry_point("load_current_artifacts")
            workflow.add_edge("load_current_artifacts", "align_entities")
            workflow.add_edge("align_entities", END)
            return workflow.compile()

        graph_factory = _read_only_graph

    initial = {
        "tenant_id": tenant_id,
        "project_id": project_id,
        "trigger_event_id": None,
        "previous_snapshot_id": None,
        "changed_artifact_ids": [],
        "artifacts": [],
        "canonical_project_state": None,
        "canonical_materialization_status": "no_trusted_artifacts",
        "structured_source_refs": refs,
        "structured_source_units": [],
        "structured_document_quotes": [],
        "coherence_result": None,
        "impact_result": None,
        "health_result": None,
        "snapshot_id": None,
        "node_results": [],
        "risk_source_binding_status": "NOT_CONFIGURED",
    }
    result = await graph_factory().ainvoke(initial)
    if not isinstance(result, Mapping):
        raise B3SourceBridgeError("ProjectGraph returned invalid state")
    if (
        result.get("coherence_result") is not None
        or result.get("coherence_alert_evidence") is not None
        or result.get("snapshot_id") is not None
    ):
        raise B3SourceBridgeError("untrusted B3 candidates produced scoring or effects")
    if result.get("artifacts"):
        raise B3SourceBridgeError("ProjectGraph introduced trusted artifacts")
    nodes = result.get("node_results")
    if not isinstance(nodes, list) or not nodes:
        raise B3SourceBridgeError("ProjectGraph did not execute nodes")
    states = {str(n.node): str(getattr(n.status, "value", n.status)) for n in nodes}
    if set(states) != {"load_current_artifacts", "align_entities"}:
        raise B3SourceBridgeError("B3 preview ran a node outside read-only allowlist")
    if len(nodes) != 2:
        raise B3SourceBridgeError("B3 preview node receipt count mismatch")
    if any(state.lower() != "ok" for state in states.values()):
        raise B3SourceBridgeError("B3 read-only node failed")
    return {
        "status": "SOURCE_ONLY_GRAPH_PREVIEW",
        "node_count": len(nodes),
        "node_statuses": states,
        "source_revision_count": len(refs),
        "source_families": [r["family"] for r in refs],
        "contract_n4": "NOT_RUN_BY_PREVIEW",
        "n12": "NOT_RUN_BY_PREVIEW",
        "cross_document_semantics": "NOT_ASSESSED",
        "coherence_score": None,
        "approved_artifacts": 0,
        "snapshot_written": False,
        "alerts_written": False,
        "trusted_promotions": 0,
    }


__all__ = ["preview_b3_sources_in_project_graph"]
