"""DEV-14 PR-D: issue a canonical review-gate authorization from verified Option-B evidence.

This module is deliberately narrower than a merge controller. It may certify that the
review evidence gate is satisfied for one exact PR/head, but every authorization it emits
contains authorizes_merge=false. Human merge authority remains separate.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Any

from scripts.development.review_attestation.github_context_adapter import (
    EvidenceIncomplete,
    ImplementationVerifier,
    build_trusted_context,
    canonical_inputs_digest,
    canonical_json,
)

RISK_CLASSES = (
    "trivial",
    "normal",
    "material",
    "architecture",
    "security",
    "high_blast_radius",
)
ROLE_ORDER = ("principal", "challenger", "orchestrator_synthesis")
REVIEW_POLICY_RANK = {"optional": 0, "independent_principal": 1, "principal_and_challenger": 2}


class AuthorizationError(ValueError):
    """Trusted evidence cannot issue a review-gate authorization."""


def _fail(message: str) -> None:
    raise AuthorizationError(message)


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value)).hexdigest()


def _load_verifier(repo_root: Path):
    path = repo_root / "scripts" / "development" / "verify_review_receipts.py"
    spec = importlib.util.spec_from_file_location("c2pro_review_authorization_verifier", path)
    if spec is None or spec.loader is None:
        raise AuthorizationError("cannot load protected review verifier")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    if not callable(getattr(module, "verify", None)):
        raise AuthorizationError("protected review verifier exposes no verify()")
    return module, path


def _required_roles(review_policy: dict[str, Any], risk: str) -> list[str]:
    classes = review_policy.get("risk_classes")
    if (
        review_policy.get("schema") != "c2pro-review-policy-v1"
        or review_policy.get("status") != "canonical"
        or not isinstance(classes, dict)
        or set(classes) != set(RISK_CLASSES)
    ):
        _fail("canonical review policy is malformed or incomplete")
    cfg = classes.get(risk)
    if not isinstance(cfg, dict):
        _fail(f"canonical review policy has no risk class {risk!r}")
    principal = cfg.get("independent_principal_review")
    challenger = cfg.get("challenger")
    synthesis = cfg.get("orchestrator_synthesis")
    if principal not in {"optional", "required"}:
        _fail(f"invalid principal policy for {risk}")
    if challenger not in {False, "optional", "required"}:
        _fail(f"invalid challenger policy for {risk}")
    if type(synthesis) is not bool:
        _fail(f"invalid synthesis policy for {risk}")
    roles: list[str] = []
    if principal == "required":
        roles.append("principal")
    if challenger == "required":
        roles.append("challenger")
    if synthesis:
        roles.append("orchestrator_synthesis")
    return roles


def _canonical_worker_sets(routing: dict[str, Any]) -> dict[str, set[str]]:
    if routing.get("schema") != "c2pro-routing-v2" or routing.get("status") != "canonical_role_authority":
        _fail("canonical routing is malformed or non-canonical")
    workers = routing.get("workers")
    gate = routing.get("principal_gate")
    if not isinstance(workers, dict) or not isinstance(gate, dict):
        _fail("canonical routing worker/gate mappings are missing")
    principal_gate = gate.get("eligible_workers")
    if not isinstance(principal_gate, list) or any(not isinstance(w, str) for w in principal_gate):
        _fail("canonical principal eligibility is malformed")

    principals: set[str] = set()
    challengers: set[str] = set()
    orchestrators: set[str] = set()
    for worker_id, worker in workers.items():
        if not isinstance(worker_id, str) or not isinstance(worker, dict):
            _fail("canonical routing contains malformed worker")
        roles = worker.get("eligible_roles")
        if not isinstance(roles, list) or any(not isinstance(role, str) for role in roles):
            _fail(f"canonical routing roles are malformed for {worker_id}")
        if (
            worker_id in principal_gate
            and worker.get("principal_gate_eligible") is True
            and "independent_reviewer" in roles
        ):
            principals.add(worker_id)
        if "specialist" in roles or "security" in roles:
            challengers.add(worker_id)
        if (
            worker_id in principal_gate
            and worker.get("principal_gate_eligible") is True
            and "orchestrator" in roles
        ):
            orchestrators.add(worker_id)
    return {
        "principal": principals,
        "challenger": challengers,
        "orchestrator_synthesis": orchestrators,
    }


def derive_verifier_policy(
    attestation_policy: dict[str, Any],
    canonical_review_policy: dict[str, Any],
    canonical_routing: dict[str, Any],
) -> dict[str, Any]:
    """Combine protected trust roots with canonical gate/routing authority.

    The attestation policy gate map is intentionally ignored: it can never weaken
    the canonical review policy.
    """
    if not isinstance(attestation_policy, dict):
        _fail("attestation trust policy must be a mapping")
    qualified = attestation_policy.get("role_eligibility")
    providers = attestation_policy.get("worker_providers")
    if not isinstance(qualified, dict) or not isinstance(providers, dict):
        _fail("attestation trust policy lacks qualified workers/providers")

    canonical_sets = _canonical_worker_sets(canonical_routing)
    role_eligibility: dict[str, list[str]] = {}
    for role in ROLE_ORDER:
        configured = qualified.get(role, [])
        if not isinstance(configured, list) or any(not isinstance(w, str) for w in configured):
            _fail(f"attestation role eligibility is malformed for {role}")
        role_eligibility[role] = sorted(set(configured) & canonical_sets[role])

    gates = {risk: _required_roles(canonical_review_policy, risk) for risk in RISK_CLASSES}
    for risk in ("architecture", "security", "high_blast_radius"):
        if set(gates[risk]) != set(ROLE_ORDER):
            _fail(f"canonical {risk} policy does not require the full review set")

    required_keys = ("t1_apps", "t1_apps_worker", "t2", "high_blast_radius_paths", "required_checks")
    if any(key not in attestation_policy for key in required_keys):
        _fail("attestation trust policy is incomplete")

    used_workers = set().union(*[set(values) for values in role_eligibility.values()])
    if any(not isinstance(providers.get(worker), str) or not providers[worker] for worker in used_workers):
        _fail("qualified review worker has no protected provider identity")

    return {
        "t1_apps": copy.deepcopy(attestation_policy["t1_apps"]),
        "t1_apps_worker": copy.deepcopy(attestation_policy["t1_apps_worker"]),
        "t2": copy.deepcopy(attestation_policy["t2"]),
        "role_eligibility": role_eligibility,
        "worker_providers": copy.deepcopy(providers),
        "gates": gates,
        "high_blast_radius_paths": copy.deepcopy(attestation_policy["high_blast_radius_paths"]),
        "required_checks": copy.deepcopy(attestation_policy["required_checks"]),
    }


def _validate_work_envelope(
    work: dict[str, Any],
    canonical_review_policy: dict[str, Any],
    canonical_routing: dict[str, Any],
) -> None:
    if (
        not isinstance(work, dict)
        or work.get("schema") != "c2pro-work-envelope-v1"
        or work.get("schema_version") != 1
    ):
        _fail("canonical work envelope is malformed")
    work_id = work.get("work_id")
    role = work.get("role")
    risk = work.get("risk_class")
    declared_review = work.get("review_policy")
    if not isinstance(work_id, str) or not work_id.startswith("C2PRO-DEV-"):
        _fail("canonical work envelope has invalid work_id")
    if not isinstance(role, str) or not role:
        _fail("canonical work envelope has invalid role")
    if risk not in RISK_CLASSES:
        _fail("canonical work envelope has invalid risk_class")
    if declared_review not in REVIEW_POLICY_RANK:
        _fail("canonical work envelope has invalid review_policy")

    required = _required_roles(canonical_review_policy, risk)
    minimum = (
        "principal_and_challenger"
        if "challenger" in required
        else "independent_principal"
        if "principal" in required
        else "optional"
    )
    if REVIEW_POLICY_RANK[declared_review] < REVIEW_POLICY_RANK[minimum]:
        _fail("canonical work envelope weakens the review policy required by risk")
    if not isinstance(canonical_routing.get("workers"), dict):
        _fail("canonical routing workers are malformed")


def _validate_implementer(
    context: dict[str, Any],
    work: dict[str, Any],
    routing: dict[str, Any],
    derived_policy: dict[str, Any],
) -> dict[str, Any]:
    evidence = context.get("implementation_evidence")
    if not isinstance(evidence, dict) or evidence.get("verified") is not True:
        _fail("no trusted implementation evidence")
    if evidence.get("work_id") != work.get("work_id"):
        _fail("trusted implementation evidence is for another work item")
    worker_id = evidence.get("worker_id")
    worker = routing.get("workers", {}).get(worker_id)
    if not isinstance(worker_id, str) or not isinstance(worker, dict):
        _fail("trusted implementation worker is not registered in canonical routing")
    eligible_roles = worker.get("eligible_roles")
    if not isinstance(eligible_roles, list) or work.get("role") not in eligible_roles:
        _fail("trusted implementation worker is not eligible for the canonical work role")
    provider = derived_policy.get("worker_providers", {}).get(worker_id)
    if not isinstance(provider, str) or not provider:
        _fail("trusted implementation worker has no protected provider identity")
    ref = evidence.get("evidence_ref")
    if not isinstance(ref, str) or not ref:
        _fail("trusted implementation evidence has no immutable reference")
    return {"worker_id": worker_id, "provider": provider, "evidence_ref": ref}


def issue_review_authorization(
    snapshot: dict[str, Any],
    receipts: Any,
    attestation_policy: dict[str, Any],
    canonical_review_policy: dict[str, Any],
    canonical_routing: dict[str, Any],
    work_envelope: dict[str, Any],
    *,
    implementation_verifier: ImplementationVerifier,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Issue review-gate evidence for one exact subject, never merge authority."""
    if not callable(implementation_verifier):
        _fail("review authorization requires a trusted implementation verifier")
    _validate_work_envelope(work_envelope, canonical_review_policy, canonical_routing)

    trusted_snapshot = copy.deepcopy(snapshot)
    trusted_snapshot["effective_risk_class"] = work_envelope["risk_class"]
    try:
        context = build_trusted_context(
            trusted_snapshot,
            implementation_verifier=implementation_verifier,
        )
    except EvidenceIncomplete as exc:
        raise AuthorizationError(f"trusted context incomplete: {exc}") from exc

    derived_policy = derive_verifier_policy(attestation_policy, canonical_review_policy, canonical_routing)
    implementation = _validate_implementer(context, work_envelope, canonical_routing, derived_policy)

    root = repo_root or Path(__file__).resolve().parents[3]
    verifier, verifier_path = _load_verifier(root)
    result = verifier.verify(receipts, derived_policy, context)
    if result.authorizes_merge is not False:
        _fail("review verifier attempted to authorize a merge")
    if not result.gate_satisfied or result.violations:
        codes = sorted({violation.code for violation in result.violations})
        _fail(f"review evidence gate is not satisfied: {codes}")

    expected_roles = _required_roles(canonical_review_policy, result.risk_class)
    if list(result.required_roles) != expected_roles:
        _fail("derived verifier gate diverges from canonical review policy")
    if not isinstance(receipts, list) or not receipts:
        _fail("satisfied non-trivial gate has no review receipts")

    accepted: list[dict[str, Any]] = []
    for receipt in sorted(receipts, key=lambda row: row["receipt_id"]):
        review = receipt["review"]
        worker_id = review["worker_id"]
        accepted.append(
            {
                "receipt_id": receipt["receipt_id"],
                "digest": verifier.receipt_digest(receipt),
                "role": review["role"],
                "worker_id": worker_id,
                "provider": derived_policy["worker_providers"][worker_id],
                "evidence_tier": review["evidence_tier"],
            }
        )

    subject = {
        "repository_id": context["repository"]["id"],
        "repository": context["repository"]["full_name"],
        "pr_number": context["pr"]["number"],
        "head_sha": context["pr"]["head_sha"],
        "base_sha": context["pr"]["base_sha"],
        "merge_base_sha": context["pr"]["merge_base_sha"],
        "diff_digest": verifier.diff_digest(context["pr"]["changed_files"]),
    }
    return {
        "schema": "c2pro-review-authorization-v1",
        "schema_version": 1,
        "work_id": work_envelope["work_id"],
        "subject": subject,
        "implementation": implementation,
        "risk_class": result.risk_class,
        "required_roles": list(result.required_roles),
        "satisfied_roles": list(result.satisfied_roles),
        "accepted_receipts": accepted,
        "context_digest": canonical_inputs_digest(context),
        "policy_provenance": {
            "canonical_review_policy_digest": _digest(canonical_review_policy),
            "canonical_routing_digest": _digest(canonical_routing),
            "attestation_trust_policy_digest": _digest(attestation_policy),
            "work_envelope_digest": _digest(work_envelope),
            "verifier_sha256": hashlib.sha256(verifier_path.read_bytes()).hexdigest(),
        },
        "gate_satisfied": True,
        "authorizes_merge": False,
    }
