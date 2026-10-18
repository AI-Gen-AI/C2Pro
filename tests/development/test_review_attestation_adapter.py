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
    verify_t2_receipt_artifact,
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
        "review_inventory": [],
        "attestations": {},
        "check_run_inventory": [
            {
                "id": 501,
                "name": "CI Status",
                "app_id": 15368,
                "head_sha": HEAD,
                "conclusion": "success",
            }
        ],
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
    assert ctx["implementation_evidence"] is None  # #1011: a snapshot claim is never a provenance source


@pytest.mark.parametrize(
    "flag",
    [
        "changed_files_complete",
        "reviews_complete",
        "check_runs_complete",
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
    assert ctx["implementation_evidence"] is None  # #1011: never passed through, verified or not


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


def _signed_receipt() -> dict:
    return {
        "receipt_id": "00000001-0000-4000-8000-000000000001",
        "review": {
            "provider_execution": {
                "provider": "openai",
                "model": "synthetic-model",
                "request_ids": ["req-1"],
                "response_digest": "sha256:" + "5" * 64,
                "inputs_digest": "sha256:" + "6" * 64,
            }
        },
    }


def _run_facts() -> dict:
    return {
        "repository_id": 1,
        "run_id": 80001,
        "run_attempt": 1,
        "workflow_path": ".github/workflows/c2pro-review-attest.yml",
        "head_sha": WORKFLOW_SHA,
        "ref": "refs/heads/main",
        "event": "workflow_dispatch",
        "environment": "review-attestor",
        "environment_approved": True,
        "triggering_actor_id": 1001,
        "environment_approver_id": 1002,
    }


def test_t2_artifact_verifier_binds_certificate_run_and_canonical_receipt(tmp_path) -> None:
    receipt = _signed_receipt()
    artifact = tmp_path / "receipt.json"
    artifact.write_bytes(
        json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    )
    bundle = tmp_path / "bundle.jsonl"
    bundle.write_text("synthetic-bundle", encoding="utf-8")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    output = [{
        "verificationResult": {
            "signature": {
                "certificate": {
                    "issuer": "https://token.actions.githubusercontent.com",
                    "githubWorkflowRepository": "example-org/synthetic-repo",
                    "githubWorkflowRef": "refs/heads/main",
                    "sourceRepositoryDigest": WORKFLOW_SHA,
                    "runnerEnvironment": "github-hosted",
                    "runInvocationURI": (
                        "https://github.com/example-org/synthetic-repo/"
                        "actions/runs/80001/attempts/1"
                    ),
                }
            },
            "statement": {"subject": [{"digest": {"sha256": digest}}]},
        }
    }]
    seen = {}

    def fake_runner(command, **kwargs):
        import subprocess
        seen["command"] = command
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(output), stderr="")

    verified_receipt, claims = verify_t2_receipt_artifact(
        artifact_path=artifact,
        bundle_path=bundle,
        repository="example-org/synthetic-repo",
        signer_workflow=".github/workflows/c2pro-review-attest.yml",
        source_ref="refs/heads/main",
        signer_digest=WORKFLOW_SHA,
        run_facts=_run_facts(),
        runner=fake_runner,
    )
    assert verified_receipt == receipt
    assert claims["signature_verified"] is True
    assert claims["run_id"] == 80001
    assert claims["run_attempt"] == 1
    assert claims["subject_digest"] == "sha256:" + digest
    assert "--deny-self-hosted-runners" in seen["command"]
    assert "--signer-workflow" in seen["command"]
    assert "--source-digest" in seen["command"]
    assert "--signer-digest" in seen["command"]


def test_t2_artifact_verifier_fails_when_api_run_approval_fact_is_missing(tmp_path) -> None:
    receipt = _signed_receipt()
    artifact = tmp_path / "receipt.json"
    artifact.write_bytes(
        json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    )
    bundle = tmp_path / "bundle.jsonl"
    bundle.write_text("synthetic-bundle", encoding="utf-8")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    output = [{
        "verificationResult": {
            "signature": {
                "certificate": {
                    "issuer": "https://token.actions.githubusercontent.com",
                    "githubWorkflowRepository": "example-org/synthetic-repo",
                    "githubWorkflowRef": "refs/heads/main",
                    "sourceRepositoryDigest": WORKFLOW_SHA,
                    "runnerEnvironment": "github-hosted",
                    "runInvocationURI": (
                        "https://github.com/example-org/synthetic-repo/"
                        "actions/runs/80001/attempts/1"
                    ),
                }
            },
            "statement": {"subject": [{"digest": {"sha256": digest}}]},
        }
    }]

    def fake_runner(command, **kwargs):
        import subprocess
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(output), stderr="")

    facts = _run_facts()
    facts.pop("environment_approver_id")
    with pytest.raises(EvidenceIncomplete, match="environment_approver_id"):
        verify_t2_receipt_artifact(
            artifact_path=artifact,
            bundle_path=bundle,
            repository="example-org/synthetic-repo",
            signer_workflow=".github/workflows/c2pro-review-attest.yml",
            source_ref="refs/heads/main",
            signer_digest=WORKFLOW_SHA,
            run_facts=facts,
            runner=fake_runner,
        )


def test_t2_artifact_verifier_rejects_certificate_from_other_workflow_context(tmp_path) -> None:
    receipt = _signed_receipt()
    artifact = tmp_path / "receipt.json"
    artifact.write_bytes(
        json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    )
    bundle = tmp_path / "bundle.jsonl"
    bundle.write_text("synthetic-bundle", encoding="utf-8")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    output = [{
        "verificationResult": {
            "signature": {
                "certificate": {
                    "issuer": "https://token.actions.githubusercontent.com",
                    "githubWorkflowRepository": "attacker/repo",
                    "githubWorkflowRef": "refs/heads/main",
                    "sourceRepositoryDigest": WORKFLOW_SHA,
                    "runnerEnvironment": "github-hosted",
                    "runInvocationURI": (
                        "https://github.com/example-org/synthetic-repo/"
                        "actions/runs/80001/attempts/1"
                    ),
                }
            },
            "statement": {"subject": [{"digest": {"sha256": digest}}]},
        }
    }]

    def fake_runner(command, **kwargs):
        import subprocess
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(output), stderr="")

    with pytest.raises(EvidenceIncomplete, match="certificate repository"):
        verify_t2_receipt_artifact(
            artifact_path=artifact,
            bundle_path=bundle,
            repository="example-org/synthetic-repo",
            signer_workflow=".github/workflows/c2pro-review-attest.yml",
            source_ref="refs/heads/main",
            signer_digest=WORKFLOW_SHA,
            run_facts=_run_facts(),
            runner=fake_runner,
        )


def test_complete_review_inventory_is_reconciled_with_authoritative_t1_subset() -> None:
    snap = _snapshot()
    snap["review_inventory"] = [
        {
            "review_id": 71000,
            "user_id": 2000,
            "app_id": None,
            "commit_id": HEAD,
            "state": "COMMENTED",
        }
    ]
    ctx = build_trusted_context(snap)
    assert ctx["review_inventory"][0]["review_id"] == 71000

    snap["review_inventory"].append(copy.deepcopy(snap["review_inventory"][0]))
    with pytest.raises(EvidenceIncomplete, match="duplicate review inventory"):
        build_trusted_context(snap)


def test_complete_check_run_inventory_is_preserved_and_trusted_subset_must_be_present() -> None:
    snap = _snapshot()
    snap["check_run_inventory"] = [
        {
            "id": 501,
            "name": "CI Status",
            "app_id": 15368,
            "head_sha": HEAD,
            "conclusion": "success",
        },
        {
            "id": 999,
            "name": "External Advisory",
            "app_id": 424242,
            "head_sha": HEAD,
            "conclusion": "success",
        },
    ]
    ctx = build_trusted_context(snap)
    assert {row["id"] for row in ctx["check_run_inventory"]} == {501, 999}

    snap = _snapshot()
    snap["check_run_inventory"] = []
    with pytest.raises(EvidenceIncomplete, match="trusted check run"):
        build_trusted_context(snap)


def test_inventory_entries_must_all_be_bound_to_exact_head() -> None:
    snap = _snapshot()
    snap["review_inventory"] = [
        {"review_id": 71000, "user_id": 2000, "app_id": None, "commit_id": "9" * 40, "state": "COMMENTED"}
    ]
    with pytest.raises(EvidenceIncomplete, match="review inventory"):
        build_trusted_context(snap)

    snap = _snapshot()
    snap["check_run_inventory"] = [
        {"id": 501, "name": "CI Status", "app_id": 15368, "head_sha": "9" * 40, "conclusion": "success"}
    ]
    with pytest.raises(EvidenceIncomplete, match="check-run inventory"):
        build_trusted_context(snap)


def test_markerless_app_review_is_preserved_for_contradiction_handling() -> None:
    snap = _snapshot()
    snap["review_inventory"] = [{
        "review_id": 99001,
        "user_id": 900002,
        "app_id": 900001,
        "commit_id": HEAD,
        "state": "CHANGES_REQUESTED",
    }]
    snap["check_run_inventory"] = [{
        "id": 501,
        "name": "CI Status",
        "app_id": 15368,
        "head_sha": HEAD,
        "conclusion": "success",
    }]
    ctx = build_trusted_context(snap)
    markerless = [r for r in ctx["head_reviews"] if r.get("review_id") == 99001]
    assert markerless == [{
        "source": "T1",
        "review_id": 99001,
        "user_id": 900002,
        "app_id": 900001,
        "state": "CHANGES_REQUESTED",
        "receipt": None,
        "body_receipt_digest": None,
    }]


def test_audit_snapshot_may_truthfully_report_consumption_incomplete() -> None:
    snap = _snapshot()
    snap["collection"]["consumed_complete"] = False
    ctx = build_trusted_context(snap)
    assert ctx["consumed_complete"] is False


def test_t2_bundle_verification_does_not_promote_receipt_execution_fields(tmp_path) -> None:
    receipt = _signed_receipt()
    artifact = tmp_path / "receipt.json"
    artifact.write_bytes(
        json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    )
    bundle = tmp_path / "bundle.jsonl"
    bundle.write_text("synthetic-bundle", encoding="utf-8")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    output = [{
        "verificationResult": {
            "signature": {"certificate": {
                "issuer": "https://token.actions.githubusercontent.com",
                "githubWorkflowRepository": "example-org/synthetic-repo",
                "githubWorkflowRef": "refs/heads/main",
                "sourceRepositoryDigest": WORKFLOW_SHA,
                "runnerEnvironment": "github-hosted",
                "runInvocationURI": (
                    "https://github.com/example-org/synthetic-repo/"
                    "actions/runs/80001/attempts/1"
                ),
            }},
            "statement": {"subject": [{"digest": {"sha256": digest}}]},
        }
    }]

    def fake_runner(command, **kwargs):
        import subprocess
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(output), stderr="")

    _, claims = verify_t2_receipt_artifact(
        artifact_path=artifact,
        bundle_path=bundle,
        repository="example-org/synthetic-repo",
        signer_workflow=".github/workflows/c2pro-review-attest.yml",
        source_ref="refs/heads/main",
        signer_digest=WORKFLOW_SHA,
        run_facts=_run_facts(),
        runner=fake_runner,
    )
    for key in ("provider", "model", "request_ids_digest", "inputs_digest", "response_digest"):
        assert key not in claims


def test_audit_workflow_refetches_pr_and_binds_actual_check_producer() -> None:
    workflow = (
        __import__("pathlib").Path(__file__).resolve().parents[2]
        / ".github/workflows/c2pro-review-attestation-audit.yml"
    ).read_text(encoding="utf-8")
    assert workflow.count("github.rest.pulls.get") >= 2
    assert "ref: run.data.head_sha" in workflow
    assert "run.data.head_sha !== pr.head.sha" in workflow
    assert "run.data.check_suite_id !== c.check_suite.id" in workflow
    assert "consumed_complete: false" in workflow


# ============================================================================ #1011 follow-up (RED first)
# implementation_evidence provenance, explicit non-authorization, and adapter/verifier revalidation.
import pathlib  # noqa: E402

import yaml  # noqa: E402

from scripts.development.review_attestation.github_context_adapter import main as adapter_main  # noqa: E402
from scripts.development.review_attestation.github_context_adapter import run_audit  # noqa: E402

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_WORKFLOW = _ROOT / ".github/workflows/c2pro-review-attestation-audit.yml"


def _trusted_evidence() -> dict:
    return {"work_id": "C2PRO-DEV-14", "worker_id": "claude_code", "verified": True,
            "evidence_ref": "synthetic:trusted-work-receipt:1"}


def _audit_policy(check_sha: str = WORKFLOW_SHA) -> dict:
    policy = yaml.safe_load((_ROOT / "scripts/development/review_attestation/audit-policy.yaml").read_text())
    policy["required_checks"][0]["workflow_shas"] = [check_sha]
    return policy


def _trivial_snapshot() -> dict:
    snap = _snapshot()
    snap["effective_risk_class"] = "trivial"
    return snap


@pytest.mark.parametrize("claim", [
    _trusted_evidence(),
    {"worker_id": "claude_code", "verified": True, "evidence_ref": "synthetic:work-receipt:1"},
    {"work_id": "C2PRO-DEV-14", "worker_id": "codex", "verified": True, "evidence_ref": "git-author:codex"},
])
def test_1011_snapshot_supplied_implementation_evidence_is_never_trusted(claim: dict) -> None:
    """The snapshot is collected data, not a provenance source: a self-declared verified claim is dropped."""
    snap = _snapshot()
    snap["implementation_evidence"] = claim
    ctx = build_trusted_context(snap)
    assert ctx["implementation_evidence"] is None


def test_1011_worker_identity_is_never_inferred_from_author_branch_or_comments() -> None:
    snap = _snapshot()
    snap["implementation_evidence"] = None
    snap["pr"]["head_ref"] = "claude/1011-adapter-provenance"
    snap["pr"]["author_login"] = "codex-bot"
    snap["comments"] = [{"body": "implemented by claude_code for C2PRO-DEV-14"}]
    assert build_trusted_context(snap)["implementation_evidence"] is None


def test_1011_without_a_trusted_provenance_source_the_audit_reports_implementer_unverified() -> None:
    report = run_audit(_trivial_snapshot(), [], _audit_policy())
    assert report["gate_satisfied"] is False
    assert "IMPLEMENTER_UNVERIFIED" in {v["code"] for v in report["violations"]}
    assert report["implementation_evidence_source"] == "none"


def test_1011_only_an_injected_trusted_verifier_can_supply_implementation_evidence() -> None:
    seen = []

    def trusted_verifier(subject: dict) -> dict:
        seen.append(subject)
        return _trusted_evidence()

    ctx = build_trusted_context(_trivial_snapshot(), implementation_verifier=trusted_verifier)
    assert ctx["implementation_evidence"] == _trusted_evidence()
    assert seen == [{"repository_id": 1, "pr_number": 7, "head_sha": HEAD, "base_sha": BASE}]


@pytest.mark.parametrize("returned", [
    None, "claude_code", {}, dict(_trusted_evidence(), verified=False), dict(_trusted_evidence(), verified="true"),
    dict(_trusted_evidence(), work_id="C2PRO-DEV-9"), dict(_trusted_evidence(), work_id=14),
    dict(_trusted_evidence(), worker_id="Claude Code"), dict(_trusted_evidence(), worker_id=123),
    dict(_trusted_evidence(), evidence_ref=""), {k: v for k, v in _trusted_evidence().items() if k != "work_id"},
])
def test_1011_malformed_trusted_verifier_output_fails_closed(returned) -> None:
    with pytest.raises(EvidenceIncomplete):
        build_trusted_context(_trivial_snapshot(), implementation_verifier=lambda subject: returned)


def test_1011_trusted_verifier_errors_fail_closed() -> None:
    def broken(subject: dict) -> dict:
        raise RuntimeError("provenance store unavailable")

    with pytest.raises(EvidenceIncomplete):
        build_trusted_context(_trivial_snapshot(), implementation_verifier=broken)


@pytest.mark.parametrize("satisfied", [True, False])
def test_1011_audit_report_always_states_it_does_not_authorize_merge(satisfied: bool) -> None:
    snap = _trivial_snapshot()
    verifier = (lambda subject: _trusted_evidence()) if satisfied else None
    report = run_audit(snap, [], _audit_policy(), implementation_verifier=verifier)
    assert report["gate_satisfied"] is satisfied
    assert report["authorizes_merge"] is False
    assert report["mode"] == "AUDIT_ONLY"


def test_1011_adapter_refuses_a_verifier_that_claims_authorization(monkeypatch) -> None:
    import scripts.development.review_attestation.github_context_adapter as adapter

    real_loader = adapter._load_verifier

    def loader(repo_root):
        module = real_loader(repo_root)

        class Authorizing:
            def __getattr__(self, name):
                return getattr(module, name)

            @staticmethod
            def verify(receipts, policy, context):
                result = module.verify(receipts, policy, context)

                class Claim:
                    def __getattr__(self, name):
                        return True if name == "authorizes_merge" else getattr(result, name)
                return Claim()
        return Authorizing()

    monkeypatch.setattr(adapter, "_load_verifier", loader)
    with pytest.raises(EvidenceIncomplete):
        adapter.run_audit(_trivial_snapshot(), [], _audit_policy(), implementation_verifier=lambda s: _trusted_evidence())


def test_1011_cli_report_carries_non_authorization(tmp_path) -> None:
    files = {}
    for name, value in (("snapshot", _trivial_snapshot()), ("receipts", []), ("policy", _audit_policy())):
        files[name] = tmp_path / f"{name}.json"
        files[name].write_text(json.dumps(value), encoding="utf-8")
    out = tmp_path / "audit.json"
    code = adapter_main(["--snapshot", str(files["snapshot"]), "--receipts", str(files["receipts"]),
                         "--policy", str(files["policy"]), "--output", str(out)])
    report = json.loads(out.read_text(encoding="utf-8"))
    assert code == 0  # the audit ran; exit status never encodes approval
    assert report["authorizes_merge"] is False and report["gate_satisfied"] is False


@pytest.mark.parametrize("row", [
    {"user_id": None}, {"state": None}, {"state": ""},
])
def test_1011_app_review_inventory_rows_need_complete_identity(row: dict) -> None:
    snap = _snapshot()
    entry = {"review_id": 99001, "user_id": 900002, "app_id": 900001, "commit_id": HEAD,
             "state": "CHANGES_REQUESTED"}
    entry.update(row)
    snap["review_inventory"] = [entry]
    with pytest.raises(EvidenceIncomplete):
        build_trusted_context(snap)


def test_1011_workflow_cannot_turn_an_audit_into_approval() -> None:
    workflow = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    perms = workflow["permissions"]
    assert all(level == "read" for level in perms.values()), perms
    source = _WORKFLOW.read_text(encoding="utf-8")
    for forbidden in ("gh pr review", "gh pr merge", "createReview", "pulls.merge", "addLabels",
                      "enable-auto-merge", "--approve", "issues.createComment", "checks.create"):
        assert forbidden not in source, forbidden
    assert 'report["authorizes_merge"] is False' in source
    assert "AUTHORIZES_MERGE=false" in source
    assert "C2PRO_REVIEW_ATTESTATION_AUDIT=SATISFIED" not in source


# ============================================================================ #1023 protected-base implementation provenance
def test_1023_base_work_provenance_composes_with_audit_without_authorization(tmp_path) -> None:
    from scripts.development.review_attestation.base_work_implementation_verifier import (
        build_base_work_implementation_verifier,
    )

    snap = _trivial_snapshot()
    snap["pr"]["head_ref"] = "feat/dev14-proof"
    base = snap["pr"]["base_sha"]
    current = {
        "baseline": {"main_sha": base},
        "active_work": ["C2PRO-DEV-14"],
    }
    queue = {
        "items": [{
            "work_id": "C2PRO-DEV-14",
            "status": "awaiting_review",
            "work_ref": ".c2pro/work/C2PRO-DEV-14.yaml",
        }]
    }
    work = {
        "schema": "c2pro-work-envelope-v1",
        "work_id": "C2PRO-DEV-14",
        "base_sha": base,
        "branch": snap["pr"]["head_ref"],
        "worker_selection": {
            "preferred": "claude_code",
            "eligible_principals": ["claude_code", "codex"],
            "eligible_subordinates": [],
            "selected": "claude_code",
        },
        "workspace_receipt": "workspace:synthetic:1023",
    }
    for relative, value in (
        (".c2pro/control/current.yaml", current),
        (".c2pro/control/work-queue.yaml", queue),
        (".c2pro/work/C2PRO-DEV-14.yaml", work),
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")

    report = run_audit(
        snap,
        [],
        _audit_policy(),
        implementation_verifier=build_base_work_implementation_verifier(tmp_path),
    )
    assert report["gate_satisfied"] is True
    assert report["implementation_evidence_source"] == "trusted_verifier"
    assert report["authorizes_merge"] is False
    assert report["mode"] == "AUDIT_ONLY"


def test_1023_workflow_collects_trusted_head_ref_and_adapter_autowires_base_resolver() -> None:
    workflow = _WORKFLOW.read_text(encoding="utf-8")
    adapter = (_ROOT / "scripts/development/review_attestation/github_context_adapter.py").read_text(encoding="utf-8")
    assert "head_ref: pr.head.ref" in workflow
    assert "build_base_work_implementation_verifier" in adapter
    assert "authorizes_merge" in adapter
