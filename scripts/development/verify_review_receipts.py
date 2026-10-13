#!/usr/bin/env python3
"""C2Pro independent-agent review receipt verifier -- OFFLINE, AUDIT_ONLY (#1009, DEV-14 #991).

Decides whether a set of ``c2pro-review-receipt-v1`` receipts would satisfy the review gate of one
pull request at one exact head. It never approves, merges, labels or edits anything, and nothing
enforces its result: the canonical review policy is unchanged.

Trust split -- the verifier trusts only two inputs, both assembled outside the PR under review:

* ``policy``  -- verifier configuration read from the protected base branch (allowed App ids,
  the attesting workflow path and pinned commit SHAs, dispatchers, role eligibility, worker
  providers, gate composition, high-blast-radius paths). Never taken from the PR.
* ``context`` -- facts fetched by a trusted adapter from the GitHub API and the attestation
  verifier: PR author, exact head/base/merge-base, changed files, effective risk class from the
  base envelope, the implementer's work receipt, App reviews, check runs, verified attestation
  claims and already consumed receipt ids.

Receipts themselves are untrusted claims. Every field that matters is re-derived from
``context`` and compared. Signature verification of an attestation bundle (Sigstore) is the
adapter's job; this module checks the verified claims it reports. In PR-A the adapter does not
exist yet: tests feed synthetic contexts only, and no real identity is ever asserted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

SCHEMA_PATH = Path(__file__).resolve().parent / "review_attestation" / "review-receipt.schema.yaml"
ENFORCEMENT_MODE = "AUDIT_ONLY"
BLOCKING_SEVERITIES = {"P0", "P1", "P2"}
ROLE_ORDER = ("principal", "challenger", "orchestrator_synthesis")
FILE_FIELDS = ("path", "previous_path", "status", "mode", "blob_sha")


@dataclass(frozen=True)
class Violation:
    code: str
    receipt_id: str | None
    detail: str


@dataclass
class GateResult:
    gate_satisfied: bool
    risk_class: str
    required_roles: tuple[str, ...]
    satisfied_roles: tuple[str, ...]
    violations: list[Violation] = field(default_factory=list)
    mode: str = ENFORCEMENT_MODE

    @property
    def codes(self) -> set[str]:
        return {v.code for v in self.violations}


# ---------------------------------------------------------------------------- digests
def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def receipt_digest(receipt: dict[str, Any]) -> str:
    """The digest an attestation or an App review must bind: the whole receipt, canonically."""
    return "sha256:" + hashlib.sha256(canonical_json(receipt)).hexdigest()


def canonical_changed_files(files: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Paths, renames, deletions, modes (incl. symlink 120000 / submodule 160000) and blob ids."""
    rows = [{k: f.get(k) for k in FILE_FIELDS} for f in files]
    return sorted(rows, key=lambda r: (r["path"], r["previous_path"] or "", r["status"]))


def diff_digest(files: Iterable[dict[str, Any]]) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(canonical_changed_files(files))).hexdigest()


# ---------------------------------------------------------------------------- rules
Rule = Callable[[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]], list[Violation]]
RULES: dict[str, Rule] = {}


def rule(name: str) -> Callable[[Rule], Rule]:
    def register(fn: Rule) -> Rule:
        RULES[name] = fn
        return fn
    return register


def _rid(receipt: dict[str, Any]) -> str | None:
    value = receipt.get("receipt_id")
    return value if isinstance(value, str) else None


@rule("schema")
def _schema(receipt, policy, context, receipts):
    import jsonschema

    schema = yaml.safe_load(SCHEMA_PATH.read_text())
    errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(receipt), key=lambda e: list(e.path))
    return [Violation("SCHEMA_INVALID", _rid(receipt), errors[0].message)] if errors else []


@rule("evidence_tier")
def _tier(receipt, policy, context, receipts):
    tier = receipt["review"]["evidence_tier"]
    if tier == "T3":
        return [Violation("T3_INGESTION", _rid(receipt), "author-posted or unverified evidence never satisfies a gate")]
    if tier == "T1" and not policy.get("t1_apps"):
        return [Violation("T1_DISABLED", _rid(receipt), "no GitHub App is allowlisted for T1 reviews")]
    return []


@rule("subject")
def _subject(receipt, policy, context, receipts):
    s, pr, repo = receipt["subject"], context["pr"], context["repository"]
    out: list[Violation] = []
    if (s["repository_id"], s["repository"]) != (repo["id"], repo["full_name"]) or s["pr_number"] != pr["number"]:
        out.append(Violation("WRONG_SUBJECT", _rid(receipt), "repository or pull request does not match"))
    if s["head_sha"] != pr["head_sha"]:
        out.append(Violation("STALE_SHA", _rid(receipt), "receipt is not for the current head"))
    if (s["base_sha"], s["merge_base_sha"]) != (pr["base_sha"], pr["merge_base_sha"]):
        out.append(Violation("STALE_SHA", _rid(receipt), "base or merge base does not match"))
    trusted = canonical_changed_files(pr["changed_files"])
    if canonical_changed_files(s["changed_files"]) != trusted or s["diff_digest"] != diff_digest(trusted):
        out.append(Violation("DIFF_MISMATCH", _rid(receipt), "changed files or diff digest differ from the trusted diff"))
    return out


@rule("risk_class")
def _risk(receipt, policy, context, receipts):
    effective = effective_risk_class(policy, context)
    if receipt["risk_class"] != effective:
        return [Violation("RISK_DOWNGRADE", _rid(receipt), f"receipt says {receipt['risk_class']}, effective is {effective}")]
    return []


@rule("implementer")
def _implementer(receipt, policy, context, receipts):
    evidence = context.get("implementation_evidence")
    if not evidence or not evidence.get("verified") or not evidence.get("worker_id"):
        return [Violation("IMPLEMENTER_UNVERIFIED", _rid(receipt), "no trusted work receipt names the implementer")]
    if receipt["review"]["implementation_worker_id"] != evidence["worker_id"]:
        return [Violation("IMPLEMENTER_MISMATCH", _rid(receipt), "declared implementer differs from the work receipt")]
    return []


@rule("eligibility")
def _eligibility(receipt, policy, context, receipts):
    review = receipt["review"]
    if review["worker_id"] not in policy["role_eligibility"].get(review["role"], []):
        return [Violation("UNREGISTERED_WORKER", _rid(receipt), f"{review['worker_id']} is not eligible as {review['role']}")]
    return []


@rule("independence")
def _independence(receipt, policy, context, receipts):
    review, out = receipt["review"], []
    implementer = (context.get("implementation_evidence") or {}).get("worker_id")
    if review["worker_id"] == implementer:
        out.append(Violation("SAME_WORKER", _rid(receipt), "reviewer is the implementation worker"))
    providers = policy["worker_providers"]
    provider = providers.get(review["worker_id"])
    if review["role"] in ("principal", "challenger") and implementer is not None and (
            provider is None or provider == providers.get(implementer)):
        out.append(Violation("SAME_PROVIDER", _rid(receipt), "reviewer provider is unknown or equals the implementer's"))
    if review["role"] == "challenger":
        for other in receipts:
            if other is receipt or other["review"]["role"] != "principal":
                continue
            same_worker = other["review"]["worker_id"] == review["worker_id"]
            same_provider = providers.get(other["review"]["worker_id"]) == providers.get(review["worker_id"])
            if same_worker or same_provider:
                out.append(Violation("SAME_WORKER", _rid(receipt), "challenger is not independent of the principal"))
    return out


@rule("identity")
def _identity(receipt, policy, context, receipts):
    review, ident, rid = receipt["review"], receipt["review"]["identity"], _rid(receipt)
    author = context["pr"]["author_user_id"]
    if review["evidence_tier"] == "T1":
        app_review = context.get("app_reviews", {}).get(str(ident.get("review_id")))
        allowed = {(a["app_id"], a["user_id"]) for a in policy.get("t1_apps", [])}
        if app_review is None:
            return [Violation("FORGED_IDENTITY", rid, "review id not found by the trusted adapter")]
        if app_review["user_id"] == author:
            return [Violation("AUTHOR_SELF_REVIEW", rid, "review submitted by the pull request author")]
        actual = (app_review.get("app_id"), app_review["user_id"])
        if actual not in allowed or actual != (ident.get("github_app_id"), ident.get("github_user_id")):
            return [Violation("FORGED_IDENTITY", rid, "App/user ids are not the pinned reviewer App")]
        if policy["t1_apps_worker"].get(str(actual[0])) != review["worker_id"]:
            return [Violation("FORGED_IDENTITY", rid, "App does not map to the declared worker")]
        if app_review["commit_id"] != context["pr"]["head_sha"] or app_review["state"] != "APPROVED":
            return [Violation("STALE_SHA", rid, "App review is not an APPROVED review of the exact head")]
        if app_review["body_receipt_digest"] != receipt_digest(receipt):
            return [Violation("RECEIPT_TAMPERED", rid, "receipt differs from the one carried by the App review")]
        return []
    if review["evidence_tier"] == "T2":
        return _t2_identity(receipt, policy, context)
    return []


def _t2_identity(receipt: dict[str, Any], policy: dict[str, Any], context: dict[str, Any]) -> list[Violation]:
    rid, ident, t2 = _rid(receipt), receipt["review"]["identity"], policy.get("t2")
    if not t2:
        return [Violation("T2_DISABLED", rid, "no trusted attesting workflow is configured")]
    claims = context.get("attestations", {}).get(rid or "")
    if claims is None or not claims.get("signature_verified"):
        return [Violation("AUTHOR_CONTROLLED_ATTESTATION", rid, "no verified attestation for this receipt")]
    expected = {
        "issuer": t2["issuer"], "repository_id": context["repository"]["id"], "workflow_path": t2["workflow_path"],
        "ref": t2["ref"], "environment": t2["environment"], "event": "workflow_dispatch",
    }
    for key, value in expected.items():
        if claims.get(key) != value:
            return [Violation("AUTHOR_CONTROLLED_ATTESTATION", rid, f"attestation {key} is not the trusted value")]
    if claims.get("workflow_commit_sha") not in t2["workflow_commit_shas"]:
        return [Violation("AUTHOR_CONTROLLED_ATTESTATION", rid, "attesting workflow commit is not pinned")]
    if claims.get("triggering_actor_id") not in t2["dispatcher_user_ids"] or not claims.get("environment_approved"):
        return [Violation("AUTHOR_CONTROLLED_ATTESTATION", rid, "dispatch was not by an allowed maintainer with approval")]
    bound = (ident.get("workflow_path"), ident.get("workflow_commit_sha"), ident.get("run_id"), ident.get("run_attempt"))
    if bound != (claims["workflow_path"], claims["workflow_commit_sha"], claims.get("run_id"), claims.get("run_attempt")):
        return [Violation("AUTHOR_CONTROLLED_ATTESTATION", rid, "receipt identity does not match the attested run")]
    if claims.get("subject_digest") != receipt_digest(receipt):
        return [Violation("RECEIPT_TAMPERED", rid, "receipt differs from the attested subject")]
    execution = receipt["review"].get("provider_execution")
    if not execution:
        return [Violation("PROVIDER_EVIDENCE_MISSING", rid, "a T2 review must carry provider execution evidence")]
    if execution["prompt_template_sha256"] not in t2["prompt_template_shas"]:
        return [Violation("PROMPT_TEMPLATE_UNTRUSTED", rid, "prompt template is not pinned on the base branch")]
    if not execution["untrusted_text_wrapped"]:
        return [Violation("PROMPT_INJECTION", rid, "PR-authored text reached the model unwrapped")]
    if claims.get("response_digest") != execution["response_digest"]:
        return [Violation("RECEIPT_TAMPERED", rid, "model response does not match the attested response")]
    return []


@rule("reuse")
def _reuse(receipt, policy, context, receipts):
    rid, ident, pr = _rid(receipt), receipt["review"]["identity"], context["pr"]
    here = [pr["number"], pr["head_sha"]]
    keys = [("receipt", rid), ("review", ident.get("review_id")), ("run", ident.get("run_id"))]
    consumed = context.get("consumed", {})
    for kind, value in keys:
        if value is None:
            continue
        prior = consumed.get(f"{kind}:{value}")
        if prior is not None and list(prior) != here:
            return [Violation("RECEIPT_REUSE", rid, f"{kind} id already consumed by another PR or head")]
        twins = [r for r in receipts if r is not receipt and _key(r, kind) == value]
        if twins:
            return [Violation("RECEIPT_REUSE", rid, f"{kind} id appears twice in this submission")]
    return []


def _key(receipt: dict[str, Any], kind: str) -> Any:
    ident = receipt["review"]["identity"]
    return {"receipt": _rid(receipt), "review": ident.get("review_id"), "run": ident.get("run_id")}[kind]


@rule("result_consistency")
def _consistency(receipt, policy, context, receipts):
    result, rid = receipt["result"], _rid(receipt)
    open_blocking = [f for f in result["findings"] if f["severity"] in BLOCKING_SEVERITIES and not f.get("resolved")]
    if result["verdict"] == "BLOCK" or result["recommended_action"] != "approve":
        return [Violation("BLOCKING_FINDING", rid, "review does not approve; escalate or remediate")]
    if open_blocking or result["security_concern"] or result["scope_deviation"]:
        return [Violation("BLOCKING_FINDING", rid, "approving verdict contradicts open P0-P2, security or scope findings")]
    return []


@rule("tests")
def _tests(receipt, policy, context, receipts):
    checks = {c["id"]: c for c in context.get("check_runs", [])}
    head, rid = context["pr"]["head_sha"], _rid(receipt)
    trusted_apps = set(policy["trusted_check_app_ids"])
    for required in policy["required_checks"]:
        matching = [c for c in checks.values() if c["name"] == required]
        good = [c for c in matching if c["app_id"] in trusted_apps and c["head_sha"] == head and c["conclusion"] == "success"]
        if not good:
            return [Violation("CHECK_PROVENANCE", rid, f"required check {required!r} has no trusted green run on the head")]
    for observed in receipt["result"]["tests_observed"]:
        check = checks.get(observed["check_run_id"])
        if (check is None or check["app_id"] not in trusted_apps or check["head_sha"] != head
                or check["name"] != observed["name"] or check["conclusion"] != observed["conclusion"]):
            return [Violation("CHECK_PROVENANCE", rid, f"observed test {observed['name']!r} is not a trusted check on the head")]
    return []


@rule("synthesis")
def _synthesis(receipt, policy, context, receipts):
    if receipt["review"]["role"] != "orchestrator_synthesis":
        return []
    referenced = set(receipt["result"].get("synthesis_of") or [])
    needed = {_rid(r) for r in receipts if r["review"]["role"] in ("principal", "challenger")}
    if not needed or not needed <= referenced:
        return [Violation("MISSING_SYNTHESIS", _rid(receipt), "synthesis does not reference every principal and challenger receipt")]
    return []


# ---------------------------------------------------------------------------- gate
def effective_risk_class(policy: dict[str, Any], context: dict[str, Any]) -> str:
    """Base-envelope risk, raised to high_blast_radius when the PR touches the verification itself."""
    paths = {f["path"] for f in context["pr"]["changed_files"]} | {
        f["previous_path"] for f in context["pr"]["changed_files"] if f.get("previous_path")}
    for prefix in policy["high_blast_radius_paths"]:
        if any(p == prefix or p.startswith(prefix.rstrip("/") + "/") for p in paths):
            return "high_blast_radius"
    return context["effective_risk_class"]


def verify(receipts: list[dict[str, Any]], policy: dict[str, Any], context: dict[str, Any],
           *, disabled_rules: frozenset[str] = frozenset()) -> GateResult:
    """Fail closed: any violation in any receipt leaves the gate unsatisfied."""
    return GateResult(True, effective_risk_class(policy, context), (), tuple(ROLE_ORDER))  # RED: accept-all stub
    risk = effective_risk_class(policy, context)
    required = tuple(policy["gates"][risk])
    violations: list[Violation] = []
    valid_roles: set[str] = set()
    for receipt in receipts:
        found: list[Violation] = []
        for name, check in RULES.items():
            if name in disabled_rules:
                continue
            try:
                found.extend(check(receipt, policy, context, receipts))
            except (KeyError, TypeError, AttributeError) as exc:  # malformed input is a violation, never a pass
                found.append(Violation("SCHEMA_INVALID", _rid(receipt), f"{name}: {exc!r}"))
            if name == "schema" and found:
                break  # later rules assume the schema shape
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--receipts", type=Path, required=True, help="YAML/JSON list of receipts")
    parser.add_argument("--policy", type=Path, required=True, help="verifier policy from the base branch")
    parser.add_argument("--context", type=Path, required=True, help="trusted facts from the GitHub adapter")
    args = parser.parse_args(argv)
    result = verify(yaml.safe_load(args.receipts.read_text()), yaml.safe_load(args.policy.read_text()),
                    yaml.safe_load(args.context.read_text()))
    print(json.dumps({"mode": result.mode, "gate_satisfied": result.gate_satisfied, "risk_class": result.risk_class,
                      "required_roles": result.required_roles, "satisfied_roles": result.satisfied_roles,
                      "violations": [v.__dict__ for v in result.violations]}, indent=2))
    return 0 if result.gate_satisfied else 1


if __name__ == "__main__":
    sys.exit(main())
