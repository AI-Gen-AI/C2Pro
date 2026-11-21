"""Dedicated N4-only UAT pipeline: N1 -> N2 -> governed N4 -> END.

The graph contains NO N12, HITL, N8, N17 or trust transition nodes. The
normal N1-N17 workflow is unchanged. The only billable node reuses the
existing fenced N4IncrementalRunner and transactional budget ledger.
"""
from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
from typing import Any, cast

from langgraph.graph import END, StateGraph

from src.analysis.adapters.graph.n4_governed_bridge import _identity, _limits
from src.analysis.adapters.graph.nodes import risk_extractor_node
from src.analysis.adapters.graph.nodes_extended import (
    document_ingestion_node,
    pii_anonymizer_node,
)
from src.analysis.adapters.graph.schema import ProjectState
from src.analysis.application.n4_only_pilot_policy import (
    N4OnlyPilotDenied,
    require_marked_pilot,
)
from src.analysis.domain.n4_source_windows import plan_n4_source_windows
from src.core.processing_authority import ProcessingStage, current_authority


def attest_n4_pilot_input(state: Mapping[str, Any]) -> None:
    """Reject mismatched generations, source SHA, and stale/unapproved fences BEFORE N4."""
    authority = current_authority()
    if authority is None or authority.stage is not ProcessingStage.ANALYSIS:
        raise N4OnlyPilotDenied("N4 pilot requires an active ANALYSIS grant")
    if state.get("doc_type") != "contract":
        raise N4OnlyPilotDenied("N4 pilot is restricted to the approved contract")
    scope = require_marked_pilot(
        state.get("n4_only_pilot"),
        tenant_id=state.get("tenant_id"),
        project_id=state.get("project_id"),
        document_id=state.get("document_id"),
        revision_id=state.get("document_revision_id"),
        generation=authority.generation,
    )
    if authority.fencing_token <= scope.predecessor_fence:
        raise N4OnlyPilotDenied("pilot fence did not advance beyond signed predecessor")
    _, project, projection = _identity(state)  # N2 and parsed-text provenance guard
    if project != scope.project_id or sha256(projection.encode("utf-8")).hexdigest() != scope.source_sha256:
        raise N4OnlyPilotDenied("N4 pilot projection SHA does not match approved R1")
    # Parse the EXACT pinned N2 source with the real runner's own splitting
    # configuration before reserve_call can reserve a cent. Natural paragraph
    # boundaries may yield 23 actual windows where no-break fixtures yield 22.
    _run_cap, _window_reservation, max_chars, overlap = _limits()
    planned = plan_n4_source_windows(
        projection, revision_id=str(scope.revision_id),
        max_context_chars=max_chars, overlap_chars=overlap,
    )
    if (
        len(planned) != scope.expected_windows
        or planned[0].core_start != 0
        or planned[-1].core_end != len(projection)
        or any(a.core_end != b.core_start for a, b in zip(planned, planned[1:], strict=False))
    ):
        raise N4OnlyPilotDenied("N4 pilot source-window inventory changed; no reservation permitted")


async def n4_only_risk_node(state: ProjectState) -> ProjectState:
    attest_n4_pilot_input(state)
    return await risk_extractor_node(state)


def build_n4_only_workflow() -> StateGraph[ProjectState, None, ProjectState, ProjectState]:
    """An independent topology, not an N12 escape hatch or workflow_terminated spoof."""
    graph = StateGraph(ProjectState)
    graph.add_node("document_ingestion", document_ingestion_node)
    graph.add_node("pii_anonymizer", pii_anonymizer_node)
    graph.add_node("risk_extractor", n4_only_risk_node)
    graph.set_entry_point("document_ingestion")
    graph.add_edge("document_ingestion", "pii_anonymizer")
    graph.add_edge("pii_anonymizer", "risk_extractor")
    graph.add_edge("risk_extractor", END)
    return graph


class N4OnlyPilotIncomplete(RuntimeError):
    """No success state or new provider attempt is inferred from partial N4 rows."""


async def run_n4_only_pilot(initial_state: dict[str, Any]) -> dict[str, Any]:
    """Run one authorized pilot; N4 receipts/findings persist in its own ledger.

    No LangGraph checkpoint writes are needed: N4's fenced SQL ledger is the
    durable retry source. A replay re-enters N1/N2 and revalidates source
    identity before reaching any N4 reservation.
    """
    if not isinstance(initial_state.get("n4_only_pilot"), dict):
        raise N4OnlyPilotDenied("no server-issued N4-only pilot marker")
    # Graph topology is fail-closed; N12 and HITL are not registered at all.
    result = await build_n4_only_workflow().compile().ainvoke(cast(ProjectState, initial_state))
    if result.get("workflow_terminated") is True:
        raise N4OnlyPilotIncomplete("N4 ledger incomplete or provider failed")
    coverage = result.get("n4_incremental_window_coverage") or {}
    if (
        not isinstance(coverage, dict)
        or type(coverage.get("examined")) is not int
        or type(coverage.get("total")) is not int
        or coverage["examined"] != coverage["total"]
        or coverage["total"] <= 0
        or not result.get("n4_incremental_run_id")
    ):
        raise N4OnlyPilotIncomplete("N4 did not persist all receipts/windows")
    # PROPOSED is a research artifact, never a trusted/approved analysis.
    status = (
        "PROPOSED_N12_UNASSESSED"
        if result.get("extracted_risks")
        else "NO_FINDINGS_UNASSESSED"
    )
    return {
        "n4_only_pilot_status": status,
        "n4_incremental_run_id": result["n4_incremental_run_id"],
        "n4_incremental_window_coverage": coverage,
        "n12_status": "UNASSESSED",
        "pdf_original_coverage": "UNVERIFIED",
        "coherence_score": None,
        "confidence_score": None,
        "hitl_generated": False,
        "trust_state": "PROPOSED",
    }
