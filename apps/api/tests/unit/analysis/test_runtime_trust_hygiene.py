"""TS-ADR-013-GRAPH-001 - Runtime Trust hygiene checks."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4


def test_persist_node_error_event_kwargs_match_evidence_event_orm() -> None:
    """TS-ADR-013-GRAPH-001 - Error persistence kwargs must match EvidenceExtractionEventORM."""
    from src.evidence.adapters.persistence.models import EvidenceExtractionEventORM

    event = EvidenceExtractionEventORM(
        extraction_run_id=uuid4(),
        tenant_id=uuid4(),
        project_id=uuid4(),
        document_id=uuid4(),
        event_type="processing_error",
        dimension=None,
        claim_type="analysis_graph_node",
        reason="node_failed",
        payload_trace={"node_result": {"node": "n4", "status": "failed"}},
    )

    assert event.event_type == "processing_error"
    assert event.reason == "node_failed"
    assert event.payload_trace["node_result"]["node"] == "n4"


def test_helper_broad_except_comments_are_specific() -> None:
    """TS-ADR-013-GRAPH-001 - Helper broad-except comments must describe the actual fail-closed behavior."""
    source = Path("apps/api/src/analysis/adapters/graph/nodes_extended.py").read_text()

    assert "explicit NodeResult remains the source of truth" not in source
    assert "flag resolution fail-closed." not in source
