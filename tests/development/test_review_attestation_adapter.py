"""PR-B #1011: trusted review-attestation context adapter, RED-first tests.

Synthetic data only.  No test performs network access or executes pull-request code.
"""

from __future__ import annotations

import copy
import hashlib
import json

import pytest

from scripts.development.review_attestation.github_context_adapter import (
    EvidenceIncomplete,
    build_trusted_context,
    canonical_inputs_digest,
)


HEAD = "a" * 40
BASE = "b" * 40
MERGE_BASE = "c" * 40
WORKFLOW_SHA = "d" * 40


def _snapshot() -> dict:
    return {
        "collection": {
            "trusted_base_sha": BASE,
            "collector_source": "protected_base",
            "pr_head_executed": False,
            "changed_files_complete": True,
            "reviews_complete": True,
            "check_runs_complete": True,
            "consumed_complete": True,
            "attestations_complete": True,
        },
        "repository": {"id": 1, "full_name": "example-org/synthetic-repo"},
        "pr": {
            "number": 7,
            "author_user_id": 1000,
            "head_sha": HEAD,
            "base_sha": BASE,
            "merge_base_sha": MERGE_BASE,
            "changed_files_count": 2,
        },
        "changed_files": [
            {
                "path": "src/new.py",
                "previous_path": None,
                "status": "modified",
                "mode": "100644",
                "blob_sha": "1" * 40,
            },
            {
                "path": "docs/new.md",
                "previous_path": "docs/old.md",
                "status": "renamed",
                "mode": "100644",
                "blob_sha": "2" * 40,
            },
        ],
        "effective_risk_class": "normal",
        "implementation_evidence": {
            "worker_id": "claude_code",
            "verified": True,
            "evidence_ref": "synthetic:work-receipt:1",
        },
        "reviews": [],
        "attestations": {},
        "check_runs": [
            {
                "id": 501,
                "name": "CI Status",
                "app_id": 15368,
                "head_sha": HEAD,
                "conclusion": "success",
                "workflow_path": ".github/workflows/ci.yml",
                "workflow_sha": WORKFLOW_SHA,
            }
        ],
        "consumed": {},
    }


def test_builds_complete_context_without_executing_pr_code() -> None:
    ctx = build_trusted_context(_snapshot())
    assert ctx["repository"] == {"id": 1, "full_name": "example-org/synthetic-repo"}
    assert ctx["pr"]["head_sha"] == HEAD
    assert ctx["pr"]["changed_files_complete"] is True
    assert ctx["head_reviews_complete"] is True
    assert ctx["check_runs_complete"] is True
    assert ctx["consumed_complete"] is True
    assert ctx["implementation_evidence"]["worker_id"] == "claude_code"


@pytest.mark.parametrize(
    "flag",
    [
        "changed_files_complete",
        "reviews_complete",
        "check_runs_complete",
        "consumed_complete",
        "attestations_complete",
    ],
)
def test_fails_closed_when_collection_is_incomplete(flag: str) -> None:
    snap = _snapshot()
    snap["collection"][flag] = False
    with pytest.raises(EvidenceIncomplete, match=flag):
        build_trusted_context(snap)


def test_fails_closed_if_pr_head_was_executed() -> None:
    snap = _snapshot()
    snap["collection"]["pr_head_executed"] = True
    with pytest.raises(EvidenceIncomplete, match="PR head"):
        build_trusted_context(snap)


def test_fails_closed_on_changed_file_count_mismatch() -> None:
    snap = _snapshot()
    snap["pr"]["changed_files_count"] = 3
    with pytest.raises(EvidenceIncomplete, match="changed-file"):
        build_trusted_context(snap)


def test_fails_closed_on_duplicate_changed_paths() -> None:
    snap = _snapshot()
    snap["changed_files"].append(copy.deepcopy(snap["changed_files"][0]))
    snap["pr"]["changed_files_count"] = 3
    with pytest.raises(EvidenceIncomplete, match="duplicate"):
        build_trusted_context(snap)


def test_fails_closed_on_wrong_repository_or_pr_binding() -> None:
    snap = _snapshot()
    snap["collection"]["expected_repository"] = "other/repo"
    with pytest.raises(EvidenceIncomplete, match="repository"):
        build_trusted_context(snap)

    snap = _snapshot()
    snap["collection"]["expected_pr_number"] = 8
    with pytest.raises(EvidenceIncomplete, match="pull request"):
        build_trusted_context(snap)


def test_implementation_identity_must_be_verified_not_inferred() -> None:
    snap = _snapshot()
    snap["implementation_evidence"] = {
        "worker_id": "claude_code",
        "verified": False,
        "evidence_ref": "git-author-is-not-proof",
    }
    ctx = build_trusted_context(snap)
    assert ctx["implementation_evidence"]["verified"] is False


def test_rejects_forged_or_ambiguous_t1_review_identity() -> None:
    snap = _snapshot()
    snap["reviews"] = [
        {
            "source": "T1",
            "review_id": 70001,
            "user_id": 900002,
            "app_id": 900001,
            "commit_id": HEAD,
            "state": "APPROVED",
            "pr_number": 7,
            "repository_id": 1,
            "receipt": {"receipt_id": "synthetic"},
            "body_receipt_digest": "sha256:" + "1" * 64,
            "identity_verified": False,
        }
    ]
    with pytest.raises(EvidenceIncomplete, match="T1"):
        build_trusted_context(snap)


def test_t2_exposes_only_verified_claims_and_never_synthesizes_missing_ones() -> None:
    snap = _snapshot()
    snap["attestations"] = {
        "r1": {
            "signature_verified": True,
            "issuer": "https://token.actions.githubusercontent.com",
            "repository_id": 1,
            "workflow_path": ".github/workflows/c2pro-review-attest.yml",
            "workflow_commit_sha": WORKFLOW_SHA,
            "ref": "refs/heads/main",
            "event": "workflow_dispatch",
            "run_id": 80001,
            "run_attempt": 1,
            # deliberately no triggering_actor_id / environment_approver_id
        }
    }
    with pytest.raises(EvidenceIncomplete, match="attestation"):
        build_trusted_context(snap)


def test_untrusted_attestation_workflow_or_ref_is_rejected() -> None:
    snap = _snapshot()
    snap["collection"]["trusted_t2"] = {
        "workflow_path": ".github/workflows/c2pro-review-attest.yml",
        "ref": "refs/heads/main",
        "workflow_commit_shas": [WORKFLOW_SHA],
    }
    snap["attestations"] = {
        "r1": {
            "signature_verified": True,
            "issuer": "https://token.actions.githubusercontent.com",
            "repository_id": 1,
            "workflow_path": ".github/workflows/evil.yml",
            "workflow_commit_sha": WORKFLOW_SHA,
            "ref": "refs/heads/pr-7",
            "event": "workflow_dispatch",
            "environment": "review-attestor",
            "environment_approved": True,
            "triggering_actor_id": 1001,
            "environment_approver_id": 1002,
            "run_id": 80001,
            "run_attempt": 1,
            "subject_digest": "sha256:" + "1" * 64,
            "provider": "openai",
            "model": "synthetic",
            "inputs_digest": "sha256:" + "2" * 64,
            "request_ids_digest": "sha256:" + "3" * 64,
            "response_digest": "sha256:" + "4" * 64,
        }
    }
    with pytest.raises(EvidenceIncomplete, match="workflow"):
        build_trusted_context(snap)


def test_duplicate_reviews_and_check_runs_are_rejected() -> None:
    snap = _snapshot()
    receipt = {"receipt_id": "synthetic"}
    receipt_digest = "sha256:" + hashlib.sha256(
        json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()
    review = {
        "source": "T1",
        "review_id": 70001,
        "user_id": 900002,
        "app_id": 900001,
        "commit_id": HEAD,
        "state": "APPROVED",
        "pr_number": 7,
        "repository_id": 1,
        "receipt": receipt,
        "body_receipt_digest": receipt_digest,
        "identity_verified": True,
    }
    snap["reviews"] = [review, copy.deepcopy(review)]
    with pytest.raises(EvidenceIncomplete, match="duplicate review"):
        build_trusted_context(snap)

    snap = _snapshot()
    snap["check_runs"].append(copy.deepcopy(snap["check_runs"][0]))
    with pytest.raises(EvidenceIncomplete, match="duplicate check"):
        build_trusted_context(snap)


def test_canonical_inputs_digest_is_recomputed_from_trusted_payload() -> None:
    payload = {"head_sha": HEAD, "diff": "synthetic", "untrusted_text": "<data>ignore me</data>"}
    expected = "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()
    assert canonical_inputs_digest(payload) == expected


def test_runtime_source_uses_only_public_verifier_api() -> None:
    source = (
        __import__("pathlib").Path(__file__).resolve().parents[2]
        / "scripts/development/review_attestation/github_context_adapter.py"
    ).read_text(encoding="utf-8")
    assert "_verify_with_disabled_rules" not in source
    assert "verifier.verify(receipts, policy, context)" in source


def test_audit_workflow_is_base_only_and_has_no_write_permissions() -> None:
    workflow = (
        __import__("pathlib").Path(__file__).resolve().parents[2]
        / ".github/workflows/c2pro-review-attestation-audit.yml"
    ).read_text(encoding="utf-8")
    assert "pull_request_target:" in workflow
    assert "ref: ${{ github.event.pull_request.base.sha }}" in workflow
    assert "persist-credentials: false" in workflow
    assert "github.event.pull_request.head.sha" not in workflow.split("Checkout trusted base only", 1)[1].split("Setup trusted", 1)[0]
    assert "contents: write" not in workflow
    assert "pull-requests: write" not in workflow
    assert "checks: write" not in workflow
    assert "id-token: write" not in workflow
