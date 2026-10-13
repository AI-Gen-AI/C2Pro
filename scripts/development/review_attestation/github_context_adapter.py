#!/usr/bin/env python3
"""Trusted-context adapter for C2Pro review receipts -- AUDIT_ONLY (#1011).

A trusted base-branch workflow collects GitHub facts and attestation-verifier
claims into a snapshot. This module validates that snapshot fail-closed and
converts it to the context consumed by verify_review_receipts.verify.

It never infers implementer identity from commits, comments, branch names,
models, providers or harnesses.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

import yaml

SHA40 = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
ALLOWED_FILE_STATUS = {"added", "modified", "removed", "renamed", "copied", "changed"}
ALLOWED_MODES = {"100644", "100755", "120000", "160000", "040000"}
REQUIRED_COLLECTION_FLAGS = (
    "changed_files_complete",
    "reviews_complete",
    "check_runs_complete",
    "consumed_complete",
    "attestations_complete",
)
T2_REQUIRED_CLAIMS = {
    "signature_verified", "issuer", "repository_id", "workflow_path",
    "workflow_commit_sha", "ref", "event", "environment",
    "environment_approved", "triggering_actor_id", "environment_approver_id",
    "run_id", "run_attempt", "subject_digest", "response_digest", "provider",
    "model", "inputs_digest", "request_ids_digest",
}


class EvidenceIncomplete(ValueError):
    """Trusted collection cannot prove complete, exact-subject evidence."""


def _fail(message: str) -> None:
    raise EvidenceIncomplete(message)


def _is_int(value: Any) -> bool:
    return type(value) is int


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(f"{name} must be a mapping")
    return value


def _list(value: Any, name: str) -> list[Any]:
    if not isinstance(value, list):
        _fail(f"{name} must be a list")
    return value


def _sha(value: Any, name: str) -> str:
    if not isinstance(value, str) or not SHA40.fullmatch(value):
        _fail(f"{name} must be an exact 40-hex SHA")
    return value


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def canonical_inputs_digest(payload: Any) -> str:
    """Digest trusted model-visible input; never trust a receipt-authored digest."""
    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()


def _validate_collection(snapshot: dict[str, Any]) -> dict[str, Any]:
    collection = _mapping(snapshot.get("collection"), "collection")
    if collection.get("collector_source") != "protected_base":
        _fail("collector_source must be protected_base")
    if collection.get("pr_head_executed") is not False:
        _fail("PR head code must never be executed by the trusted collector")
    for flag in REQUIRED_COLLECTION_FLAGS:
        if collection.get(flag) is not True:
            _fail(f"{flag} is not proven true")
    _sha(collection.get("trusted_base_sha"), "trusted_base_sha")
    return collection


def _validate_subject(
    snapshot: dict[str, Any], collection: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    repository = _mapping(snapshot.get("repository"), "repository")
    pr = _mapping(snapshot.get("pr"), "pr")
    if not _is_int(repository.get("id")) or repository["id"] < 1:
        _fail("repository id must be a positive integer")
    full_name = repository.get("full_name")
    if not isinstance(full_name, str) or "/" not in full_name:
        _fail("repository full_name is invalid")
    if not _is_int(pr.get("number")) or pr["number"] < 1:
        _fail("pull request number is invalid")
    if not _is_int(pr.get("author_user_id")):
        _fail("pull request author id is invalid")
    head = _sha(pr.get("head_sha"), "pr head")
    base = _sha(pr.get("base_sha"), "pr base")
    _sha(pr.get("merge_base_sha"), "merge base")
    if collection["trusted_base_sha"] != base:
        _fail("trusted base SHA does not match pull request base")
    if collection.get("expected_repository") is not None and collection["expected_repository"] != full_name:
        _fail("repository does not match trusted event binding")
    if collection.get("expected_pr_number") is not None and collection["expected_pr_number"] != pr["number"]:
        _fail("pull request does not match trusted event binding")
    expected_head = collection.get("expected_head_sha")
    if expected_head is not None and expected_head != head:
        _fail("pull request head does not match trusted event binding")
    return repository, pr


def _validate_changed_files(snapshot: dict[str, Any], pr: dict[str, Any]) -> list[dict[str, Any]]:
    raw = _list(snapshot.get("changed_files"), "changed_files")
    expected_count = pr.get("changed_files_count")
    if not _is_int(expected_count) or expected_count < 0 or len(raw) != expected_count:
        _fail("changed-file collection does not match GitHub changed_files count")
    seen: set[str] = set()
    files: list[dict[str, Any]] = []
    for index, value in enumerate(raw):
        row = _mapping(value, f"changed_files[{index}]")
        path = row.get("path")
        if not isinstance(path, str) or not path:
            _fail("changed-file path is invalid")
        if path in seen:
            _fail(f"duplicate changed-file path: {path}")
        seen.add(path)
        previous = row.get("previous_path")
        if previous is not None and (not isinstance(previous, str) or not previous):
            _fail(f"changed-file previous_path is invalid for {path}")
        status = row.get("status")
        if status not in ALLOWED_FILE_STATUS:
            _fail(f"changed-file status is invalid for {path}")
        mode, blob = row.get("mode"), row.get("blob_sha")
        if status == "removed":
            if mode is not None or blob is not None:
                _fail(f"removed changed-file must have null mode/blob_sha: {path}")
        else:
            if mode not in ALLOWED_MODES:
                _fail(f"changed-file mode is invalid for {path}")
            _sha(blob, f"blob_sha for {path}")
        files.append({
            "path": path,
            "previous_path": previous,
            "status": status,
            "mode": mode,
            "blob_sha": blob,
        })
    return files


def _receipt_digest(receipt: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(receipt)).hexdigest()


def _validate_reviews(
    snapshot: dict[str, Any], repository: dict[str, Any], pr: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    raw = _list(snapshot.get("reviews"), "reviews")
    app_reviews: dict[str, Any] = {}
    head_reviews: list[dict[str, Any]] = []
    seen: set[int] = set()
    for value in raw:
        review = _mapping(value, "review")
        rid = review.get("review_id")
        if not _is_int(rid) or rid < 1:
            _fail("review id is invalid")
        if rid in seen:
            _fail(f"duplicate review id: {rid}")
        seen.add(rid)
        if review.get("source") != "T1":
            _fail("GitHub review collection may contain only T1 App evidence")
        if review.get("identity_verified") is not True:
            _fail(f"T1 review {rid} identity is not verified")
        for key in ("user_id", "app_id"):
            if not _is_int(review.get(key)) or review[key] < 1:
                _fail(f"T1 review {rid} {key} is invalid")
        if review.get("commit_id") != pr["head_sha"]:
            _fail(f"T1 review {rid} is not bound to the exact PR head")
        if review.get("pr_number") != pr["number"] or review.get("repository_id") != repository["id"]:
            _fail(f"T1 review {rid} has wrong repository/pull request subject")
        receipt = review.get("receipt")
        digest = review.get("body_receipt_digest")
        if not isinstance(receipt, dict):
            _fail(f"T1 review {rid} receipt is missing")
        if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
            _fail(f"T1 review {rid} body receipt digest is malformed")
        if _receipt_digest(receipt) != digest:
            _fail(f"T1 review {rid} receipt digest mismatch")
        app_reviews[str(rid)] = {
            "user_id": review["user_id"],
            "app_id": review["app_id"],
            "commit_id": review["commit_id"],
            "state": review.get("state"),
            "body_receipt_digest": digest,
            "pr_number": review["pr_number"],
            "repository_id": review["repository_id"],
        }
        head_reviews.append({
            "source": "T1",
            "review_id": rid,
            "user_id": review["user_id"],
            "app_id": review["app_id"],
            "state": review.get("state"),
            "receipt": receipt,
            "body_receipt_digest": digest,
        })
    return app_reviews, head_reviews


def verify_t2_receipt_artifact(
    *,
    artifact_path: Path,
    bundle_path: Path,
    repository: str,
    signer_workflow: str,
    source_ref: str,
    signer_digest: str,
    run_facts: dict[str, Any],
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Verify one canonical receipt artifact and return receipt + trusted claims.

    The signature/certificate is verified by gh. Provider fields are read from
    the signed receipt artifact itself, not from the workflow-controlled SLSA
    predicate. Actor/environment facts must come from GitHub API evidence for
    the exact run bound by the certificate runInvocationURI.
    """
    _sha(signer_digest, "T2 signer digest")
    if not artifact_path.is_file() or not bundle_path.is_file():
        _fail("attestation artifact or bundle is missing")
    try:
        raw = artifact_path.read_bytes()
        receipt = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceIncomplete("attested receipt artifact is invalid") from exc
    if not isinstance(receipt, dict) or raw != canonical_json(receipt):
        _fail("attested receipt artifact must be canonical JSON bytes")
    artifact_digest = _receipt_digest(receipt)

    command = [
        "gh", "attestation", "verify", str(artifact_path),
        "--repo", repository,
        "--bundle", str(bundle_path),
        "--signer-workflow", repository + "/" + signer_workflow,
        "--source-ref", source_ref,
        "--source-digest", signer_digest,
        "--signer-digest", signer_digest,
        "--cert-oidc-issuer", "https://token.actions.githubusercontent.com",
        "--deny-self-hosted-runners",
        "--format", "json",
    ]
    try:
        completed = runner(command, check=False, capture_output=True, text=True)
    except OSError as exc:
        raise EvidenceIncomplete("gh attestation verifier is unavailable") from exc
    if completed.returncode != 0:
        _fail("gh attestation verification failed")
    try:
        rows = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise EvidenceIncomplete("gh attestation verification output is malformed") from exc
    if not isinstance(rows, list) or len(rows) != 1:
        _fail("attestation verification must yield exactly one verified statement")
    verification = _mapping(rows[0].get("verificationResult"), "verificationResult")
    signature = _mapping(verification.get("signature"), "verificationResult.signature")
    cert = _mapping(signature.get("certificate"), "verificationResult.signature.certificate")
    statement = _mapping(verification.get("statement"), "verificationResult.statement")

    if cert.get("issuer") != "https://token.actions.githubusercontent.com":
        _fail("attestation certificate issuer is not trusted")
    if cert.get("githubWorkflowRepository") != repository:
        _fail("attestation certificate repository is not trusted")
    if cert.get("githubWorkflowRef") != source_ref:
        _fail("attestation certificate source ref is not trusted")
    if cert.get("sourceRepositoryDigest") != signer_digest:
        _fail("attestation certificate source digest is not pinned")
    if cert.get("runnerEnvironment") != "github-hosted":
        _fail("self-hosted or unknown attestation runner is forbidden")

    invocation = cert.get("runInvocationURI")
    if not isinstance(invocation, str):
        _fail("attestation certificate has no run invocation URI")
    escaped_repo = re.escape(repository)
    match = re.fullmatch(
        rf"https://github\.com/{escaped_repo}/actions/runs/(\d+)/attempts/(\d+)",
        invocation,
    )
    if not match:
        _fail("attestation run invocation URI is malformed")
    run_id, run_attempt = int(match.group(1)), int(match.group(2))

    if run_facts.get("run_id") != run_id or run_facts.get("run_attempt") != run_attempt:
        _fail("attestation run does not match trusted GitHub run facts")
    if run_facts.get("workflow_path") != signer_workflow:
        _fail("attestation run workflow path is not trusted")
    if run_facts.get("head_sha") != signer_digest or run_facts.get("ref") != source_ref:
        _fail("attestation run source binding is not trusted")
    if run_facts.get("event") != "workflow_dispatch":
        _fail("attestation run was not workflow_dispatch")
    for key in ("triggering_actor_id", "environment_approver_id", "run_id", "run_attempt"):
        if not _is_int(run_facts.get(key)) or run_facts[key] < 1:
            _fail(f"attestation run fact {key} is missing")
    if run_facts.get("environment_approved") is not True:
        _fail("attestation environment approval is not verified")
    environment = run_facts.get("environment")
    if not isinstance(environment, str) or not environment:
        _fail("attestation environment is missing")

    subjects = statement.get("subject")
    if not isinstance(subjects, list):
        _fail("verified statement subject is missing")
    expected_hex = artifact_digest.removeprefix("sha256:")
    if not any(
        isinstance(item, dict)
        and isinstance(item.get("digest"), dict)
        and item["digest"].get("sha256") == expected_hex
        for item in subjects
    ):
        _fail("verified statement does not bind the canonical receipt digest")

    review = _mapping(receipt.get("review"), "attested receipt review")
    execution = _mapping(review.get("provider_execution"), "attested provider execution")
    request_ids = execution.get("request_ids")
    if not isinstance(request_ids, list) or not request_ids or not all(isinstance(x, str) and x for x in request_ids):
        _fail("attested provider request ids are missing")
    for key in ("response_digest", "inputs_digest"):
        if not isinstance(execution.get(key), str) or not DIGEST.fullmatch(execution[key]):
            _fail(f"attested provider {key} is malformed")
    provider, model = execution.get("provider"), execution.get("model")
    if not isinstance(provider, str) or not provider or not isinstance(model, str) or not model:
        _fail("attested provider/model is missing")

    claims = {
        "signature_verified": True,
        "issuer": cert["issuer"],
        "repository_id": run_facts.get("repository_id"),
        "workflow_path": signer_workflow,
        "workflow_commit_sha": signer_digest,
        "ref": source_ref,
        "event": run_facts["event"],
        "environment": environment,
        "environment_approved": True,
        "triggering_actor_id": run_facts["triggering_actor_id"],
        "environment_approver_id": run_facts["environment_approver_id"],
        "run_id": run_id,
        "run_attempt": run_attempt,
        "subject_digest": artifact_digest,
        "response_digest": execution["response_digest"],
        "provider": provider,
        "model": model,
        "inputs_digest": execution["inputs_digest"],
        "request_ids_digest": "sha256:" + hashlib.sha256(
            canonical_json(sorted(request_ids))
        ).hexdigest(),
    }
    if not _is_int(claims["repository_id"]):
        _fail("attestation run repository id is missing")
    return receipt, claims


def _validate_attestations(
    snapshot: dict[str, Any], repository: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    raw = _mapping(snapshot.get("attestations"), "attestations")
    if not raw:
        return {}
    trusted = snapshot["collection"].get("trusted_t2")
    if not isinstance(trusted, dict):
        _fail("attestation trust policy is missing")
    trusted_path = trusted.get("workflow_path")
    trusted_ref = trusted.get("ref")
    trusted_shas = trusted.get("workflow_commit_shas")
    if not isinstance(trusted_path, str) or not isinstance(trusted_ref, str) or not isinstance(trusted_shas, list):
        _fail("attestation trust policy is malformed")
    result: dict[str, dict[str, Any]] = {}
    seen_runs: set[tuple[int, int]] = set()
    for receipt_id, value in raw.items():
        if not isinstance(receipt_id, str) or not receipt_id:
            _fail("attestation receipt id is invalid")
        claims = _mapping(value, f"attestation {receipt_id}")
        missing = sorted(T2_REQUIRED_CLAIMS - set(claims))
        if missing:
            _fail(f"attestation {receipt_id} missing verified claim {missing[0]}")
        if claims.get("signature_verified") is not True:
            _fail(f"attestation {receipt_id} signature is not verified")
        if claims.get("repository_id") != repository["id"]:
            _fail(f"attestation {receipt_id} repository is not trusted")
        if claims.get("workflow_path") != trusted_path or claims.get("ref") != trusted_ref:
            _fail(f"attestation {receipt_id} workflow/ref is not trusted")
        if claims.get("workflow_commit_sha") not in trusted_shas:
            _fail(f"attestation {receipt_id} workflow commit is not trusted")
        _sha(claims.get("workflow_commit_sha"), f"attestation {receipt_id} workflow commit")
        if claims.get("event") != "workflow_dispatch":
            _fail(f"attestation {receipt_id} event is not workflow_dispatch")
        if claims.get("environment_approved") is not True:
            _fail(f"attestation {receipt_id} environment approval is not verified")
        for key in ("triggering_actor_id", "environment_approver_id", "run_id", "run_attempt"):
            if not _is_int(claims.get(key)) or claims[key] < 1:
                _fail(f"attestation {receipt_id} {key} is not a verified integer claim")
        run_key = (claims["run_id"], claims["run_attempt"])
        if run_key in seen_runs:
            _fail(f"duplicate attestation run identity: {run_key[0]}/{run_key[1]}")
        seen_runs.add(run_key)
        for key in ("subject_digest", "response_digest", "inputs_digest", "request_ids_digest"):
            if not isinstance(claims.get(key), str) or not DIGEST.fullmatch(claims[key]):
                _fail(f"attestation {receipt_id} {key} is malformed")
        if not isinstance(claims.get("issuer"), str) or not claims["issuer"]:
            _fail(f"attestation {receipt_id} issuer is missing")
        for key in ("environment", "provider", "model"):
            if not isinstance(claims.get(key), str) or not claims[key]:
                _fail(f"attestation {receipt_id} {key} is missing")
        result[receipt_id] = dict(claims)
    return result


def _validate_check_runs(snapshot: dict[str, Any], pr: dict[str, Any]) -> list[dict[str, Any]]:
    raw = _list(snapshot.get("check_runs"), "check_runs")
    seen: set[int] = set()
    checks: list[dict[str, Any]] = []
    for value in raw:
        check = _mapping(value, "check run")
        cid = check.get("id")
        if not _is_int(cid) or cid < 1:
            _fail("check run id is invalid")
        if cid in seen:
            _fail(f"duplicate check run id: {cid}")
        seen.add(cid)
        if check.get("head_sha") != pr["head_sha"]:
            _fail(f"check run {cid} is not bound to the exact PR head")
        for key in ("name", "workflow_path"):
            if not isinstance(check.get(key), str) or not check[key]:
                _fail(f"check run {cid} {key} is missing")
        if not _is_int(check.get("app_id")) or check["app_id"] < 1:
            _fail(f"check run {cid} app_id is invalid")
        _sha(check.get("workflow_sha"), f"check run {cid} workflow_sha")
        checks.append({
            "id": cid,
            "name": check["name"],
            "app_id": check["app_id"],
            "head_sha": check["head_sha"],
            "conclusion": check.get("conclusion"),
            "workflow_path": check["workflow_path"],
            "workflow_sha": check["workflow_sha"],
        })
    return checks


def _validate_consumed(snapshot: dict[str, Any]) -> dict[str, list[Any]]:
    raw = _mapping(snapshot.get("consumed"), "consumed")
    result: dict[str, list[Any]] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not key:
            _fail("consumed identity key is invalid")
        if not isinstance(value, list) or len(value) != 2 or not _is_int(value[0]):
            _fail(f"consumed ledger entry {key!r} is malformed")
        _sha(value[1], f"consumed ledger SHA for {key}")
        result[key] = [value[0], value[1]]
    return result


def _validate_review_inventory(snapshot: dict[str, Any], pr: dict[str, Any]) -> list[dict[str, Any]]:
    raw = _list(snapshot.get("review_inventory"), "review_inventory")
    seen: set[int] = set()
    inventory: list[dict[str, Any]] = []
    for value in raw:
        row = _mapping(value, "review inventory row")
        rid = row.get("review_id")
        if not _is_int(rid) or rid < 1:
            _fail("review inventory id is invalid")
        if rid in seen:
            _fail(f"duplicate review inventory id: {rid}")
        seen.add(rid)
        if row.get("commit_id") != pr["head_sha"]:
            _fail(f"review inventory {rid} is not bound to exact head")
        user_id = row.get("user_id")
        app_id = row.get("app_id")
        if user_id is not None and (not _is_int(user_id) or user_id < 1):
            _fail(f"review inventory {rid} user_id is invalid")
        if app_id is not None and (not _is_int(app_id) or app_id < 1):
            _fail(f"review inventory {rid} app_id is invalid")
        inventory.append({
            "review_id": rid,
            "user_id": user_id,
            "app_id": app_id,
            "commit_id": row["commit_id"],
            "state": row.get("state"),
        })
    return inventory


def _validate_check_run_inventory(snapshot: dict[str, Any], pr: dict[str, Any]) -> list[dict[str, Any]]:
    raw = _list(snapshot.get("check_run_inventory"), "check_run_inventory")
    seen: set[int] = set()
    inventory: list[dict[str, Any]] = []
    for value in raw:
        row = _mapping(value, "check-run inventory row")
        cid = row.get("id")
        if not _is_int(cid) or cid < 1:
            _fail("check-run inventory id is invalid")
        if cid in seen:
            _fail(f"duplicate check-run inventory id: {cid}")
        seen.add(cid)
        if row.get("head_sha") != pr["head_sha"]:
            _fail(f"check-run inventory {cid} is not bound to exact head")
        app_id = row.get("app_id")
        if app_id is not None and (not _is_int(app_id) or app_id < 1):
            _fail(f"check-run inventory {cid} app_id is invalid")
        name = row.get("name")
        if not isinstance(name, str) or not name:
            _fail(f"check-run inventory {cid} name is missing")
        inventory.append({
            "id": cid,
            "name": name,
            "app_id": app_id,
            "head_sha": row["head_sha"],
            "conclusion": row.get("conclusion"),
        })
    return inventory


def build_trusted_context(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Validate an exhaustive trusted snapshot and return verifier context."""
    snapshot = _mapping(snapshot, "snapshot")
    collection = _validate_collection(snapshot)
    repository, pr = _validate_subject(snapshot, collection)
    changed_files = _validate_changed_files(snapshot, pr)
    review_inventory = _validate_review_inventory(snapshot, pr)
    check_run_inventory = _validate_check_run_inventory(snapshot, pr)
    app_reviews, head_reviews = _validate_reviews(snapshot, repository, pr)
    attestations = _validate_attestations(snapshot, repository)
    checks = _validate_check_runs(snapshot, pr)
    consumed = _validate_consumed(snapshot)

    review_ids = {row["review_id"] for row in review_inventory}
    missing_review_ids = sorted(
        int(review_id) for review_id in app_reviews if int(review_id) not in review_ids
    )
    if missing_review_ids:
        _fail(f"trusted T1 review missing from complete review inventory: {missing_review_ids[0]}")
    check_ids = {row["id"] for row in check_run_inventory}
    missing_check_ids = sorted(check["id"] for check in checks if check["id"] not in check_ids)
    if missing_check_ids:
        _fail(f"trusted check run missing from complete check-run inventory: {missing_check_ids[0]}")

    t2_reviews = snapshot.get("t2_reviews", [])
    if not isinstance(t2_reviews, list):
        _fail("t2_reviews must be a list")
    seen_t2: set[str] = set()
    for value in t2_reviews:
        entry = _mapping(value, "T2 head review")
        receipt_id = entry.get("receipt_id")
        receipt = entry.get("receipt")
        if not isinstance(receipt_id, str) or not receipt_id or not isinstance(receipt, dict):
            _fail("T2 head review is malformed")
        if receipt_id in seen_t2:
            _fail(f"duplicate T2 head review receipt id: {receipt_id}")
        seen_t2.add(receipt_id)
        if receipt_id not in attestations:
            _fail(f"T2 head review {receipt_id} has no verified attestation")
        head_reviews.append({"source": "T2", "receipt_id": receipt_id, "receipt": receipt})

    implementation = snapshot.get("implementation_evidence")
    if implementation is not None and not isinstance(implementation, dict):
        _fail("implementation_evidence must be a mapping or null")

    risk = snapshot.get("effective_risk_class")
    if risk not in {"trivial", "normal", "material", "architecture", "security", "high_blast_radius"}:
        _fail("effective_risk_class is invalid")

    return {
        "repository": {"id": repository["id"], "full_name": repository["full_name"]},
        "pr": {
            "number": pr["number"],
            "author_user_id": pr["author_user_id"],
            "head_sha": pr["head_sha"],
            "base_sha": pr["base_sha"],
            "merge_base_sha": pr["merge_base_sha"],
            "changed_files": changed_files,
            "changed_files_complete": True,
        },
        "effective_risk_class": risk,
        "implementation_evidence": implementation,
        "app_reviews": app_reviews,
        "review_inventory": review_inventory,
        "head_reviews": head_reviews,
        "head_reviews_complete": True,
        "attestations": attestations,
        "check_run_inventory": check_run_inventory,
        "check_runs": checks,
        "check_runs_complete": True,
        "consumed": consumed,
        "consumed_complete": True,
    }


def _load_verifier(repo_root: Path):
    path = repo_root / "scripts" / "development" / "verify_review_receipts.py"
    spec = importlib.util.spec_from_file_location("c2pro_verify_review_receipts", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load trusted review verifier")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    if not callable(getattr(module, "verify", None)):
        raise RuntimeError("trusted review verifier exposes no public verify()")
    return module


def run_audit(
    snapshot: dict[str, Any],
    receipts: Any,
    policy: dict[str, Any],
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Invoke only the verifier public API and return an AUDIT_ONLY result."""
    context = build_trusted_context(snapshot)
    verifier = _load_verifier(repo_root or Path(__file__).resolve().parents[3])
    result = verifier.verify(receipts, policy, context)
    return {
        "mode": "AUDIT_ONLY",
        "gate_satisfied": bool(result.gate_satisfied),
        "risk_class": result.risk_class,
        "required_roles": list(result.required_roles),
        "satisfied_roles": list(result.satisfied_roles),
        "violations": [v.__dict__ for v in result.violations],
        "context_digest": canonical_inputs_digest(context),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--receipts", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    receipts = yaml.safe_load(args.receipts.read_text(encoding="utf-8"))
    policy = yaml.safe_load(args.policy.read_text(encoding="utf-8"))
    audit = run_audit(snapshot, receipts, policy)
    args.output.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(audit, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
