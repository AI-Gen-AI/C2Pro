"""A-side S2→S4 handshake tests against the ORIGINAL, paid-run review packet.

No external provider, finance writes, project source grants, or UAT.
Set C2PRO_V41_REAL_REVIEW_PACKET to the private, SHA-pinned SEC review packet.
Absent authentic file = explicit SKIP, never a successful real-data proof.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import stat
from pathlib import Path

import pytest

from scripts.emit_v41_s2_s4_handoff import emit
from src.analysis.application.v41_s2_s4_handoff import (
    S2S4HandoffError,
    create_pending_s2_s4_manifest,
)

PACKET_SHA = "7bf753a485a92b7fc096763f7fbf623a9a1c3de878c8efa0df84030041931b43"


@pytest.fixture
def authentic_packet():
    loc = os.environ.get("C2PRO_V41_REAL_REVIEW_PACKET")
    if not loc:
        pytest.skip("Actual SEC PDF/paid-N4 offline review packet not mounted")
    blob = Path(loc).read_bytes()
    assert hashlib.sha256(blob).hexdigest() == PACKET_SHA
    return json.loads(blob)


def test_real_s2_s4_handoff_never_launders_partial_source_or_trust(authentic_packet):
    h = create_pending_s2_s4_manifest(authentic_packet)
    assert h["proposed_count"] == h["pending_human_review_count"] == 142
    assert h["validated_count"] == 0
    assert h["n2_and_sec_pdf_literal_evidence_count"] == 50
    assert h["unverified_literal_count"] == 92
    assert h["coherence_result"] == "UNASSESSED_NOT_CALLED"
    assert h["s4_provider_call_authorized"] is False
    assert h["projectgraph_promotion_authorized"] is False
    assert h["coherence_verified_manifest_sha256"] is None
    assert h["original_blob_sha256_from_current_project_db"] is None
    assert h["tenant_id_current"] is None
    assert h["project_id_current"] is None
    assert h["current_trusted_project_run_id"] is None
    assert h["score_validated"] is None and h["score_pending"] is None
    assert h["handoff_sha256"] == "734067d997bd6f6086ca3d5d11eaa280febfca7a358a75f7c2c45b87d7f86cb4"
    assert len({r["finding_key"] for r in h["item_pointers_without_quotes_or_model_text"]}) == 142
    assert len({r["n4_window_ordinal"] for r in h["item_pointers_without_quotes_or_model_text"]}) == 24
    assert all(r["review"] == "PENDING_HUMAN" for r in h["item_pointers_without_quotes_or_model_text"])
    assert "model_interpretation" not in json.dumps(h)
    assert "quote_text" not in json.dumps(h)


def test_refuse_fake_reviewed_item(authentic_packet):
    altered = copy.deepcopy(authentic_packet)
    altered["findings"][0]["review_decision"] = "CONFIRMED"
    with pytest.raises(S2S4HandoffError, match="PROPOSAL_IDENTITY_OR_REVIEW_FALSIFIED"):
        create_pending_s2_s4_manifest(altered)


def test_refuse_fake_projectgraph_permission(authentic_packet):
    altered = copy.deepcopy(authentic_packet)
    altered["projectgraph_projection_enabled"] = True
    with pytest.raises(S2S4HandoffError, match="OFFLINE_PROPOSALS_CANNOT_BECOME_HITL_OR_S4"):
        create_pending_s2_s4_manifest(altered)


def test_refuse_fake_trusted_artifact_or_n12_checkpoint(authentic_packet):
    for field in ("trusted_artifact_id", "n12_checkpoint_id", "review_row_id"):
        altered = copy.deepcopy(authentic_packet)
        altered[field] = "fake-bound-authority"
        with pytest.raises(S2S4HandoffError, match="OFFLINE_PROPOSALS_CANNOT_BECOME_HITL_OR_S4"):
            create_pending_s2_s4_manifest(altered)


def test_refuse_fabricated_pdf_page_for_unverified_risk(authentic_packet):
    altered = copy.deepcopy(authentic_packet)
    risk = next(x for x in altered["findings"] if x["source_provenance"]["quote_status"] == "NOT_VERIFIED_IN_N2")
    risk["source_provenance"]["sec_filing_page"] = 15
    with pytest.raises(S2S4HandoffError, match="UNVERIFIED_QUOTE_CANNOT_GAIN_PAGE"):
        create_pending_s2_s4_manifest(altered)


def test_refuse_duplicate_risk_fingerprint(authentic_packet):
    altered = copy.deepcopy(authentic_packet)
    altered["findings"][1]["n4_finding_key"] = altered["findings"][0]["n4_finding_key"]
    with pytest.raises(S2S4HandoffError, match="PROPOSAL_IDENTITY_OR_REVIEW_FALSIFIED"):
        create_pending_s2_s4_manifest(altered)


def test_refuse_reassigned_n2_digest(authentic_packet):
    altered = copy.deepcopy(authentic_packet)
    altered["source_sha256"] = "a" * 64
    with pytest.raises(S2S4HandoffError, match="PROPOSAL_IDENTITY_OR_REVIEW_FALSIFIED"):
        create_pending_s2_s4_manifest(altered)


def test_refuse_missing_24_window_inventory(authentic_packet):
    altered = copy.deepcopy(authentic_packet)
    changed = altered["findings"][0]["n4_window_ordinal"]
    for row in altered["findings"]:
        if row["n4_window_ordinal"] == changed:
            row["n4_window_ordinal"] = 1 if changed != 1 else 2
    with pytest.raises(S2S4HandoffError, match="N4_SOURCE_REVISION_OR_WINDOW_GAP"):
        create_pending_s2_s4_manifest(altered)


def test_real_handoff_cli_requires_exact_packet_sha_and_private_no_overwrite(
    authentic_packet, tmp_path,
):
    p = tmp_path / "n4_offline_review_packet_sec_verified.json"
    p.write_text(json.dumps(authentic_packet))
    different_sha = hashlib.sha256(p.read_bytes()).hexdigest()
    assert different_sha != PACKET_SHA  # JSON reserialization changes bytes
    with pytest.raises(S2S4HandoffError, match="REVIEW_PACKET_SHA256_MISMATCH"):
        emit(root=tmp_path, expected_packet_sha256=PACKET_SHA)
    receipt = emit(root=tmp_path, expected_packet_sha256=different_sha)
    assert receipt["s4_provider_call_authorized"] is False
    out = tmp_path / "s2_s4_handoff_manifest.json"
    assert stat.S_IMODE(out.stat().st_mode) == 0o600
    unchanged = out.read_bytes()
    with pytest.raises(S2S4HandoffError, match="HANDOFF_ALREADY_EXISTS"):
        emit(root=tmp_path, expected_packet_sha256=different_sha)
    assert out.read_bytes() == unchanged


def test_refuse_unpinned_or_missing_real_source_for_any_handoff():
    with pytest.raises(S2S4HandoffError, match="OFFLINE_PROPOSALS_CANNOT_BECOME_HITL_OR_S4"):
        create_pending_s2_s4_manifest({
            "packet_kind": "OFFLINE_N4_REVIEW_PREPARATION_NOT_HITL",
            "review_recording_enabled": True,
        })
