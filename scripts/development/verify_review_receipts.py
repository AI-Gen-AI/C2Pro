#!/usr/bin/env python3
"""C2Pro independent-agent review receipt verifier -- OFFLINE, AUDIT_ONLY (#1009, DEV-14 #991).

Decides whether a set of ``c2pro-review-receipt-v1`` receipts would satisfy the review gate of one
pull request at one exact head. It never approves, merges, labels or edits anything, and nothing
enforces its result: the canonical review policy is unchanged.

Trust split -- the verifier trusts only two inputs, both assembled outside the PR under review:

* ``policy``  -- verifier configuration read from the protected base branch (allowed App ids,
  the attesting workflow path and pinned commit SHAs, dispatchers, role eligibility, worker
  providers, gate composition, required checks with their producing workflow, high-blast-radius
  paths). Never taken from the PR.
* ``context`` -- facts fetched by a trusted adapter from the GitHub API and the attestation
  verifier: PR author, exact head/base/merge-base, the complete changed-file list, the effective
  risk class from the base envelope, the implementer's work receipt, App reviews, EVERY review
  evidence recorded at the head (so an author cannot submit only the approving one), check runs
  with their producer, verified attestation claims and already consumed ids.

Receipts are untrusted claims; every field that matters is re-derived from ``context``.
Signature verification of an attestation bundle (Sigstore) is the adapter's job (PR-B); this
module checks the verified claims it reports. Re-verifying the same receipt for the same PR and
head is idempotent; any other reuse is rejected. In PR-A only synthetic contexts exist.

The result is an audit observation, never an authorization: ``authorizes_merge`` is always false and
the CLI never exits 0 (3 = evidence would satisfy the gate, 1 = it would not), so neither a CI status
nor a caller reading the exit code can treat an AUDIT_ONLY run as a passing review gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime
from itertools import pairwise
from pathlib import Path
from typing import Any

import yaml

SCHEMA_PATH = Path(__file__).resolve().parent / "review_attestation" / "review-receipt.schema.yaml"
ENFORCEMENT_MODE = "AUDIT_ONLY"
BLOCKING_SEVERITIES = {"P0", "P1", "P2"}
UNRESOLVABLE_SEVERITIES = {"P0", "P1"}  # a reviewer cannot self-clear these at the head it approves
ROLE_ORDER = ("principal", "challenger", "orchestrator_synthesis")
RISK_RANK = ("trivial", "normal", "material", "architecture", "security", "high_blast_radius")
SYNTHESIS_RISKS = {"architecture", "security", "high_blast_radius"}
FILE_FIELDS = ("path", "previous_path", "status", "mode", "blob_sha")
APPROVING_STATES = {"APPROVED"}
# CLI exit codes. AUDIT_ONLY never exits 0, so no CI status or caller can read an audit as approval.
EXIT_AUDIT_NOT_SATISFIED = 1
EXIT_AUDIT_SATISFIED_NOT_AUTHORIZATION = 3
_STRICT_ID = re.compile(r"[a-z0-9_]+")
_RFC3339 = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})")
_SHA256_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_WORK_ID = re.compile(r"C2PRO-DEV-[0-9]{2}")  # same shape as the receipt schema; always fullmatch


@dataclass(frozen=True)
class Violation:
    code: str
    receipt_id: str | None
    detail: str


@dataclass
class GateResult:
    """An audit observation. ``gate_satisfied`` describes the evidence; it is never an authorization."""

    gate_satisfied: bool
    risk_class: str
    required_roles: tuple[str, ...]
    satisfied_roles: tuple[str, ...]
    violations: list[Violation] = field(default_factory=list)
    mode: str = field(default=ENFORCEMENT_MODE, init=False)  # set by this module only, never by a caller

    @property
    def codes(self) -> set[str]:
        return {v.code for v in self.violations}

    @property
    def authorizes_merge(self) -> bool:
        """Always False: this verifier is AUDIT_ONLY and has no authorization path, however it is reconfigured."""
        return False


# ---------------------------------------------------------------------------- digests
def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def receipt_digest(receipt: dict[str, Any]) -> str:
    """The digest an attestation or an App review must bind: the whole receipt, canonically."""
    return "sha256:" + hashlib.sha256(canonical_json(receipt)).hexdigest()


def request_ids_digest(request_ids: list[str]) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(sorted(request_ids))).hexdigest()


def canonical_changed_files(files: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Paths, renames, deletions, modes (incl. symlink 120000 / submodule 160000) and blob ids."""
    rows = [{k: f.get(k) for k in FILE_FIELDS} for f in files]
    return sorted(rows, key=lambda r: tuple("" if r[k] is None else str(r[k]) for k in FILE_FIELDS))


def diff_digest(files: Iterable[dict[str, Any]]) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(canonical_changed_files(files))).hexdigest()


def _is_int(value: Any) -> bool:
    return type(value) is int  # bool and float never stand in for an id


# ---------------------------------------------------------------------------- rules
Rule = Callable[[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]], list[Violation]]
RULES: dict[str, Rule] = {}


def rule(name: str) -> Callable[[Rule], Rule]:
    def register(fn: Rule) -> Rule:
        RULES[name] = fn
        return fn
    return register


def _rid(receipt: Any) -> str | None:
    value = receipt.get("receipt_id") if isinstance(receipt, dict) else None
    return value if isinstance(value, str) else None


def _v(code: str, receipt: Any, detail: str) -> list[Violation]:
    return [Violation(code, _rid(receipt), detail)]


def _strict_strings(node: Any) -> bool:
    if isinstance(node, dict):
        return all(_strict_strings(v) for v in node.values())
    if isinstance(node, list):
        return all(_strict_strings(v) for v in node)
    if isinstance(node, float):
        return False
    return not (isinstance(node, str) and ("\n" in node or "\r" in node))


@rule("schema")
def _schema(receipt, policy, context, receipts):
    import jsonschema

    schema = yaml.safe_load(SCHEMA_PATH.read_text())
    errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(receipt), key=lambda e: list(e.path))
    if errors:
        return _v("SCHEMA_INVALID", receipt, errors[0].message)
    if not _strict_strings(receipt):
        return _v("SCHEMA_INVALID", receipt, "floats or line breaks are not allowed in a receipt")
    review = receipt["review"]
    if not (_STRICT_ID.fullmatch(review["worker_id"]) and _STRICT_ID.fullmatch(review["implementation_worker_id"])):
        return _v("SCHEMA_INVALID", receipt, "worker ids must match exactly")
    try:
        if not _RFC3339.fullmatch(receipt["issued_at"]):
            raise ValueError(receipt["issued_at"])
        datetime.fromisoformat(receipt["issued_at"].replace("Z", "+00:00"))
    except ValueError:
        return _v("SCHEMA_INVALID", receipt, "issued_at is not an RFC 3339 timestamp")
    return []


@rule("evidence_tier")
def _tier(receipt, policy, context, receipts):
    tier = receipt["review"]["evidence_tier"]
    if tier == "T3":
        return _v("T3_INGESTION", receipt, "author-posted or unverified evidence never satisfies a gate")
    if tier == "T1" and not policy.get("t1_apps"):
        return _v("T1_DISABLED", receipt, "no GitHub App is allowlisted for T1 reviews")
    return []


@rule("subject")
def _subject(receipt, policy, context, receipts):
    s, pr, repo = receipt["subject"], context["pr"], context["repository"]
    out: list[Violation] = []
    if (s["repository_id"], s["repository"]) != (repo["id"], repo["full_name"]) or s["pr_number"] != pr["number"]:
        out += _v("WRONG_SUBJECT", receipt, "repository or pull request does not match")
    if s["head_sha"] != pr["head_sha"]:
        out += _v("STALE_SHA", receipt, "receipt is not for the current head")
    if (s["base_sha"], s["merge_base_sha"]) != (pr["base_sha"], pr["merge_base_sha"]):
        out += _v("STALE_SHA", receipt, "base or merge base does not match")
    out += _diff_violations(receipt, pr)
    return out


def _diff_violations(receipt: dict[str, Any], pr: dict[str, Any]) -> list[Violation]:
    if pr.get("changed_files_complete") is not True:
        return _v("DIFF_MISMATCH", receipt, "the trusted changed-file list is not known to be complete")
    trusted = canonical_changed_files(pr["changed_files"])
    if len({row["path"] for row in trusted}) != len(trusted):
        return _v("DIFF_MISMATCH", receipt, "duplicate paths in the changed-file list")
    s = receipt["subject"]
    if canonical_changed_files(s["changed_files"]) != trusted or s["diff_digest"] != diff_digest(trusted):
        return _v("DIFF_MISMATCH", receipt, "changed files or diff digest differ from the trusted diff")
    return []


@rule("risk_class")
def _risk(receipt, policy, context, receipts):
    effective = effective_risk_class(policy, context)
    if receipt["risk_class"] != effective:
        return _v("RISK_DOWNGRADE", receipt, f"receipt says {receipt['risk_class']}, effective is {effective}")
    return []


@rule("implementer")
def _implementer(receipt, policy, context, receipts):
    """The trusted work receipt names both the work item and its implementer; the receipt must match both."""
    problem = _work_evidence_problem(context)
    if problem:
        return _v("IMPLEMENTER_UNVERIFIED", receipt, problem)
    evidence = context["implementation_evidence"]
    if receipt["work_id"] != evidence["work_id"]:
        return _v("WORK_MISMATCH", receipt, "receipt is for another work item than the trusted work receipt")
    if receipt["review"]["implementation_worker_id"] != evidence["worker_id"]:
        return _v("IMPLEMENTER_MISMATCH", receipt, "declared implementer differs from the work receipt")
    return []


def _work_evidence_problem(context: dict[str, Any]) -> str | None:
    """Why the trusted work receipt cannot identify the work and its implementer, or None if it can."""
    evidence = context.get("implementation_evidence")
    if not isinstance(evidence, dict) or evidence.get("verified") is not True:
        return "no trusted work receipt names the implementer"
    worker_id = evidence.get("worker_id")
    if not isinstance(worker_id, str) or not _STRICT_ID.fullmatch(worker_id):
        return "the trusted work receipt names no valid implementer id"
    work_id = evidence.get("work_id")
    if not isinstance(work_id, str) or not _WORK_ID.fullmatch(work_id):
        return "the trusted work receipt names no valid work id"
    return None


@rule("eligibility")
def _eligibility(receipt, policy, context, receipts):
    review = receipt["review"]
    if review["worker_id"] not in policy["role_eligibility"].get(review["role"], []):
        return _v("UNREGISTERED_WORKER", receipt, f"{review['worker_id']} is not eligible as {review['role']}")
    return []


@rule("independence")
def _independence(receipt, policy, context, receipts):
    review = receipt["review"]
    implementer = review["implementation_worker_id"]
    providers = policy["worker_providers"]
    if review["worker_id"] == implementer:
        return _v("SAME_WORKER", receipt, "reviewer is the implementation worker")
    if review["role"] not in ("principal", "challenger"):
        return []
    if providers.get(implementer) is None:
        return _v("IMPLEMENTER_PROVIDER_UNKNOWN", receipt, "implementer provider is not registered; independence unprovable")
    provider = providers.get(review["worker_id"])
    if provider is None or provider == providers[implementer]:
        return _v("SAME_PROVIDER", receipt, "reviewer provider is unknown or equals the implementer's")
    if review["role"] == "challenger" and _challenger_shares_principal(receipt, receipts, providers):
        return _v("SAME_WORKER", receipt, "challenger is not independent of the principal")
    return []


def _challenger_shares_principal(receipt: dict[str, Any], receipts: list[dict[str, Any]],
                                 providers: dict[str, str]) -> bool:
    worker = receipt["review"]["worker_id"]
    for other in receipts:
        if other is receipt or other["review"]["role"] != "principal":
            continue
        if other["review"]["worker_id"] == worker or providers.get(other["review"]["worker_id"]) == providers.get(worker):
            return True
    return False


@rule("identity")
def _identity(receipt, policy, context, receipts):
    tier = receipt["review"]["evidence_tier"]
    if tier == "T1":
        return _t1_identity(receipt, policy, context)
    if tier == "T2":
        return _t2_identity(receipt, policy, context) or _t2_execution(receipt, policy, context)
    return []


def _t1_identity(receipt: dict[str, Any], policy: dict[str, Any], context: dict[str, Any]) -> list[Violation]:
    review, ident = receipt["review"], receipt["review"]["identity"]
    app_review = context.get("app_reviews", {}).get(str(ident.get("review_id")))
    if app_review is None:
        return _v("FORGED_IDENTITY", receipt, "review id not found by the trusted adapter")
    if app_review.get("user_id") == context["pr"]["author_user_id"]:
        return _v("AUTHOR_SELF_REVIEW", receipt, "review submitted by the pull request author")
    actual = (app_review.get("app_id"), app_review.get("user_id"))
    allowed = {(a["app_id"], a["user_id"]) for a in policy.get("t1_apps", [])}
    declared = (ident.get("github_app_id"), ident.get("github_user_id"))
    if not all(_is_int(x) for x in actual) or actual not in allowed or actual != declared:
        return _v("FORGED_IDENTITY", receipt, "App/user ids are not the pinned reviewer App")
    if policy.get("t1_apps_worker", {}).get(str(actual[0])) != review["worker_id"]:
        return _v("FORGED_IDENTITY", receipt, "App does not map to the declared worker")
    bound = (app_review.get("pr_number"), app_review.get("repository_id"))
    if bound != (context["pr"]["number"], context["repository"]["id"]):
        return _v("WRONG_SUBJECT", receipt, "App review belongs to another pull request or repository")
    if app_review.get("commit_id") != context["pr"]["head_sha"] or app_review.get("state") not in APPROVING_STATES:
        return _v("STALE_SHA", receipt, "App review is not an APPROVED review of the exact head")
    if app_review.get("body_receipt_digest") != receipt_digest(receipt):
        return _v("RECEIPT_TAMPERED", receipt, "receipt differs from the one carried by the App review")
    return []


def _t2_identity(receipt: dict[str, Any], policy: dict[str, Any], context: dict[str, Any]) -> list[Violation]:
    rid, ident, t2 = _rid(receipt), receipt["review"]["identity"], policy.get("t2")
    if not t2:
        return _v("T2_DISABLED", receipt, "no trusted attesting workflow is configured")
    claims = context.get("attestations", {}).get(rid or "")
    if not isinstance(claims, dict) or claims.get("signature_verified") is not True:
        return _v("AUTHOR_CONTROLLED_ATTESTATION", receipt, "no verified attestation for this receipt")
    expected = {
        "issuer": t2["issuer"], "repository_id": context["repository"]["id"], "workflow_path": t2["workflow_path"],
        "ref": t2["ref"], "environment": t2["environment"], "event": "workflow_dispatch",
    }
    wrong = [k for k, value in expected.items() if claims.get(k) != value]
    if wrong:
        return _v("AUTHOR_CONTROLLED_ATTESTATION", receipt, f"attestation {wrong[0]} is not the trusted value")
    if claims.get("workflow_commit_sha") not in t2["workflow_commit_shas"]:
        return _v("AUTHOR_CONTROLLED_ATTESTATION", receipt, "attesting workflow commit is not pinned")
    if not _dispatch_is_independent(claims, t2, context["pr"]["author_user_id"]):
        return _v("AUTHOR_CONTROLLED_ATTESTATION", receipt, "dispatch or approval was not by an independent allowed maintainer")
    bound = (ident.get("workflow_path"), ident.get("workflow_commit_sha"), ident.get("run_id"), ident.get("run_attempt"))
    if bound != (claims["workflow_path"], claims["workflow_commit_sha"], claims.get("run_id"), claims.get("run_attempt")):
        return _v("AUTHOR_CONTROLLED_ATTESTATION", receipt, "receipt identity does not match the attested run")
    if claims.get("subject_digest") != receipt_digest(receipt):
        return _v("RECEIPT_TAMPERED", receipt, "receipt differs from the attested subject")
    return []


def _dispatch_is_independent(claims: dict[str, Any], t2: dict[str, Any], author: int) -> bool:
    actor, approver = claims.get("triggering_actor_id"), claims.get("environment_approver_id")
    return (_is_int(actor) and _is_int(approver) and actor in t2["dispatcher_user_ids"]
            and approver in t2.get("approver_user_ids", []) and claims.get("environment_approved") is True
            and author not in (actor, approver) and approver != actor)


def _t2_execution(receipt: dict[str, Any], policy: dict[str, Any], context: dict[str, Any]) -> list[Violation]:
    execution = receipt["review"].get("provider_execution")
    claims = context["attestations"][_rid(receipt)]
    if not execution:
        return _v("PROVIDER_EVIDENCE_MISSING", receipt, "a T2 review must carry provider execution evidence")
    if execution["prompt_template_sha256"] not in policy["t2"]["prompt_template_shas"]:
        return _v("PROMPT_TEMPLATE_UNTRUSTED", receipt, "prompt template is not pinned on the base branch")
    if execution["untrusted_text_wrapped"] is not True:
        return _v("PROMPT_INJECTION", receipt, "PR-authored text reached the model unwrapped")
    if execution["provider"] != policy["worker_providers"].get(receipt["review"]["worker_id"]):
        return _v("PROVIDER_MISMATCH", receipt, "executed provider is not the worker's registered provider")
    attested_inputs = claims.get("inputs_digest")
    if not isinstance(attested_inputs, str) or not _SHA256_DIGEST.fullmatch(attested_inputs):
        return _v("PROVIDER_MISMATCH", receipt, "attestation has no valid provider inputs digest")
    if execution["inputs_digest"] != attested_inputs:
        return _v("PROVIDER_MISMATCH", receipt, "provider inputs differ from the attested execution")
    attested = (claims.get("provider"), claims.get("model"), claims.get("request_ids_digest"))
    if attested != (execution["provider"], execution["model"], request_ids_digest(execution["request_ids"])):
        return _v("PROVIDER_MISMATCH", receipt, "provider, model or requests differ from the attested execution")
    if claims.get("response_digest") != execution["response_digest"]:
        return _v("RECEIPT_TAMPERED", receipt, "model response does not match the attested response")
    return []


@rule("reuse")
def _reuse(receipt, policy, context, receipts):
    pr = context["pr"]
    here = [pr["number"], pr["head_sha"]]
    consumed = context.get("consumed", {})
    for kind in ("receipt", "review", "run"):
        value = _key(receipt, kind)
        if value is None:
            continue
        prior = consumed.get(f"{kind}:{value}")
        if prior is not None and list(prior) != here:
            return _v("RECEIPT_REUSE", receipt, f"{kind} id already consumed by another PR or head")
        if any(r is not receipt and _key(r, kind) == value for r in receipts):
            return _v("RECEIPT_REUSE", receipt, f"{kind} id appears twice in this submission")
    return []


def _key(receipt: Any, kind: str) -> Any:
    if not isinstance(receipt, dict):
        return None
    ident = receipt.get("review", {}).get("identity", {})
    return {"receipt": _rid(receipt), "review": ident.get("review_id"), "run": ident.get("run_id")}[kind]


@rule("result_consistency")
def _consistency(receipt, policy, context, receipts):
    result = receipt["result"]
    findings = result["findings"]
    if result["verdict"] == "BLOCK" or result["recommended_action"] != "approve":
        return _v("BLOCKING_FINDING", receipt, "review does not approve; escalate or remediate")
    if len({f["id"] for f in findings}) != len(findings):
        return _v("BLOCKING_FINDING", receipt, "duplicate finding ids")
    for f in findings:
        unresolved = f.get("resolved") is not True
        if f["severity"] in UNRESOLVABLE_SEVERITIES or (f["severity"] in BLOCKING_SEVERITIES and unresolved):
            return _v("BLOCKING_FINDING", receipt, f"{f['severity']} finding {f['id']} contradicts approval")
    if result["security_concern"] or result["scope_deviation"]:
        return _v("BLOCKING_FINDING", receipt, "approval contradicts a security or scope concern")
    if result["architecture_drift"] and effective_risk_class(policy, context) not in SYNTHESIS_RISKS:
        return _v("BLOCKING_FINDING", receipt, "architecture drift outside an architecture-reviewed gate")
    return []


@rule("tests")
def _tests(receipt, policy, context, receipts):
    """An approval must have seen every required check green on its latest trusted run at the head."""
    observed = receipt["result"]["tests_observed"]
    checks = {c["id"]: c for c in context.get("check_runs", []) if _is_int(c.get("id"))}
    specs = {r["name"]: r for r in policy["required_checks"]}
    if not set(specs) <= {o["name"] for o in observed}:
        return _v("CHECK_PROVENANCE", receipt, "receipt does not observe every required check")
    head = context["pr"]["head_sha"]
    for o in observed:
        check = checks.get(o["check_run_id"])
        if check is None or o["name"] != check["name"] or o["conclusion"] != check["conclusion"]:
            return _v("CHECK_PROVENANCE", receipt, f"observed test {o['name']!r} does not match a check run")
        spec = specs.get(o["name"])
        if spec is None:
            continue
        if not _produced_by(check, spec, head):
            return _v("CHECK_PROVENANCE", receipt, f"observed test {o['name']!r} is not from the trusted producer on the head")
        latest = _latest_run(spec, context)
        if latest is None or check["id"] != latest["id"] or check["conclusion"] != "success":
            return _v("CHECK_PROVENANCE", receipt, f"observed required check {o['name']!r} is not its latest successful run")
    return []


def _produced_by(check: dict[str, Any], spec: dict[str, Any], head: str) -> bool:
    return (check.get("app_id") == spec["app_id"] and check.get("workflow_path") == spec["workflow_path"]
            and check.get("workflow_sha") in spec["workflow_shas"] and check.get("head_sha") == head)


def _latest_run(spec: dict[str, Any], context: dict[str, Any]) -> dict[str, Any] | None:
    """Latest run of this producer on the head, pinned or not, so an unpinned rerun is never skipped over."""
    head = context["pr"]["head_sha"]
    runs = [c for c in context.get("check_runs", [])
            if c.get("name") == spec["name"] and _is_int(c.get("id")) and c.get("app_id") == spec["app_id"]
            and c.get("workflow_path") == spec["workflow_path"] and c.get("head_sha") == head]
    return max(runs, key=lambda c: c["id"]) if runs else None


@rule("synthesis")
def _synthesis(receipt, policy, context, receipts):
    if receipt["review"]["role"] != "orchestrator_synthesis":
        return []
    referenced = {(ref["receipt_id"], ref["digest"]) for ref in receipt["result"].get("synthesis_of") or []}
    reviewed = {(_rid(r), receipt_digest(r)) for r in receipts if r["review"]["role"] in ("principal", "challenger")}
    if not reviewed or referenced != reviewed:
        return _v("MISSING_SYNTHESIS", receipt, "synthesis must bind exactly every principal and challenger receipt by digest")
    return []


# ---------------------------------------------------------------------------- gate-level checks
def effective_risk_class(policy: dict[str, Any], context: dict[str, Any]) -> str:
    """The stricter of the base-envelope risk and high_blast_radius when the PR touches verification."""
    base = context["effective_risk_class"]
    files = context["pr"]["changed_files"]
    paths = {f["path"] for f in files} | {f["previous_path"] for f in files if f.get("previous_path")}
    prefixes = [prefix.rstrip("/") for prefix in policy["high_blast_radius_paths"]]
    touched = any(p == prefix or p.startswith(prefix + "/") for prefix in prefixes for p in paths)
    if not touched or base not in RISK_RANK:
        return base
    return max(base, "high_blast_radius", key=RISK_RANK.index)


def _policy_violations(policy: dict[str, Any], risk: str) -> list[Violation]:
    gates = policy["gates"]
    if risk not in RISK_RANK or risk not in gates:
        return [Violation("POLICY_INVALID", None, f"unknown risk class {risk!r}")]
    for lower, higher in pairwise(RISK_RANK):
        if not set(gates.get(lower, [])) <= set(gates.get(higher, [])):
            return [Violation("POLICY_INVALID", None, f"gate for {higher} is weaker than for {lower}")]
    if any(set(ROLE_ORDER) - set(gates.get(r, [])) for r in SYNTHESIS_RISKS):
        return [Violation("POLICY_INVALID", None, "architecture/security gates must require all three roles")]
    if not policy["required_checks"]:
        return [Violation("POLICY_INVALID", None, "at least one required check must be configured")]
    names = [spec["name"] for spec in policy["required_checks"]]
    if len(set(names)) != len(names):
        return [Violation("POLICY_INVALID", None, "required check names must be unique, one producer each")]
    return []


def _context_violations(context: dict[str, Any]) -> list[Violation]:
    """The adapter must prove completeness; an absent or partial fact never reads as 'nothing found'."""
    pr = context["pr"]
    if not _is_int(pr.get("author_user_id")):
        return [Violation("POLICY_INVALID", None, "pull request author id is not an integer")]
    if pr.get("changed_files_complete") is not True:
        return [Violation("POLICY_INVALID", None, "changed-file list is not known to be complete")]
    if not isinstance(context.get("head_reviews"), list) or context.get("head_reviews_complete") is not True:
        return [Violation("POLICY_INVALID", None, "head review evidence is missing or incomplete")]
    if not isinstance(context.get("check_runs"), list) or context.get("check_runs_complete") is not True:
        return [Violation("POLICY_INVALID", None, "check-run evidence is not known to be complete")]
    if not isinstance(context.get("consumed"), dict) or context.get("consumed_complete") is not True:
        return [Violation("POLICY_INVALID", None, "consumed-id evidence is not known to be complete")]
    problem = _work_evidence_problem(context)  # checked here too: a gate with no required role runs no receipt rule
    if problem:
        return [Violation("IMPLEMENTER_UNVERIFIED", None, problem)]
    return []


def _check_violations(policy: dict[str, Any], context: dict[str, Any]) -> list[Violation]:
    """Required checks hold once per gate: the latest trusted-producer run on the head must be green."""
    head = context["pr"]["head_sha"]
    for spec in policy["required_checks"]:
        latest = _latest_run(spec, context)
        if latest is None or latest.get("conclusion") != "success" or not _produced_by(latest, spec, head):
            return [Violation("CHECK_PROVENANCE", None, f"required check {spec['name']!r} has no green latest trusted run")]
    return []


def _contradiction_violations(policy: dict[str, Any], context: dict[str, Any]) -> list[Violation]:
    """Every review recorded at the head counts, not only the receipts the author chose to submit."""
    allowed_apps = {(a["app_id"], a["user_id"]) for a in policy.get("t1_apps", [])}
    for entry in context["head_reviews"]:
        source = entry.get("source") if isinstance(entry, dict) else None
        if source == "T1":
            if (entry.get("app_id"), entry.get("user_id")) in allowed_apps and not _app_review_approves(entry, policy, context):
                return [Violation("CONTRADICTING_REVIEW", None, f"App review {entry.get('review_id')} does not approve")]
        elif source == "T2":
            if not _attested_review_approves(entry.get("receipt"), policy, context):
                return [Violation("CONTRADICTING_REVIEW", entry.get("receipt_id"), "an attested review at this head does not approve")]
        else:
            return [Violation("CONTRADICTING_REVIEW", None, f"unknown head review source {source!r}")]
    return []


def _app_review_approves(entry: dict[str, Any], policy: dict[str, Any], context: dict[str, Any]) -> bool:
    """An allowlisted App review approves only if APPROVED and its carried receipt verifies and approves.

    Reviews by Apps outside the allowlist are ignored: they carry no authority either way.
    """
    receipt = entry.get("receipt")
    return (entry.get("state") == "APPROVED" and isinstance(receipt, dict)
            and entry.get("body_receipt_digest") == receipt_digest(receipt)
            and _attested_review_approves(receipt, policy, context))


def _attested_review_approves(receipt: Any, policy: dict[str, Any], context: dict[str, Any]) -> bool:
    """Same consistency rule as a submitted receipt; anything unreadable counts as not approving."""
    try:
        return isinstance(receipt, dict) and not _consistency(receipt, policy, context, [])
    except Exception:  # noqa: BLE001
        return False


def _receipt_violations(receipt: Any, policy: dict[str, Any], context: dict[str, Any], receipts: list[Any],
                        disabled_rules: frozenset[str]) -> list[Violation]:
    if not isinstance(receipt, dict):
        return [Violation("SCHEMA_INVALID", None, "a receipt must be a mapping")]
    found: list[Violation] = []
    for name, check in RULES.items():
        if name in disabled_rules:
            continue
        try:
            found.extend(check(receipt, policy, context, receipts))
        except Exception as exc:  # noqa: BLE001 - malformed input is a violation, never a pass
            found.append(Violation("SCHEMA_INVALID", _rid(receipt), f"{name}: {type(exc).__name__}"))
        if name == "schema" and found:
            break  # later rules assume the schema shape
    return found


def _verify_internal(receipts: Any, policy: dict[str, Any], context: dict[str, Any],
                     disabled_rules: frozenset[str]) -> GateResult:
    """Fail closed: any violation, in any receipt or at gate level, leaves the gate unsatisfied."""
    try:
        risk = effective_risk_class(policy, context)
        violations = _context_violations(context) or _policy_violations(policy, risk)
        if violations:
            return GateResult(False, str(risk), (), (), violations)
        required = tuple(policy["gates"][risk])
        violations = _check_violations(policy, context) + _contradiction_violations(policy, context)
    except Exception as exc:  # noqa: BLE001 - an unusable policy or context never passes
        return GateResult(False, "unknown", (), (), [Violation("POLICY_INVALID", None, type(exc).__name__)])
    if not isinstance(receipts, list):
        return GateResult(False, risk, required, (), [Violation("SCHEMA_INVALID", None, "receipts must be a list")])
    valid_roles: set[str] = set()
    for receipt in receipts:
        found = _receipt_violations(receipt, policy, context, receipts, disabled_rules)
        violations.extend(found)
        if not found:
            valid_roles.add(receipt["review"]["role"])
    for role in required:
        if role not in valid_roles:
            code = {"challenger": "MISSING_CHALLENGER", "orchestrator_synthesis": "MISSING_SYNTHESIS"}.get(role, "MISSING_PRINCIPAL")
            violations.append(Violation(code, None, f"{risk} requires a valid {role} receipt"))
    satisfied = tuple(r for r in ROLE_ORDER if r in valid_roles)
    return GateResult(gate_satisfied=not violations, risk_class=risk, required_roles=required,
                      satisfied_roles=satisfied, violations=violations)


def _verify_with_disabled_rules(receipts: Any, policy: dict[str, Any], context: dict[str, Any],
                                disabled_rules: frozenset[str]) -> GateResult:
    """Test-only mutation hook. Production callers must use :func:`verify`."""
    return _verify_internal(receipts, policy, context, disabled_rules)


def verify(receipts: Any, policy: dict[str, Any], context: dict[str, Any]) -> GateResult:
    """Fail closed with every verification rule enabled."""
    return _verify_internal(receipts, policy, context, frozenset())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--receipts", type=Path, required=True, help="YAML/JSON list of receipts")
    parser.add_argument("--policy", type=Path, required=True, help="verifier policy from the base branch")
    parser.add_argument("--context", type=Path, required=True, help="trusted facts from the GitHub adapter")
    args = parser.parse_args(argv)
    result = verify(yaml.safe_load(args.receipts.read_text()), yaml.safe_load(args.policy.read_text()),
                    yaml.safe_load(args.context.read_text()))
    print(json.dumps({"mode": result.mode, "gate_satisfied": result.gate_satisfied,
                      "authorizes_merge": result.authorizes_merge, "risk_class": result.risk_class,
                      "required_roles": result.required_roles, "satisfied_roles": result.satisfied_roles,
                      "violations": [v.__dict__ for v in result.violations]}, indent=2))
    return EXIT_AUDIT_SATISFIED_NOT_AUTHORIZATION if result.gate_satisfied else EXIT_AUDIT_NOT_SATISFIED


if __name__ == "__main__":
    sys.exit(main())
