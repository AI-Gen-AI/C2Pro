"""Synthetic builders for review-receipt tests (#1009). Every identity, SHA and id here is FAKE.

Repository ``example-org/synthetic-repo`` (id 1), App ids 9000xx and SHAs built from repeated hex
digits never exist on GitHub, so no fixture can ever validate a real pull request.
"""

from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location("verify_review_receipts",
                                               ROOT / "scripts/development/verify_review_receipts.py")
assert _SPEC and _SPEC.loader
vr = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = vr  # dataclasses resolve their module through sys.modules
_SPEC.loader.exec_module(vr)

HEAD, BASE, MERGE_BASE = "a" * 40, "b" * 40, "c" * 40
WORKFLOW_SHA, PROMPT_SHA = "d" * 40, "e" * 64
AUTHOR_ID, DISPATCHER_ID, APPROVER_ID = 1000, 1001, 1002
CI_WORKFLOW, CI_WORKFLOW_SHA = ".github/workflows/ci.yml", "c1" * 20
CODEX_APP, CODEX_BOT = 900001, 900002
CHECK_APP = 15368  # GitHub Actions App id (public, constant); synthetic check ids below
WORK_ID = "C2PRO-DEV-14"  # authoritative work identity, reported by the trusted adapter from the work envelope

CHANGED = [
    {"path": "scripts/example.py", "previous_path": None, "status": "modified", "mode": "100644", "blob_sha": "1" * 40},
    {"path": "docs/new_name.md", "previous_path": "docs/old_name.md", "status": "renamed", "mode": "100644", "blob_sha": "2" * 40},
    {"path": "tools/link", "previous_path": None, "status": "added", "mode": "120000", "blob_sha": "3" * 40},
    {"path": "obsolete.txt", "previous_path": None, "status": "removed", "mode": None, "blob_sha": None},
]


def policy() -> dict[str, Any]:
    """Synthetic verifier policy. NOT the canonical review policy or routing authority."""
    return {
        "t1_apps": [{"app_id": CODEX_APP, "user_id": CODEX_BOT}],
        "t1_apps_worker": {str(CODEX_APP): "codex"},
        "t2": {
            "issuer": "https://token.actions.githubusercontent.com",
            "workflow_path": ".github/workflows/c2pro-review-attest.yml",
            "workflow_commit_shas": [WORKFLOW_SHA],
            "ref": "refs/heads/main",
            "environment": "review-attestor",
            "dispatcher_user_ids": [DISPATCHER_ID],
            "approver_user_ids": [APPROVER_ID],
            "prompt_template_shas": [PROMPT_SHA],
        },
        "role_eligibility": {
            "principal": ["claude_code", "codex"],
            "challenger": ["claude_code", "codex", "antigravity"],
            "orchestrator_synthesis": ["gpt6_orchestrator"],
        },
        "worker_providers": {"claude_code": "anthropic", "codex": "openai", "antigravity": "google",
                             "gpt6_orchestrator": "openai"},
        "gates": {
            "trivial": [], "normal": ["principal"], "material": ["principal"],
            "architecture": ["principal", "challenger", "orchestrator_synthesis"],
            "security": ["principal", "challenger", "orchestrator_synthesis"],
            "high_blast_radius": ["principal", "challenger", "orchestrator_synthesis"],
        },
        "high_blast_radius_paths": [
            "scripts/development/verify_review_receipts.py", "scripts/development/review_attestation/",
            ".c2pro/control/", ".github/workflows/",
        ],
        "required_checks": [{"name": "CI Status", "app_id": CHECK_APP, "workflow_path": CI_WORKFLOW,
                             "workflow_shas": [CI_WORKFLOW_SHA]}],
    }


def context(risk: str = "normal", implementer: str | None = "claude_code") -> dict[str, Any]:
    return {
        "repository": {"id": 1, "full_name": "example-org/synthetic-repo"},
        "pr": {"number": 7, "author_user_id": AUTHOR_ID, "head_sha": HEAD, "base_sha": BASE,
               "merge_base_sha": MERGE_BASE, "changed_files": copy.deepcopy(CHANGED), "changed_files_complete": True},
        "effective_risk_class": risk,
        "implementation_evidence": ({"work_id": WORK_ID, "worker_id": implementer, "verified": True,
                                     "evidence_ref": "work-receipt-synthetic"} if implementer else None),
        "app_reviews": {},
        "head_reviews": [],
        "head_reviews_complete": True,
        "attestations": {},
        "check_runs": [{"id": 501, "name": "CI Status", "app_id": CHECK_APP, "head_sha": HEAD, "conclusion": "success",
                        "workflow_path": CI_WORKFLOW, "workflow_sha": CI_WORKFLOW_SHA}],
        "check_runs_complete": True,
        "consumed": {},
        "consumed_complete": True,
    }


def _uuid(n: int) -> str:
    return f"{n:08x}-0000-4000-8000-{n:012x}"


def receipt(n: int, role: str, worker: str, *, tier: str = "T2", risk: str = "normal",
            implementer: str = "claude_code", synthesis_of: list[str] | None = None) -> dict[str, Any]:
    identity: dict[str, Any]
    if tier == "T1":
        identity = {"github_app_id": CODEX_APP, "github_user_id": CODEX_BOT, "review_id": 70000 + n}
    else:
        identity = {"workflow_path": ".github/workflows/c2pro-review-attest.yml", "workflow_commit_sha": WORKFLOW_SHA,
                    "run_id": 80000 + n, "run_attempt": 1}
    r: dict[str, Any] = {
        "schema": "c2pro-review-receipt-v1", "schema_version": 1, "receipt_id": _uuid(n), "work_id": WORK_ID,
        "risk_class": risk,
        "subject": {"repository_id": 1, "repository": "example-org/synthetic-repo", "pr_number": 7, "head_sha": HEAD,
                    "base_sha": BASE, "merge_base_sha": MERGE_BASE, "diff_digest": vr.diff_digest(CHANGED),
                    "changed_files": copy.deepcopy(CHANGED)},
        "review": {"role": role, "worker_id": worker, "implementation_worker_id": implementer, "evidence_tier": tier,
                   "identity": identity},
        "result": {"verdict": "PASS", "findings": [{"id": "F1", "severity": "P3", "file": None, "line": None,
                                                    "summary": "synthetic non-blocking note"}],
                   "tests_observed": [{"name": "CI Status", "check_run_id": 501, "conclusion": "success"}],
                   "architecture_drift": False, "security_concern": False, "scope_deviation": False,
                   "recommended_action": "approve"},
        "issued_at": "2026-01-01T00:00:00Z",
    }
    if tier == "T2":
        r["review"]["provider_execution"] = {
            "provider": {"codex": "openai", "antigravity": "google", "claude_code": "anthropic",
                         "gpt6_orchestrator": "openai"}.get(worker, "unknown"),
            "model": "synthetic-model", "request_ids": [f"req-synthetic-{n}"],
            "response_digest": "sha256:" + f"{n:064x}", "prompt_template_sha256": PROMPT_SHA,
            "inputs_digest": "sha256:" + "f" * 64, "untrusted_text_wrapped": True}
    if synthesis_of is not None:
        r["result"]["synthesis_of"] = synthesis_of
    return r


def attest(ctx: dict[str, Any], r: dict[str, Any]) -> None:
    """Record what a trusted attestation adapter would report for ``r`` (synthetic)."""
    if r["review"]["evidence_tier"] == "T1":
        ident = r["review"]["identity"]
        ctx["app_reviews"][str(ident["review_id"])] = {
            "user_id": ident["github_user_id"], "app_id": ident["github_app_id"], "commit_id": ctx["pr"]["head_sha"],
            "state": "APPROVED", "body_receipt_digest": vr.receipt_digest(r), "pr_number": ctx["pr"]["number"],
            "repository_id": ctx["repository"]["id"]}
        ctx["head_reviews"].append({"source": "T1", "review_id": ident["review_id"], "user_id": ident["github_user_id"],
                                    "app_id": ident["github_app_id"], "state": "APPROVED", "receipt": copy.deepcopy(r),
                                    "body_receipt_digest": vr.receipt_digest(r)})
        return
    ident = r["review"]["identity"]
    ctx["attestations"][r["receipt_id"]] = {
        "signature_verified": True, "issuer": "https://token.actions.githubusercontent.com",
        "repository_id": ctx["repository"]["id"], "workflow_path": ident["workflow_path"],
        "workflow_commit_sha": ident["workflow_commit_sha"], "ref": "refs/heads/main", "event": "workflow_dispatch",
        "environment": "review-attestor", "environment_approved": True, "triggering_actor_id": DISPATCHER_ID,
        "environment_approver_id": APPROVER_ID,
        "run_id": ident["run_id"], "run_attempt": ident["run_attempt"], "subject_digest": vr.receipt_digest(r),
        "response_digest": r["review"]["provider_execution"]["response_digest"],
        "provider": r["review"]["provider_execution"]["provider"], "model": r["review"]["provider_execution"]["model"],
        "inputs_digest": r["review"]["provider_execution"]["inputs_digest"],
        "request_ids_digest": vr.request_ids_digest(r["review"]["provider_execution"]["request_ids"])}
    ctx["head_reviews"].append({"source": "T2", "receipt_id": r["receipt_id"], "receipt": copy.deepcopy(r)})


def normal_case() -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    ctx = context("normal")
    principal = receipt(1, "principal", "codex")
    attest(ctx, principal)
    return [principal], policy(), ctx


def architecture_case() -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    ctx = context("architecture")
    principal = receipt(1, "principal", "codex", risk="architecture")
    challenger = receipt(2, "challenger", "antigravity", risk="architecture")
    synthesis = receipt(3, "orchestrator_synthesis", "gpt6_orchestrator", risk="architecture",
                        synthesis_of=[{"receipt_id": x["receipt_id"], "digest": vr.receipt_digest(x)}
                                      for x in (principal, challenger)])
    for r in (principal, challenger, synthesis):
        attest(ctx, r)
    return [principal, challenger, synthesis], policy(), ctx


def reattest(receipts: list[dict[str, Any]], ctx: dict[str, Any]) -> None:
    """Re-sign after a deliberate *legitimate* edit, so a test isolates one rule from tamper checks."""
    ctx["attestations"].clear()
    ctx["app_reviews"].clear()
    ctx["head_reviews"].clear()
    by_id = {r["receipt_id"]: r for r in receipts if isinstance(r, dict) and "receipt_id" in r}
    for r in receipts:  # keep synthesis references bound to the (re-signed) receipts they name
        for ref in (r.get("result", {}).get("synthesis_of") or []) if isinstance(r, dict) else []:
            if isinstance(ref, dict) and ref.get("receipt_id") in by_id:
                ref["digest"] = vr.receipt_digest(by_id[ref["receipt_id"]])
    for r in receipts:
        attest(ctx, r)
