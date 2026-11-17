"""Contract-grade checks on the ORIGINAL billed OpenAI artifact, never synthetic LLM output.

Set C2PRO_V41_REAL_EVIDENCE_JSON and C2PRO_V41_REAL_N2_SOURCE to enable.
No model, network, database, or extra cost. Test fixtures are the actual
GitHub Actions #44007355327 artifact and its pinned N2 source projection.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path

import pytest

from scripts.reconcile_v41_n4_real_artifact import (
    N4ArtifactRecoveryError,
    inspect_real_n4,
    prepare_offline_hitl_packet,
)

ARTIFACT_SHA = "549ca20b14549e7d74aee1452a33e43f8aa526036fb57a5d07cc83be55f61cad"
SOURCE_SHA = "cf8f4b7d5341b04b7aacd5532b45cf130dd689037412a08ed1e9f7e59bf555c4"
RUN_SHA = "61df7648715085112ad41dacf61565e57725b710"


@pytest.fixture
def authentic_sample():
    evidence_file = os.environ.get("C2PRO_V41_REAL_EVIDENCE_JSON")
    source_file = os.environ.get("C2PRO_V41_REAL_N2_SOURCE")
    if not evidence_file or not source_file:
        pytest.skip("Original billed GHA evidence and N2 projection not mounted")
    raw = Path(evidence_file).read_bytes()
    text = Path(source_file).read_text(encoding="utf8")
    assert hashlib.sha256(raw).hexdigest() == ARTIFACT_SHA
    assert hashlib.sha256(text.encode()).hexdigest() == SOURCE_SHA
    return json.loads(raw), text


def _inspect(evidence, text):
    return inspect_real_n4(
        evidence, text, expected_run_sha=RUN_SHA,
        expected_source_sha256=SOURCE_SHA,
    )


def test_real_billed_24_window_artifact_restores_reviewable_unapproved_proposals(authentic_sample):
    document, text = authentic_sample
    result = _inspect(document, text)
    assert result["provider_settled_receipt_windows"] == 24
    assert result["persisted_candidate_windows"] == 24
    assert result["distinct_provider_receipt_ids"] == 24
    assert result["distinct_candidate_keys"] == 142
    assert result["verified_literal_candidates"] == 50
    assert result["unverified_literal_candidates"] == 92
    assert result["legacy_n4_status"] == "PARTIAL"
    assert result["legacy_clean_examined_windows"] == 0
    assert result["approved_human_decisions"] == 0
    assert result["historical_window_states_reconstructible"] is False
    assert result["n12_status"] == "NOT_STARTED"


def test_real_billed_artifact_rejects_repeat_provider_receipt_id(authentic_sample):
    document, text = authentic_sample
    changed = copy.deepcopy(document)
    rows = changed["n4"]["receipts"]
    rows[1]["provider_request_id"] = rows[0]["provider_request_id"]
    with pytest.raises(N4ArtifactRecoveryError, match="N4_RECEIPT_UNVERIFIED_OR_DUPLICATE"):
        _inspect(changed, text)


def test_real_billed_artifact_rejects_forged_literal_quote_offset(authentic_sample):
    document, text = authentic_sample
    changed = copy.deepcopy(document)
    verified = next(
        c for c in changed["n4"]["candidates"]
        if c["claim"]["source_evidence_status"] == "EXACT_MODEL_SAFE_MATCH"
    )
    verified["source_refs"][0]["analysis_span"][0] += 1
    # The canonical finding identity also embeds the source offset; either
    # guard may reject first, and both correctly refuse the forged anchor.
    with pytest.raises(
        N4ArtifactRecoveryError,
        match="N4_(FINDING_IDENTITY_MISMATCH|LITERAL_QUOTE_AND_WINDOW_MISMATCH)",
    ):
        _inspect(changed, text)


def test_real_billed_artifact_rejects_false_human_approval(authentic_sample):
    document, text = authentic_sample
    changed = copy.deepcopy(document)
    changed["n4"]["candidates"][0]["claim"]["review_status"] = "APPROVED"
    with pytest.raises(N4ArtifactRecoveryError, match="N4_CANDIDATE_MISSING_OR_DUPLICATE"):
        _inspect(changed, text)


def test_real_billed_artifact_rejects_claim_fingerprint_tampering(authentic_sample):
    document, text = authentic_sample
    changed = copy.deepcopy(document)
    changed["n4"]["candidates"][0]["claim"]["category"] = "fabricated_category"
    with pytest.raises(N4ArtifactRecoveryError, match="N4_FINDING_IDENTITY_MISMATCH"):
        _inspect(changed, text)


def test_real_billed_artifact_rejects_provenance_digest_tampering(authentic_sample):
    document, text = authentic_sample
    changed = copy.deepcopy(document)
    item = next(
        row for row in changed["n4"]["candidates"]
        if row["claim"]["source_evidence_status"] == "EXACT_MODEL_SAFE_MATCH"
    )
    item["source_refs"][0]["quote_sha256"] = "0" * 64
    with pytest.raises(N4ArtifactRecoveryError, match="N4_LITERAL_QUOTE_AND_WINDOW_MISMATCH"):
        _inspect(changed, text)


def test_real_billed_candidate_review_packet_preserves_142_unapproved_items(authentic_sample):
    document, text = authentic_sample
    packet = prepare_offline_hitl_packet(
        document, text, expected_run_sha=RUN_SHA,
        expected_source_sha256=SOURCE_SHA,
    )
    assert packet["packet_kind"] == "OFFLINE_N4_REVIEW_PREPARATION_NOT_HITL"
    assert packet["candidate_count"] == len(packet["findings"]) == 142
    assert packet["n4_status"] == "PARTIAL"
    assert packet["n12_status"] == "NOT_STARTED"
    assert packet["review_recording_enabled"] is False
    assert packet["review_row_id"] is None
    assert packet["trusted_artifact_id"] is None
    assert packet["n12_checkpoint_id"] is None
    assert packet["projectgraph_projection_enabled"] is False
    assert packet["coherence_score_change"] is None
    assert all(f["review_decision"] is None for f in packet["findings"])
    assert len({f["n4_finding_key"] for f in packet["findings"]}) == 142

    verified = [
        f for f in packet["findings"]
        if f["source_provenance"]["quote_status"] == "VERIFIED_IN_N2"
    ]
    unverified = [
        f for f in packet["findings"]
        if f["source_provenance"]["quote_status"] == "NOT_VERIFIED_IN_N2"
    ]
    assert len(verified) == 50
    assert len(unverified) == 92
    assert all(
        text[f["source_provenance"]["analysis_span_n2"][0]:f["source_provenance"]["analysis_span_n2"][1]]
        == f["source_provenance"]["quote_text"]
        for f in verified
    )
    assert all(
        f["source_provenance"]["quote_text"] is None
        and f["source_provenance"]["analysis_span_n2"] is None
        and not f["source_provenance"]["original_pdf_page_verified"]
        for f in unverified
    )


def test_real_billed_review_cli_packet_is_private_and_never_overwritten(
    authentic_sample, tmp_path, monkeypatch,
):
    from scripts.reconcile_v41_n4_real_artifact import main

    evidence_path = Path(os.environ["C2PRO_V41_REAL_EVIDENCE_JSON"])
    source_path = Path(os.environ["C2PRO_V41_REAL_N2_SOURCE"])
    packet_path = tmp_path / "review-packet.json"
    summary_path = tmp_path / "recovery-summary.json"
    monkeypatch.setattr("sys.argv", [
        "reconcile_v41_n4_real_artifact.py",
        "--evidence", str(evidence_path),
        "--n2-source", str(source_path),
        "--expected-evidence-sha256", ARTIFACT_SHA,
        "--expected-source-sha256", SOURCE_SHA,
        "--expected-run-sha", RUN_SHA,
        "--out", str(summary_path),
        "--review-packet-out", str(packet_path),
    ])
    assert main() == 0
    assert packet_path.stat().st_mode & 0o777 == 0o600
    assert json.loads(packet_path.read_text())["candidate_count"] == 142
    original = packet_path.read_bytes()
    assert main() == 2
    assert packet_path.read_bytes() == original
