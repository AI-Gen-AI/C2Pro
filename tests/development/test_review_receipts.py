"""#1009 PR-A: offline review-receipt verifier (AUDIT_ONLY). Synthetic data only; no network.

Behavioural RED: every negative case below is ACCEPTED by an accept-all verifier, so each test
fails until its rule exists. Tamper tests mutate every bound field of a valid receipt; the
ablation test switches each rule off in turn and proves some case then slips through.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml
from review_receipt_builders import (
    AUTHOR_ID,
    CHECK_APP,
    CODEX_APP,
    CODEX_BOT,
    HEAD,
    architecture_case,
    normal_case,
    reattest,
    vr,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "review_receipts"
VERIFIER = Path(__file__).resolve().parents[2] / "scripts" / "development" / "verify_review_receipts.py"


def codes(receipts: list[dict[str, Any]], policy: dict[str, Any], ctx: dict[str, Any]) -> set[str]:
    result = vr.verify(receipts, policy, ctx)
    assert result.mode == "AUDIT_ONLY"
    return result.codes


def assert_rejected(code: str, receipts: list[dict[str, Any]], policy: dict[str, Any], ctx: dict[str, Any]) -> None:
    result = vr.verify(receipts, policy, ctx)
    assert not result.gate_satisfied, f"expected {code}, gate was satisfied"
    assert code in result.codes, result.violations


# ============================================================================ positive
def test_valid_normal_principal_satisfies_the_normal_gate() -> None:
    result = vr.verify(*normal_case())
    assert result.gate_satisfied, result.violations
    assert result.satisfied_roles == ("principal",)


def test_valid_architecture_set_satisfies_principal_challenger_and_synthesis() -> None:
    result = vr.verify(*architecture_case())
    assert result.gate_satisfied, result.violations
    assert result.satisfied_roles == ("principal", "challenger", "orchestrator_synthesis")


@pytest.mark.parametrize("name", ["normal", "architecture"])
def test_static_synthetic_fixtures_verify_and_match_the_schema(name: str) -> None:
    case = yaml.safe_load((FIXTURES / f"{name}.yaml").read_text())
    receipts, policy, context = normal_case() if name == "normal" else architecture_case()
    assert case == {"receipts": receipts, "policy": policy, "context": context}
    result = vr.verify(case["receipts"], case["policy"], case["context"])
    assert result.gate_satisfied, result.violations
    assert case["context"]["repository"]["full_name"] == "example-org/synthetic-repo"  # never a real repository


def test_t1_app_review_is_accepted_only_as_an_approved_review_of_the_exact_head() -> None:
    receipts, policy, ctx = normal_case()
    receipts[0] = __import__("review_receipt_builders").receipt(1, "principal", "codex", tier="T1")
    reattest(receipts, ctx)
    assert vr.verify(receipts, policy, ctx).gate_satisfied


# ============================================================================ negative cases (plan items 1-14)
def test_01_forged_identity_wrong_numeric_ids() -> None:
    receipts, policy, ctx = normal_case()
    receipts[0] = __import__("review_receipt_builders").receipt(1, "principal", "codex", tier="T1")
    reattest(receipts, ctx)
    ctx["app_reviews"][str(receipts[0]["review"]["identity"]["review_id"])]["user_id"] = CODEX_BOT + 1  # look-alike
    assert_rejected("FORGED_IDENTITY", receipts, policy, ctx)


def test_02_author_self_review() -> None:
    receipts, policy, ctx = normal_case()
    receipts[0] = __import__("review_receipt_builders").receipt(1, "principal", "codex", tier="T1")
    reattest(receipts, ctx)
    ctx["app_reviews"][str(receipts[0]["review"]["identity"]["review_id"])]["user_id"] = AUTHOR_ID
    assert_rejected("AUTHOR_SELF_REVIEW", receipts, policy, ctx)


def test_03_same_worker_as_implementer() -> None:
    receipts, policy, ctx = normal_case()
    receipts[0]["review"]["worker_id"] = "claude_code"  # implementer reviewing itself
    reattest(receipts, ctx)
    assert_rejected("SAME_WORKER", receipts, policy, ctx)


def test_03b_challenger_equal_to_principal_provider() -> None:
    receipts, policy, ctx = architecture_case()
    receipts[1]["review"]["worker_id"] = "codex"  # challenger == principal
    reattest(receipts, ctx)
    assert_rejected("SAME_WORKER", receipts, policy, ctx)


def test_03c_same_provider_as_implementer_is_not_independent() -> None:
    receipts, policy, ctx = normal_case()
    policy["worker_providers"]["codex"] = "anthropic"  # different worker id, same provider/control plane
    assert_rejected("SAME_PROVIDER", receipts, policy, ctx)


def test_04_stale_head_after_a_new_push() -> None:
    receipts, policy, ctx = normal_case()
    ctx["pr"]["head_sha"] = "9" * 40
    ctx["check_runs"][0]["head_sha"] = "9" * 40
    assert_rejected("STALE_SHA", receipts, policy, ctx)


def test_04b_wrong_merge_base() -> None:
    receipts, policy, ctx = normal_case()
    ctx["pr"]["merge_base_sha"] = "8" * 40
    assert_rejected("STALE_SHA", receipts, policy, ctx)


@pytest.mark.parametrize("mutate", [
    lambda files: files.pop(),                                      # omitted deletion
    lambda files: files[0].update(blob_sha="7" * 40),               # wrong blob
    lambda files: files[1].update(previous_path=None, status="added"),  # rename hidden as add
    lambda files: files[2].update(mode="100644"),                   # symlink hidden as file
    lambda files: files.append({"path": ".c2pro/control/review-policy.yaml", "previous_path": None,
                                "status": "modified", "mode": "100644", "blob_sha": "6" * 40}),
])
def test_05_diff_mismatch(mutate: Any) -> None:
    receipts, policy, ctx = normal_case()
    mutate(ctx["pr"]["changed_files"])  # the trusted diff changed; the receipt describes something else
    assert "DIFF_MISMATCH" in codes(receipts, policy, ctx)


def test_05b_receipt_digest_alone_cannot_vouch_for_a_forged_file_list() -> None:
    receipts, policy, ctx = normal_case()
    receipts[0]["subject"]["changed_files"].pop()
    receipts[0]["subject"]["diff_digest"] = vr.diff_digest(receipts[0]["subject"]["changed_files"])
    reattest(receipts, ctx)
    assert_rejected("DIFF_MISMATCH", receipts, policy, ctx)


def test_06_receipt_reuse_on_another_pr_or_head() -> None:
    receipts, policy, ctx = normal_case()
    ctx["consumed"] = {f"receipt:{receipts[0]['receipt_id']}": [99, HEAD]}
    assert_rejected("RECEIPT_REUSE", receipts, policy, ctx)


def test_06b_duplicate_run_in_one_submission() -> None:
    receipts, policy, ctx = architecture_case()
    receipts[1]["review"]["identity"]["run_id"] = receipts[0]["review"]["identity"]["run_id"]
    reattest(receipts, ctx)
    assert "RECEIPT_REUSE" in codes(receipts, policy, ctx)


def test_07_missing_challenger_for_architecture() -> None:
    receipts, policy, ctx = architecture_case()
    receipts = [receipts[0], receipts[2]]
    receipts[1]["result"]["synthesis_of"] = [receipts[0]["receipt_id"]]
    reattest(receipts, ctx)
    assert_rejected("MISSING_CHALLENGER", receipts, policy, ctx)


def test_07b_missing_or_partial_synthesis() -> None:
    receipts, policy, ctx = architecture_case()
    assert_rejected("MISSING_SYNTHESIS", receipts[:2], policy, ctx)
    receipts[2]["result"]["synthesis_of"] = [receipts[0]["receipt_id"]]  # ignores the challenger
    reattest(receipts, ctx)
    assert_rejected("MISSING_SYNTHESIS", receipts, policy, ctx)


@pytest.mark.parametrize("field,value", [
    ("signature_verified", False), ("ref", "refs/heads/feature"), ("workflow_path", ".github/workflows/pr.yml"),
    ("workflow_commit_sha", "5" * 40), ("event", "pull_request"), ("repository_id", 2),
    ("triggering_actor_id", AUTHOR_ID + 77), ("environment_approved", False), ("issuer", "https://evil.example"),
])
def test_08_author_controlled_or_unpinned_attestation(field: str, value: Any) -> None:
    receipts, policy, ctx = normal_case()
    ctx["attestations"][receipts[0]["receipt_id"]][field] = value
    assert_rejected("AUTHOR_CONTROLLED_ATTESTATION", receipts, policy, ctx)


def test_09_pr_touching_the_verifier_is_high_blast_radius_and_needs_the_full_set() -> None:
    receipts, policy, ctx = normal_case()
    touched = {"path": "scripts/development/verify_review_receipts.py", "previous_path": None, "status": "modified",
               "mode": "100644", "blob_sha": "4" * 40}
    ctx["pr"]["changed_files"].append(touched)
    receipts[0]["subject"]["changed_files"].append(dict(touched))
    receipts[0]["subject"]["diff_digest"] = vr.diff_digest(ctx["pr"]["changed_files"])
    reattest(receipts, ctx)
    result = vr.verify(receipts, policy, ctx)
    assert result.risk_class == "high_blast_radius"
    assert not result.gate_satisfied
    assert {"RISK_DOWNGRADE", "MISSING_CHALLENGER", "MISSING_SYNTHESIS"} <= result.codes


def test_10_unregistered_worker() -> None:
    receipts, policy, ctx = normal_case()
    receipts[0]["review"]["worker_id"] = "gpt6_orchestrator"  # synthesis-only worker presented as principal
    reattest(receipts, ctx)
    assert_rejected("UNREGISTERED_WORKER", receipts, policy, ctx)


def test_11_t3_author_posted_receipt_is_never_accepted() -> None:
    receipts, policy, ctx = normal_case()
    receipts[0]["review"]["evidence_tier"] = "T3"
    reattest(receipts, ctx)
    assert_rejected("T3_INGESTION", receipts, policy, ctx)


def test_12_prompt_injection_and_unpinned_prompt() -> None:
    receipts, policy, ctx = normal_case()
    receipts[0]["review"]["provider_execution"]["untrusted_text_wrapped"] = False
    reattest(receipts, ctx)
    assert_rejected("PROMPT_INJECTION", receipts, policy, ctx)
    receipts, policy, ctx = normal_case()
    receipts[0]["review"]["provider_execution"]["prompt_template_sha256"] = "0" * 64
    reattest(receipts, ctx)
    assert_rejected("PROMPT_TEMPLATE_UNTRUSTED", receipts, policy, ctx)


@pytest.mark.parametrize("edit", [
    lambda r: r["result"]["findings"].append({"id": "F2", "severity": "P1", "file": None, "line": None, "summary": "x"}),
    lambda r: r["result"].update(verdict="BLOCK"),
    lambda r: r["result"].update(security_concern=True),
    lambda r: r["result"].update(recommended_action="escalate"),
])
def test_13_blocking_finding_contradicts_approval(edit: Any) -> None:
    receipts, policy, ctx = normal_case()
    edit(receipts[0])
    reattest(receipts, ctx)
    assert_rejected("BLOCKING_FINDING", receipts, policy, ctx)


def test_14_risk_downgrade() -> None:
    receipts, policy, ctx = normal_case()
    ctx["effective_risk_class"] = "architecture"  # base envelope says architecture; receipt says normal
    assert_rejected("RISK_DOWNGRADE", receipts, policy, ctx)


# ============================================================================ adjudication amendments B, C, E
def test_b_missing_implementer_receipt_fails_closed() -> None:
    receipts, policy, ctx = normal_case()
    ctx["implementation_evidence"] = None
    assert_rejected("IMPLEMENTER_UNVERIFIED", receipts, policy, ctx)
    ctx["implementation_evidence"] = {"worker_id": "claude_code", "verified": False}
    assert_rejected("IMPLEMENTER_UNVERIFIED", receipts, policy, ctx)


def test_b_self_declared_implementer_must_match_the_work_receipt() -> None:
    receipts, policy, ctx = normal_case()
    receipts[0]["review"]["implementation_worker_id"] = "antigravity"
    reattest(receipts, ctx)
    assert_rejected("IMPLEMENTER_MISMATCH", receipts, policy, ctx)


def test_c_response_and_receipt_must_match_the_attested_run() -> None:
    receipts, policy, ctx = normal_case()
    ctx["attestations"][receipts[0]["receipt_id"]]["response_digest"] = "sha256:" + "0" * 64
    assert_rejected("RECEIPT_TAMPERED", receipts, policy, ctx)
    receipts, policy, ctx = normal_case()
    ctx["attestations"][receipts[0]["receipt_id"]]["run_attempt"] = 2
    assert_rejected("AUTHOR_CONTROLLED_ATTESTATION", receipts, policy, ctx)


@pytest.mark.parametrize("mutate", [
    lambda c: c.update(app_id=CHECK_APP + 1),       # similarly named check from another App
    lambda c: c.update(head_sha="9" * 40),          # stale check
    lambda c: c.update(conclusion="failure"),
])
def test_e_check_status_provenance(mutate: Any) -> None:
    receipts, policy, ctx = normal_case()
    mutate(ctx["check_runs"][0])
    assert_rejected("CHECK_PROVENANCE", receipts, policy, ctx)


def test_t1_disabled_without_an_allowlisted_app() -> None:
    receipts, policy, ctx = normal_case()
    receipts[0] = __import__("review_receipt_builders").receipt(1, "principal", "codex", tier="T1")
    reattest(receipts, ctx)
    policy["t1_apps"] = []
    assert_rejected("T1_DISABLED", receipts, policy, ctx)
    assert CODEX_APP  # synthetic id only


def test_malformed_receipt_is_a_violation_never_a_pass() -> None:
    receipts, policy, ctx = normal_case()
    del receipts[0]["result"]
    assert_rejected("SCHEMA_INVALID", receipts, policy, ctx)


# ============================================================================ tamper detection (input mutation)
def _paths(node: Any, prefix: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
    if isinstance(node, dict):
        return [p for k, v in node.items() for p in _paths(v, prefix + (k,))]
    if isinstance(node, list):
        return [p for i, v in enumerate(node) for p in _paths(v, prefix + (i,))]
    return [prefix]


def _flip(value: Any) -> Any:
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return value + 1
    if value is None:
        return "tampered"
    return value[:-1] + ("0" if value[-1:] != "0" else "1")


@pytest.mark.parametrize("path", _paths(architecture_case()[0][0]))
def test_tamper_after_attestation_is_detected_for_every_receipt_field(path: tuple[Any, ...]) -> None:
    receipts, policy, ctx = architecture_case()
    node = receipts[0]
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = _flip(node[path[-1]])
    assert not vr.verify(receipts, policy, ctx).gate_satisfied, f"tampering {path} went undetected"


# ============================================================================ rule ablation (verifier mutation)
def _negative_suite() -> list[tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]]:
    """One case per rule. Receipt edits are re-attested so only the targeted rule can catch them."""
    receipt_edits = (
        lambda r: r[0].update(approved_by_owner=True),                       # schema: unknown field
        lambda r: r[0]["review"].update(evidence_tier="T3"),                 # evidence_tier
        lambda r: r[0]["subject"].update(base_sha="9" * 40),                 # subject
        lambda r: [x.update(risk_class="material") for x in r],              # risk_class
        lambda r: r[0]["review"].update(implementation_worker_id="antigravity"),  # implementer
        lambda r: r[0]["review"].update(worker_id="gpt6_orchestrator"),      # eligibility
        lambda r: (r[0]["review"].update(worker_id="claude_code"),           # independence
                   r[0]["review"]["provider_execution"].update(provider="anthropic")),
        lambda r: r[0]["result"].update(security_concern=True),              # result_consistency
        lambda r: r[2]["result"].update(synthesis_of=[]),                    # synthesis
        lambda r: r[0]["result"]["tests_observed"][0].update(check_run_id=999),  # tests
    )
    context_edits = (
        lambda r, c: c["attestations"][r[0]["receipt_id"]].update(ref="refs/heads/x"),  # identity
        lambda r, c: c.update(consumed={f"receipt:{r[0]['receipt_id']}": [99, HEAD]}),  # reuse
    )
    out = []
    for edit in receipt_edits:
        receipts, policy, ctx = architecture_case()
        edit(receipts)
        reattest(receipts, ctx)
        out.append((receipts, policy, ctx))
    for cedit in context_edits:
        receipts, policy, ctx = architecture_case()
        cedit(receipts, ctx)
        out.append((receipts, policy, ctx))
    return out


@pytest.mark.parametrize("rule_name", sorted(vr.RULES))
def test_every_rule_is_load_bearing(rule_name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    if rule_name == "result_consistency":  # the gate-level contradiction check reuses the same function
        monkeypatch.setattr(vr, "_consistency", lambda *args, **kwargs: [])
    for receipts, policy, ctx in _negative_suite():
        assert not vr.verify(copy.deepcopy(receipts), policy, ctx).gate_satisfied
    slipped = [i for i, (receipts, policy, ctx) in enumerate(_negative_suite())
               if vr._verify_with_disabled_rules(copy.deepcopy(receipts), policy, ctx,
                                                 frozenset({rule_name})).gate_satisfied]
    assert slipped, f"disabling rule {rule_name!r} lets no negative case through: the rule is untested"


# ============================================================================ adversarial review round 1 (RED first)
from review_receipt_builders import receipt as _receipt


def _t1_case() -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    receipts, policy, ctx = normal_case()
    receipts[0] = _receipt(1, "principal", "codex", tier="T1")
    reattest(receipts, ctx)
    return receipts, policy, ctx


@pytest.mark.parametrize("field,value", [("commit_id", "9" * 40), ("state", "COMMENTED")])
def test_t1_review_must_be_approved_on_the_exact_head(field: str, value: str) -> None:
    receipts, policy, ctx = _t1_case()
    ctx["app_reviews"][str(receipts[0]["review"]["identity"]["review_id"])][field] = value
    assert_rejected("STALE_SHA", receipts, policy, ctx)


@pytest.mark.parametrize("field,value", [("pr_number", 99), ("repository_id", 2)])
def test_r1_p3_5_t1_review_bound_to_pr_and_repository(field: str, value: int) -> None:
    receipts, policy, ctx = _t1_case()
    ctx["app_reviews"][str(receipts[0]["review"]["identity"]["review_id"])][field] = value
    assert_rejected("WRONG_SUBJECT", receipts, policy, ctx)


def test_r1_p1_1_pr_added_job_with_the_required_name_cannot_stand_in_for_ci() -> None:
    receipts, policy, ctx = normal_case()
    ctx["check_runs"].append({"id": 502, "name": "CI Status", "app_id": CHECK_APP, "head_sha": HEAD,
                              "conclusion": "success", "workflow_path": ".github/workflows/pr-added.yml",
                              "workflow_sha": "f" * 40})
    receipts[0]["result"]["tests_observed"] = [{"name": "CI Status", "check_run_id": 502, "conclusion": "success"}]
    reattest(receipts, ctx)  # real CI stays green: only the receipt-level producer binding can reject this
    assert_rejected("CHECK_PROVENANCE", receipts, policy, ctx)


def test_r1_p1_1_a_later_failed_rerun_wins_over_an_earlier_success() -> None:
    receipts, policy, ctx = normal_case()
    later = dict(ctx["check_runs"][0], id=503, conclusion="failure")
    ctx["check_runs"].append(later)
    assert_rejected("CHECK_PROVENANCE", receipts, policy, ctx)


def test_r1_p1_1_receipt_must_observe_the_required_checks() -> None:
    receipts, policy, ctx = normal_case()
    receipts[0]["result"]["tests_observed"] = []
    reattest(receipts, ctx)
    assert_rejected("CHECK_PROVENANCE", receipts, policy, ctx)


def test_r1_p1_1_any_workflow_change_is_high_blast_radius() -> None:
    receipts, policy, ctx = normal_case()
    row = {"path": ".github/workflows/ci.yml", "previous_path": None, "status": "modified", "mode": "100644",
           "blob_sha": "4" * 40}
    ctx["pr"]["changed_files"].append(row)
    assert vr.verify(receipts, policy, ctx).risk_class == "high_blast_radius"


def test_r1_p1_2_an_omitted_blocking_t2_review_at_the_head_contradicts_the_gate() -> None:
    receipts, policy, ctx = normal_case()
    blocked = _receipt(9, "principal", "codex")
    blocked["result"].update(verdict="BLOCK", recommended_action="remediate")
    ctx["head_reviews"].append({"source": "T2", "receipt_id": blocked["receipt_id"], "receipt": blocked})
    assert_rejected("CONTRADICTING_REVIEW", receipts, policy, ctx)


def test_r1_p1_2_a_changes_requested_app_review_at_the_head_contradicts_the_gate() -> None:
    receipts, policy, ctx = normal_case()
    ctx["head_reviews"].append({"source": "T1", "review_id": 79999, "user_id": CODEX_BOT, "app_id": CODEX_APP,
                                "state": "CHANGES_REQUESTED"})
    assert_rejected("CONTRADICTING_REVIEW", receipts, policy, ctx)


@pytest.mark.parametrize("edit", [
    lambda p, c, rid: (p["t2"]["dispatcher_user_ids"].append(AUTHOR_ID),
                       c["attestations"][rid].update(triggering_actor_id=AUTHOR_ID)),
    lambda p, c, rid: c["attestations"][rid].update(environment_approver_id=c["attestations"][rid]["triggering_actor_id"]),
    lambda p, c, rid: c["attestations"][rid].update(environment_approver_id=AUTHOR_ID),
    lambda p, c, rid: c["attestations"][rid].pop("environment_approver_id"),
])
def test_r1_p2_1_author_dispatch_or_self_approval_is_rejected(edit: Any) -> None:
    receipts, policy, ctx = normal_case()
    edit(policy, ctx, receipts[0]["receipt_id"])
    assert_rejected("AUTHOR_CONTROLLED_ATTESTATION", receipts, policy, ctx)


def test_r1_p2_2_unknown_implementer_provider_fails_closed() -> None:
    receipts, policy, ctx = normal_case()
    ctx["implementation_evidence"]["worker_id"] = "claude_code_v2"
    receipts[0]["review"]["implementation_worker_id"] = "claude_code_v2"
    reattest(receipts, ctx)
    assert_rejected("IMPLEMENTER_PROVIDER_UNKNOWN", receipts, policy, ctx)


def test_r1_p2_3_executed_provider_must_be_the_worker_provider() -> None:
    receipts, policy, ctx = normal_case()
    receipts[0]["review"]["provider_execution"]["provider"] = "anthropic"
    reattest(receipts, ctx)
    assert_rejected("PROVIDER_MISMATCH", receipts, policy, ctx)


@pytest.mark.parametrize("field", ["provider", "model", "request_ids_digest"])
def test_r1_p2_3_execution_must_match_the_attested_execution(field: str) -> None:
    receipts, policy, ctx = normal_case()
    ctx["attestations"][receipts[0]["receipt_id"]][field] = "tampered"
    assert_rejected("PROVIDER_MISMATCH", receipts, policy, ctx)


@pytest.mark.parametrize("edit", [
    lambda r: r["result"].update(architecture_drift=True),
    lambda r: r["result"]["findings"].append({"id": "F9", "severity": "P0", "file": None, "line": None,
                                             "summary": "x", "resolved": True}),
    lambda r: r["result"]["findings"].append(dict(r["result"]["findings"][0])),
])
def test_r1_p2_4_drift_self_resolved_criticals_and_duplicate_findings_block(edit: Any) -> None:
    receipts, policy, ctx = normal_case()
    edit(receipts[0])
    reattest(receipts, ctx)
    assert_rejected("BLOCKING_FINDING", receipts, policy, ctx)


def test_r1_p2_5_blast_radius_escalation_keeps_the_stricter_base_gate() -> None:
    receipts, policy, ctx = normal_case()
    policy["gates"]["high_blast_radius"] = ["principal"]  # a weaker hbr gate must not override security
    ctx["effective_risk_class"] = "security"
    ctx["pr"]["changed_files"].append({"path": ".c2pro/control/routing.yaml", "previous_path": None,
                                       "status": "modified", "mode": "100644", "blob_sha": "4" * 40})
    result = vr.verify(receipts, policy, ctx)
    assert not result.gate_satisfied
    assert {"POLICY_INVALID", "MISSING_CHALLENGER"} & result.codes


def test_r1_p2_6_required_checks_hold_even_without_receipts() -> None:
    _, policy, ctx = normal_case()
    ctx["effective_risk_class"] = "trivial"
    ctx["check_runs"][0]["conclusion"] = "failure"
    assert_rejected("CHECK_PROVENANCE", [], policy, ctx)


@pytest.mark.parametrize("edit", [
    lambda r: r["review"].update(worker_id="codex\n"),
    lambda r: r["subject"].update(pr_number=7.0),
    lambda r: r.update(issued_at="not-a-date"),
])
def test_r1_p3_1_strict_schema_types_and_formats(edit: Any) -> None:
    receipts, policy, ctx = normal_case()
    edit(receipts[0])
    reattest(receipts, ctx)
    assert_rejected("SCHEMA_INVALID", receipts, policy, ctx)


@pytest.mark.parametrize("edit,code", [
    (lambda c, rid: c["implementation_evidence"].update(verified="false"), "IMPLEMENTER_UNVERIFIED"),
    (lambda c, rid: c["attestations"][rid].update(signature_verified="false"), "AUTHOR_CONTROLLED_ATTESTATION"),
    (lambda c, rid: c["attestations"][rid].update(environment_approved="no"), "AUTHOR_CONTROLLED_ATTESTATION"),
    (lambda c, rid: c["pr"].update(changed_files_complete=False), "POLICY_INVALID"),
])
def test_r1_p3_2_truthy_strings_never_stand_in_for_true(edit: Any, code: str) -> None:
    receipts, policy, ctx = normal_case()
    edit(ctx, receipts[0]["receipt_id"])
    assert_rejected(code, receipts, policy, ctx)


@pytest.mark.parametrize("receipts", [[1], "x", None, [None], [{"receipt_id": 5}]])
def test_r1_p3_3_malformed_submissions_fail_closed_without_raising(receipts: Any) -> None:
    _, policy, ctx = normal_case()
    assert not vr.verify(receipts, policy, ctx).gate_satisfied


def test_r1_p3_3_unknown_risk_class_fails_closed_without_raising() -> None:
    receipts, policy, ctx = normal_case()
    ctx["effective_risk_class"] = "unheard-of"
    assert_rejected("POLICY_INVALID", receipts, policy, ctx)


def test_r1_p3_4_exact_protected_directory_path_is_high_blast_radius() -> None:
    receipts, policy, ctx = normal_case()
    ctx["pr"]["changed_files"].append({"path": "scripts/development/review_attestation", "previous_path": None,
                                       "status": "added", "mode": "120000", "blob_sha": "4" * 40})
    assert vr.verify(receipts, policy, ctx).risk_class == "high_blast_radius"


def test_r1_p3_6_duplicate_paths_in_the_trusted_diff_fail_closed() -> None:
    receipts, policy, ctx = normal_case()
    ctx["pr"]["changed_files"].append(dict(ctx["pr"]["changed_files"][0]))
    receipts[0]["subject"]["changed_files"].append(dict(receipts[0]["subject"]["changed_files"][0]))
    receipts[0]["subject"]["diff_digest"] = vr.diff_digest(receipts[0]["subject"]["changed_files"])
    reattest(receipts, ctx)
    assert_rejected("DIFF_MISMATCH", receipts, policy, ctx)


@pytest.mark.parametrize("edit", [
    lambda refs: refs.append({"receipt_id": "00000009-0000-4000-8000-000000000009", "digest": "sha256:" + "0" * 64}),
    lambda refs: refs[0].update(digest="sha256:" + "0" * 64),
])
def test_r1_p3_7_synthesis_binds_exactly_the_reviewed_receipts_by_digest(edit: Any) -> None:
    receipts, policy, ctx = architecture_case()
    edit(receipts[2]["result"]["synthesis_of"])
    for r in receipts:  # re-sign WITHOUT refreshing references, so the edit survives
        ctx["attestations"][r["receipt_id"]]["subject_digest"] = vr.receipt_digest(r)
    assert_rejected("MISSING_SYNTHESIS", receipts, policy, ctx)


# ============================================================================ adversarial review round 2 (RED first)
def test_r2_n2_an_omitted_approving_receipt_with_an_open_p0_contradicts_the_gate() -> None:
    receipts, policy, ctx = normal_case()
    hidden = _receipt(5, "principal", "codex")
    hidden["result"]["findings"].append({"id": "F9", "severity": "P0", "file": None, "line": None, "summary": "x"})
    hidden["result"]["security_concern"] = True
    ctx["head_reviews"].append({"source": "T2", "receipt_id": hidden["receipt_id"], "receipt": hidden})
    assert_rejected("CONTRADICTING_REVIEW", receipts, policy, ctx)


@pytest.mark.parametrize("edit", [lambda c: c.pop("head_reviews"), lambda c: c.update(head_reviews=None),
                                  lambda c: c.update(head_reviews_complete=False)])
def test_r2_n1_missing_or_incomplete_head_reviews_fail_closed(edit: Any) -> None:
    receipts, policy, ctx = normal_case()
    edit(ctx)
    assert_rejected("POLICY_INVALID", receipts, policy, ctx)


@pytest.mark.parametrize("entry", [{"source": "t2", "receipt_id": "x"}, {"source": "T9"}])
def test_r2_n4_unknown_head_review_sources_fail_closed(entry: dict[str, Any]) -> None:
    receipts, policy, ctx = normal_case()
    ctx["head_reviews"].append(entry)
    assert_rejected("CONTRADICTING_REVIEW", receipts, policy, ctx)


def test_r2_n3_a_block_from_a_deregistered_worker_still_contradicts() -> None:
    receipts, policy, ctx = normal_case()
    blocked = _receipt(6, "principal", "retired_worker")
    blocked["result"]["verdict"] = "BLOCK"
    ctx["head_reviews"].append({"source": "T2", "receipt_id": blocked["receipt_id"], "receipt": blocked})
    assert_rejected("CONTRADICTING_REVIEW", receipts, policy, ctx)


def test_r2_n5_a_newer_failed_run_with_an_unpinned_workflow_wins() -> None:
    receipts, policy, ctx = normal_case()
    ctx["check_runs"].append(dict(ctx["check_runs"][0], id=600, conclusion="failure", workflow_sha="0" * 40))
    assert_rejected("CHECK_PROVENANCE", receipts, policy, ctx)


def test_r2_gate_level_check_rejects_a_pr_added_job_even_without_receipts() -> None:
    _, policy, ctx = normal_case()
    ctx["effective_risk_class"] = "trivial"
    ctx["check_runs"] = [dict(ctx["check_runs"][0], id=502, workflow_path=".github/workflows/pr-added.yml",
                              workflow_sha="f" * 40)]
    assert_rejected("CHECK_PROVENANCE", [], policy, ctx)


def test_r2_n11_incomplete_diff_fails_closed_at_gate_level() -> None:
    _, policy, ctx = normal_case()
    ctx["effective_risk_class"] = "trivial"
    del ctx["pr"]["changed_files_complete"]
    assert_rejected("POLICY_INVALID", [], policy, ctx)


def test_r2_n6_environment_approver_must_be_allowlisted() -> None:
    receipts, policy, ctx = normal_case()
    ctx["attestations"][receipts[0]["receipt_id"]]["environment_approver_id"] = 4242
    assert_rejected("AUTHOR_CONTROLLED_ATTESTATION", receipts, policy, ctx)


def test_r2_n7_author_id_must_be_an_integer() -> None:
    receipts, policy, ctx = normal_case()
    ctx["pr"]["author_user_id"] = str(ctx["pr"]["author_user_id"])
    assert_rejected("POLICY_INVALID", receipts, policy, ctx)


@pytest.mark.parametrize("stamp", ["2026-01-01", "20260101T000000"])
def test_r2_n8_issued_at_must_be_strict_rfc3339(stamp: str) -> None:
    receipts, policy, ctx = normal_case()
    receipts[0]["issued_at"] = stamp
    reattest(receipts, ctx)
    assert_rejected("SCHEMA_INVALID", receipts, policy, ctx)


@pytest.mark.parametrize("edit", [lambda p: p["gates"].update(architecture=["principal"], security=["principal"],
                                                                  high_blast_radius=["principal"]),
                                  lambda p: p.update(required_checks=[])])
def test_r2_n9_n10_policy_must_require_synthesis_and_checks(edit: Any) -> None:
    receipts, policy, ctx = normal_case()
    edit(policy)
    assert_rejected("POLICY_INVALID", receipts, policy, ctx)


# ============================================================================ adversarial review round 3 (RED first)
def test_r3_an_omitted_approved_app_review_carrying_an_open_p1_contradicts_the_gate() -> None:
    receipts, policy, ctx = normal_case()
    hidden = _receipt(7, "principal", "codex", tier="T1")
    hidden["result"]["findings"].append({"id": "F9", "severity": "P1", "file": None, "line": None, "summary": "x"})
    ctx["head_reviews"].append({"source": "T1", "review_id": hidden["review"]["identity"]["review_id"],
                                "user_id": CODEX_BOT, "app_id": CODEX_APP, "state": "APPROVED", "receipt": hidden,
                                "body_receipt_digest": vr.receipt_digest(hidden)})
    assert_rejected("CONTRADICTING_REVIEW", receipts, policy, ctx)


@pytest.mark.parametrize("edit", [lambda e: e.pop("receipt"), lambda e: e.update(body_receipt_digest="sha256:" + "0" * 64)])
def test_r3_an_allowlisted_app_review_without_its_verifiable_receipt_contradicts(edit: Any) -> None:
    receipts, policy, ctx = _t1_case()
    edit(ctx["head_reviews"][0])
    assert_rejected("CONTRADICTING_REVIEW", receipts, policy, ctx)


# ============================================================================ independent review fixes
@pytest.mark.parametrize("edit", [
    lambda c: c.pop("check_runs_complete"),
    lambda c: c.update(check_runs_complete=False),
    lambda c: c.update(check_runs_complete="true"),
    lambda c: c.pop("check_runs"),
    lambda c: c.pop("consumed_complete"),
    lambda c: c.update(consumed_complete=False),
    lambda c: c.update(consumed_complete="true"),
    lambda c: c.pop("consumed"),
])
def test_completeness_flags_are_explicit_true_even_for_a_trivial_empty_gate(edit: Any) -> None:
    _, policy, ctx = normal_case()
    ctx["effective_risk_class"] = "trivial"
    edit(ctx)
    assert_rejected("POLICY_INVALID", [], policy, ctx)


@pytest.mark.parametrize("edit", [
    lambda claims: claims.pop("inputs_digest"),
    lambda claims: claims.update(inputs_digest="true"),
    lambda claims: claims.update(inputs_digest="sha256:" + "0" * 64),
])
def test_t2_provider_inputs_digest_must_match_a_valid_attested_claim(edit: Any) -> None:
    receipts, policy, ctx = normal_case()
    edit(ctx["attestations"][receipts[0]["receipt_id"]])
    assert_rejected("PROVIDER_MISMATCH", receipts, policy, ctx)


@pytest.mark.parametrize("tier,field", [
    ("T1", "github_app_id"),
    ("T1", "github_user_id"),
    ("T1", "review_id"),
    ("T2", "workflow_path"),
    ("T2", "workflow_commit_sha"),
    ("T2", "run_id"),
    ("T2", "run_attempt"),
])
def test_tier_identity_requires_every_binding_field(tier: str, field: str) -> None:
    receipts, policy, ctx = _t1_case() if tier == "T1" else normal_case()
    del receipts[0]["review"]["identity"][field]
    assert_rejected("SCHEMA_INVALID", receipts, policy, ctx)


@pytest.mark.parametrize("field", ["run_id", "run_attempt"])
def test_missing_t2_run_binding_cannot_pass_when_both_sides_are_none(field: str) -> None:
    receipts, policy, ctx = normal_case()
    receipt = receipts[0]
    claims = ctx["attestations"][receipt["receipt_id"]]
    del receipt["review"]["identity"][field]
    claims.pop(field)
    claims["subject_digest"] = vr.receipt_digest(receipt)
    assert_rejected("SCHEMA_INVALID", receipts, policy, ctx)


@pytest.mark.parametrize("bad_value", [True, 1.0, "1"])
@pytest.mark.parametrize("tier,field", [
    ("T1", "github_app_id"),
    ("T1", "github_user_id"),
    ("T1", "review_id"),
    ("T2", "run_id"),
    ("T2", "run_attempt"),
])
def test_tier_identity_ids_are_strict_integers(tier: str, field: str, bad_value: Any) -> None:
    receipts, policy, ctx = _t1_case() if tier == "T1" else normal_case()
    receipts[0]["review"]["identity"][field] = bad_value
    assert_rejected("SCHEMA_INVALID", receipts, policy, ctx)


def test_public_verify_has_no_rule_ablation_argument() -> None:
    receipts, policy, ctx = normal_case()
    with pytest.raises(TypeError):
        vr.verify(receipts, policy, ctx, disabled_rules=frozenset(vr.RULES))


# ============================================================================ #1013 post-merge findings (RED first)
# CX-P1 / CX-P2 are the Codex review threads on merged #1010; C6 is the AUDIT_ONLY exit-code finding.
def _foreign_work(receipts: list[dict[str, Any]], ctx: dict[str, Any], index: int = 0) -> None:
    receipts[index]["work_id"] = "C2PRO-DEV-99"
    reattest(receipts, ctx)  # a freshly attested receipt: only the work binding can reject it


def test_1013_cx_p1_receipt_for_another_work_item_is_rejected() -> None:
    receipts, policy, ctx = normal_case()
    _foreign_work(receipts, ctx)
    assert_rejected("WORK_MISMATCH", receipts, policy, ctx)


@pytest.mark.parametrize("index", [0, 1, 2])
def test_1013_cx_p1_every_architecture_role_is_bound_to_the_work(index: int) -> None:
    receipts, policy, ctx = architecture_case()
    _foreign_work(receipts, ctx, index)
    assert_rejected("WORK_MISMATCH", receipts, policy, ctx)


@pytest.mark.parametrize("mutate", [
    lambda e: e.pop("work_id"),
    lambda e: e.update(work_id=None),
    lambda e: e.update(work_id=14),
    lambda e: e.update(work_id=""),
    lambda e: e.update(work_id="c2pro-dev-14"),
    lambda e: e.update(work_id="C2PRO-DEV-14 "),
    lambda e: e.update(work_id="C2PRO-DEV-14\n"),
    lambda e: e.update(work_id=["C2PRO-DEV-14"]),
])
def test_1013_cx_p1_missing_or_malformed_trusted_work_id_fails_closed(mutate: Callable[[dict[str, Any]], Any]) -> None:
    receipts, policy, ctx = normal_case()
    mutate(ctx["implementation_evidence"])
    assert_rejected("IMPLEMENTER_UNVERIFIED", receipts, policy, ctx)


def test_1013_cx_p1_receipt_cannot_supply_its_own_work_identity() -> None:
    """With no trusted work id, the receipt's self-declared one is never used as a fallback."""
    receipts, policy, ctx = normal_case()
    del ctx["implementation_evidence"]["work_id"]
    assert receipts[0]["work_id"] == "C2PRO-DEV-14"
    assert_rejected("IMPLEMENTER_UNVERIFIED", receipts, policy, ctx)


def _ci_run(run_id: int, conclusion: str) -> dict[str, Any]:
    return {"id": run_id, "name": "CI Status", "app_id": CHECK_APP, "head_sha": HEAD, "conclusion": conclusion,
            "workflow_path": ".github/workflows/ci.yml", "workflow_sha": "c1" * 20}


def _observe(receipts: list[dict[str, Any]], ctx: dict[str, Any], *observed: tuple[int, str]) -> None:
    receipts[0]["result"]["tests_observed"] = [{"name": "CI Status", "check_run_id": i, "conclusion": c}
                                               for i, c in observed]
    reattest(receipts, ctx)


def test_1013_cx_p2_approval_that_observed_a_failed_required_check_is_rejected() -> None:
    """Historical failure (500) then success (501): the gate is green, but the receipt saw only the failure."""
    receipts, policy, ctx = normal_case()
    ctx["check_runs"].insert(0, _ci_run(500, "failure"))
    _observe(receipts, ctx, (500, "failure"))
    assert_rejected("CHECK_PROVENANCE", receipts, policy, ctx)


def test_1013_cx_p2_stale_success_superseded_by_a_newer_run_is_rejected() -> None:
    receipts, policy, ctx = normal_case()
    ctx["check_runs"].insert(0, _ci_run(499, "success"))
    _observe(receipts, ctx, (499, "success"))  # a later run (501) exists; the receipt did not see it
    assert_rejected("CHECK_PROVENANCE", receipts, policy, ctx)


def test_1013_cx_p2_a_failed_observation_is_not_cleared_by_also_observing_the_success() -> None:
    receipts, policy, ctx = normal_case()
    ctx["check_runs"].insert(0, _ci_run(500, "failure"))
    _observe(receipts, ctx, (501, "success"), (500, "failure"))
    assert_rejected("CHECK_PROVENANCE", receipts, policy, ctx)


def test_1013_cx_p2_fabricated_required_check_is_rejected() -> None:
    receipts, policy, ctx = normal_case()
    _observe(receipts, ctx, (999, "success"))
    assert_rejected("CHECK_PROVENANCE", receipts, policy, ctx)


def test_1013_cx_p2_failed_required_check_is_rejected_by_the_receipt_rule_alone() -> None:
    """The latest run failed and the receipt says so; reject at receipt level, not only at gate level."""
    receipts, policy, ctx = normal_case()
    ctx["check_runs"][0]["conclusion"] = "failure"
    _observe(receipts, ctx, (501, "failure"))
    result = vr._verify_with_disabled_rules(receipts, policy, ctx, frozenset())
    assert any(v.code == "CHECK_PROVENANCE" and v.receipt_id == receipts[0]["receipt_id"] for v in result.violations)


def test_1013_cx_p2_observing_the_latest_successful_run_still_passes() -> None:
    receipts, policy, ctx = normal_case()
    ctx["check_runs"].insert(0, _ci_run(500, "failure"))
    _observe(receipts, ctx, (501, "success"))
    assert vr.verify(receipts, policy, ctx).gate_satisfied


def _run_cli(tmp_path: Path, receipts: Any, policy: Any, ctx: Any) -> tuple[int, dict[str, Any]]:
    for name, value in (("receipts", receipts), ("policy", policy), ("context", ctx)):
        (tmp_path / f"{name}.yaml").write_text(yaml.safe_dump(value))
    args = [str(tmp_path / f"{n}.yaml") for n in ("receipts", "policy", "context")]
    proc = subprocess.run([sys.executable, str(VERIFIER), "--receipts", args[0], "--policy", args[1], "--context", args[2]],
                          capture_output=True, text=True, check=False, timeout=60)
    return proc.returncode, json.loads(proc.stdout)


def test_1013_c6_audit_only_cli_never_exits_zero_on_a_satisfied_gate(tmp_path: Path) -> None:
    code, out = _run_cli(tmp_path, *normal_case())
    assert code != 0, "exit 0 would read as a passing required check"
    assert out["mode"] == "AUDIT_ONLY" and out["gate_satisfied"] is True  # audit result stays machine-readable
    assert out.get("authorizes_merge") is False


def test_1013_c6_satisfied_and_unsatisfied_audits_have_distinct_nonzero_exits(tmp_path: Path) -> None:
    receipts, policy, ctx = normal_case()
    satisfied, _ = _run_cli(tmp_path, receipts, policy, ctx)
    ctx["check_runs"][0]["conclusion"] = "failure"
    unsatisfied, out = _run_cli(tmp_path, receipts, policy, ctx)
    assert 0 not in (satisfied, unsatisfied) and satisfied != unsatisfied
    assert out["gate_satisfied"] is False and out.get("authorizes_merge") is False


def test_1013_c6_an_audit_result_never_satisfies_an_enforce_gate() -> None:
    result = vr.verify(*normal_case())
    assert result.gate_satisfied and result.mode == "AUDIT_ONLY"
    assert getattr(result, "authorizes_merge", None) is False
    result.mode = "ENFORCE"  # relabelling a result after the fact grants nothing
    assert getattr(result, "authorizes_merge", None) is False
    with pytest.raises(TypeError):
        vr.GateResult(True, "normal", ("principal",), ("principal",), [], mode="ENFORCE")


# ============================================================================ #1015 Codex review of cafdf946 (RED first)
@pytest.mark.parametrize("mutate", [
    lambda c: c["implementation_evidence"].pop("work_id"),
    lambda c: c["implementation_evidence"].update(work_id="not-a-work-id"),
    lambda c: c["implementation_evidence"].update(worker_id=123),
    lambda c: c["implementation_evidence"].update(worker_id=""),
    lambda c: c["implementation_evidence"].update(worker_id="Claude-Code"),
    lambda c: c["implementation_evidence"].update(verified=False),
    lambda c: c.update(implementation_evidence=None),
])
def test_1015_trusted_work_evidence_fails_closed_even_when_the_gate_needs_no_receipt(
        mutate: Callable[[dict[str, Any]], Any]) -> None:
    """A trivial gate requires no roles, so no receipt rule runs; the context check must still catch bad evidence."""
    _, policy, ctx = normal_case()
    ctx["effective_risk_class"] = "trivial"
    ctx["attestations"], ctx["head_reviews"] = {}, []
    mutate(ctx)
    assert_rejected("IMPLEMENTER_UNVERIFIED", [], policy, ctx)


def test_1015_valid_trusted_work_evidence_still_satisfies_a_trivial_gate() -> None:
    _, policy, ctx = normal_case()
    ctx["effective_risk_class"] = "trivial"
    ctx["attestations"], ctx["head_reviews"] = {}, []
    assert vr.verify([], policy, ctx).gate_satisfied


def test_1015_authorizes_merge_is_false_even_if_the_module_mode_is_reconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    result = vr.verify(*normal_case())
    monkeypatch.setattr(vr, "ENFORCEMENT_MODE", "ENFORCE")
    result.mode = "ENFORCE"
    assert result.gate_satisfied and result.authorizes_merge is False


def test_1015_duplicate_required_check_names_are_an_invalid_policy() -> None:
    """Two producers under one name: a receipt could observe only one of them; refuse the policy instead."""
    receipts, policy, ctx = normal_case()
    other = {"name": "CI Status", "app_id": CHECK_APP, "workflow_path": ".github/workflows/other.yml",
             "workflow_shas": ["b2" * 20]}
    policy["required_checks"].append(other)
    ctx["check_runs"].append({"id": 601, "name": "CI Status", "app_id": CHECK_APP, "head_sha": HEAD,
                              "conclusion": "success", "workflow_path": other["workflow_path"], "workflow_sha": "b2" * 20})
    _observe(receipts, ctx, (601, "success"))  # the receipt observed only the second producer
    assert_rejected("POLICY_INVALID", receipts, policy, ctx)


# ============================================================================ #1015 Codex review of 9a7215b3 (RED first)
_BAD_IMPLEMENTER_IDS = [123, True, ["claude_code"], {"id": 1}, "Claude Code", "claude_code\n", " claude_code", "claude_code "]


@pytest.mark.parametrize("bad_worker", _BAD_IMPLEMENTER_IDS)
def test_1015_trusted_implementer_id_must_be_a_strict_worker_id(bad_worker: Any) -> None:
    """Truthiness is not identity: a non-string or malformed implementer id must fail even with no receipts."""
    _, policy, ctx = normal_case()
    ctx["effective_risk_class"] = "trivial"
    ctx["attestations"], ctx["head_reviews"] = {}, []
    ctx["implementation_evidence"]["worker_id"] = bad_worker
    assert_rejected("IMPLEMENTER_UNVERIFIED", [], policy, ctx)


@pytest.mark.parametrize("bad_worker", _BAD_IMPLEMENTER_IDS)
def test_1015_malformed_implementer_id_is_still_rejected_at_nontrivial_risk(bad_worker: Any) -> None:
    """Regression guard: the nontrivial path already failed closed (IMPLEMENTER_MISMATCH) and must keep doing so."""
    receipts, policy, ctx = normal_case()
    ctx["implementation_evidence"]["worker_id"] = bad_worker
    assert not vr.verify(receipts, policy, ctx).gate_satisfied


def test_1015_valid_string_implementer_id_still_satisfies_both_gates() -> None:
    _, policy, ctx = normal_case()
    ctx["effective_risk_class"] = "trivial"
    ctx["attestations"], ctx["head_reviews"] = {}, []
    assert vr.verify([], policy, ctx).gate_satisfied
    assert vr.verify(*normal_case()).gate_satisfied


# ============================================================================ #1016 trusted context/policy shape (RED first)
# Every fact the verifier trusts is shape-checked before risk, gates or receipts are evaluated. A malformed
# trusted fact is POLICY_INVALID (CHECK_PROVENANCE for check runs) and never reads as "nothing found".
_HB_CHANGE = {"path": ".github/workflows/x.yml", "previous_path": None, "status": "added", "mode": "100644",
              "blob_sha": "4" * 40}


def _trivial(ctx: dict[str, Any]) -> dict[str, Any]:
    ctx["effective_risk_class"] = "trivial"
    ctx["attestations"], ctx["head_reviews"] = {}, []
    return ctx


def _rejected_without_receipts(code: str, policy: dict[str, Any], ctx: dict[str, Any]) -> None:
    """The no-receipt trivial path must fail closed too: no receipt rule runs there."""
    assert_rejected(code, [], policy, _trivial(ctx))


# ---- P2-A: check-run records
@pytest.mark.parametrize("bad_id", ["502", 502.0, True, None, 0, -1])
def test_1016_p2a_failing_rerun_with_malformed_id_cannot_hide_behind_an_older_green_run(bad_id: Any) -> None:
    receipts, policy, ctx = normal_case()
    ctx["check_runs"].append(dict(ctx["check_runs"][0], id=bad_id, conclusion="failure"))
    assert_rejected("CHECK_PROVENANCE", receipts, policy, ctx)


@pytest.mark.parametrize("bad_id", ["502", True, None])
def test_1016_p2a_malformed_check_run_id_fails_closed_without_receipts(bad_id: Any) -> None:
    _, policy, ctx = normal_case()
    ctx["check_runs"].append(dict(ctx["check_runs"][0], id=bad_id, conclusion="failure"))
    _rejected_without_receipts("CHECK_PROVENANCE", policy, ctx)


@pytest.mark.parametrize("order", ["success_first", "failure_first"])
def test_1016_p2a_duplicate_check_run_ids_are_ambiguous(order: str) -> None:
    _, policy, ctx = normal_case()
    dup = dict(ctx["check_runs"][0], conclusion="failure")
    ctx["check_runs"] = [ctx["check_runs"][0], dup] if order == "success_first" else [dup, ctx["check_runs"][0]]
    _rejected_without_receipts("CHECK_PROVENANCE", policy, ctx)


@pytest.mark.parametrize("field,value", [
    ("name", ""), ("name", None), ("app_id", "15368"), ("app_id", None), ("head_sha", None), ("head_sha", "a" * 39),
    ("workflow_path", None), ("workflow_path", "./.github/workflows/ci.yml"), ("workflow_sha", None),
    ("workflow_sha", 123), ("conclusion", 1),
])
def test_1016_p2a_malformed_check_run_fields_fail_closed(field: str, value: Any) -> None:
    _, policy, ctx = normal_case()
    ctx["check_runs"][0][field] = value
    _rejected_without_receipts("CHECK_PROVENANCE", policy, ctx)


def test_1016_p2a_check_run_entry_must_be_a_mapping() -> None:
    _, policy, ctx = normal_case()
    ctx["check_runs"].append("CI Status")
    _rejected_without_receipts("CHECK_PROVENANCE", policy, ctx)


def test_1016_p2a_in_progress_newer_run_still_blocks_and_a_valid_rerun_passes() -> None:
    receipts, policy, ctx = normal_case()
    ctx["check_runs"].append(dict(ctx["check_runs"][0], id=502, conclusion=None))
    assert_rejected("CHECK_PROVENANCE", receipts, policy, ctx)
    receipts, policy, ctx = normal_case()
    assert vr.verify(receipts, policy, ctx).gate_satisfied  # positive control


# ---- P2-B: trusted head-review identity
def _t1_entry(**overrides: Any) -> dict[str, Any]:
    entry = {"source": "T1", "review_id": 999, "app_id": CODEX_APP, "user_id": CODEX_BOT,
             "state": "CHANGES_REQUESTED"}
    entry.update(overrides)
    return entry


@pytest.mark.parametrize("override,drop", [
    ({"app_id": str(CODEX_APP)}, None), ({"app_id": None}, None), ({"app_id": True}, None),
    ({}, "app_id"), ({}, "user_id"), ({"user_id": None}, None), ({"user_id": str(CODEX_BOT)}, None),
    ({"review_id": "999"}, None), ({}, "review_id"), ({"state": None}, None), ({"state": 1}, None),
])
def test_1016_p2b_malformed_blocking_app_review_identity_fails_closed(override: dict[str, Any], drop: str | None) -> None:
    receipts, policy, ctx = normal_case()
    entry = _t1_entry(**override)
    if drop:
        del entry[drop]
    ctx["head_reviews"].append(entry)
    assert_rejected("POLICY_INVALID", receipts, policy, ctx)


def test_1016_p2b_malformed_app_review_identity_fails_closed_without_receipts() -> None:
    _, policy, ctx = normal_case()
    _trivial(ctx)
    ctx["head_reviews"].append(_t1_entry(app_id=str(CODEX_APP)))
    assert_rejected("POLICY_INVALID", [], policy, ctx)


@pytest.mark.parametrize("entry", [
    "T1", {"source": "T2"}, {"source": "T2", "receipt_id": 7, "receipt": {}}, {"source": "T2", "receipt_id": "x"},
    {"source": "T3", "review_id": 1},
])
def test_1016_p2b_malformed_head_review_entries_fail_closed(entry: Any) -> None:
    receipts, policy, ctx = normal_case()
    ctx["head_reviews"].append(entry)
    assert_rejected("POLICY_INVALID", receipts, policy, ctx)


def test_1016_p2b_controls_allowlisted_block_still_contradicts_and_foreign_app_has_no_authority() -> None:
    receipts, policy, ctx = normal_case()
    ctx["head_reviews"].append(_t1_entry())
    assert_rejected("CONTRADICTING_REVIEW", receipts, policy, ctx)
    receipts, policy, ctx = normal_case()
    ctx["head_reviews"].append(_t1_entry(app_id=123456, user_id=654321))  # validly identified, not allowlisted
    assert vr.verify(receipts, policy, ctx).gate_satisfied


@pytest.mark.parametrize("apps", [
    [{"app_id": str(CODEX_APP), "user_id": CODEX_BOT}], [{"app_id": CODEX_APP}], ["900001"], "900001",
])
def test_1016_p2b_malformed_t1_app_allowlist_is_an_invalid_policy(apps: Any) -> None:
    receipts, policy, ctx = normal_case()
    policy["t1_apps"] = apps
    assert_rejected("POLICY_INVALID", receipts, policy, ctx)


# ---- P2-C: high-blast-radius policy and canonical paths
@pytest.mark.parametrize("paths", [
    ".github/workflows/", [], [".github/workflows/", ".github/workflows/"], [""], [None], [7],
    ["./.github/workflows/"], ["../escape/"], ["/abs/path"], ["a//b/"], [" .github/workflows/"], ["a\\b"],
])
def test_1016_p2c_malformed_high_blast_radius_paths_never_downgrade_risk(paths: Any) -> None:
    receipts, policy, ctx = normal_case()
    policy["high_blast_radius_paths"] = paths
    assert_rejected("POLICY_INVALID", receipts, policy, ctx)
    _, policy, ctx = normal_case()
    policy["high_blast_radius_paths"] = paths
    ctx["pr"]["changed_files"].append(dict(_HB_CHANGE))
    _rejected_without_receipts("POLICY_INVALID", policy, ctx)


@pytest.mark.parametrize("path", ["./.github/workflows/x.yml", ".github//workflows/x.yml", "/etc/x", "a/../b",
                                  "x.yml ", "", None, ".github/workflows/"])
def test_1016_p2c_non_canonical_changed_paths_fail_closed(path: Any) -> None:
    _, policy, ctx = normal_case()
    ctx["pr"]["changed_files"].append(dict(_HB_CHANGE, path=path))
    _rejected_without_receipts("POLICY_INVALID", policy, ctx)


def test_1016_p2c_non_canonical_previous_path_fails_closed() -> None:
    _, policy, ctx = normal_case()
    ctx["pr"]["changed_files"].append(dict(_HB_CHANGE, path="docs/x.md", previous_path="./.github/workflows/x.yml",
                                           status="renamed"))
    _rejected_without_receipts("POLICY_INVALID", policy, ctx)


def test_1016_p2c_control_valid_list_escalates_renames_and_trivial_risk() -> None:
    _, policy, ctx = normal_case()
    ctx["pr"]["changed_files"].append(dict(_HB_CHANGE, path="docs/moved.yml", previous_path=".github/workflows/x.yml",
                                           status="renamed"))
    result = vr.verify([], policy, _trivial(ctx))
    assert result.risk_class == "high_blast_radius" and not result.gate_satisfied


# ---- P3 discoveries: trusted subject facts on the no-receipt path
@pytest.mark.parametrize("mutate", [
    lambda c: c["pr"].update(number="7"), lambda c: c["pr"].update(number=0), lambda c: c["pr"].update(number=True),
    lambda c: c["pr"].update(head_sha=None), lambda c: c["pr"].update(head_sha="A" * 40),
    lambda c: c["pr"].update(base_sha=None), lambda c: c["pr"].update(merge_base_sha=123),
    lambda c: c["repository"].update(id="1"), lambda c: c["repository"].update(full_name="not a repo"),
    lambda c: c.update(repository=None), lambda c: c.update(effective_risk_class="TRIVIAL"),
    lambda c: c.update(effective_risk_class=None), lambda c: c["pr"].update(changed_files="x"),
    lambda c: c["pr"]["changed_files"].append("x"),
    lambda c: c["pr"]["changed_files"].append(dict(_HB_CHANGE, path="scripts/example.py")),
    lambda c: c["pr"]["changed_files"].append(dict(_HB_CHANGE, status="moved")),
    lambda c: c["pr"]["changed_files"].append(dict(_HB_CHANGE, mode="100777")),
    lambda c: c["pr"]["changed_files"].append(dict(_HB_CHANGE, blob_sha="z" * 40)),
    lambda c: c.update(app_reviews=[]), lambda c: c.update(attestations=[]),
])
def test_1016_p3_malformed_subject_facts_fail_closed_without_receipts(mutate: Callable[[dict[str, Any]], Any]) -> None:
    _, policy, ctx = normal_case()
    _trivial(ctx)
    mutate(ctx)
    assert_rejected("POLICY_INVALID", [], policy, ctx)


@pytest.mark.parametrize("entry", [None, [], ["7", HEAD], [7], [7, HEAD, 1], [7, "a" * 39], "7"])
def test_1016_p3_malformed_consumed_ledger_entry_fails_closed(entry: Any) -> None:
    receipts, policy, ctx = normal_case()
    ctx["consumed"][f"receipt:{receipts[0]['receipt_id']}"] = entry
    assert_rejected("POLICY_INVALID", receipts, policy, ctx)


def test_1016_p3_consumed_ledger_key_must_be_typed() -> None:
    receipts, policy, ctx = normal_case()
    ctx["consumed"]["no-kind-prefix"] = [7, HEAD]
    assert_rejected("POLICY_INVALID", receipts, policy, ctx)


# ---- policy shape
@pytest.mark.parametrize("mutate", [
    lambda p: p.update(gates=[]), lambda p: p["gates"].pop("trivial"), lambda p: p["gates"].update(trivial=None),
    lambda p: p["gates"].update(normal="principal"), lambda p: p["gates"].update(normal=["reviewer"]),
    lambda p: p["gates"].update(normal=["principal", "principal"]),
    lambda p: p.update(required_checks={}), lambda p: p["required_checks"].append("CI"),
    lambda p: p["required_checks"][0].update(app_id="15368"), lambda p: p["required_checks"][0].update(app_id=None),
    lambda p: p["required_checks"][0].update(workflow_path=None),
    lambda p: p["required_checks"][0].update(workflow_path="./.github/workflows/ci.yml"),
    lambda p: p["required_checks"][0].update(workflow_shas="c1" * 20),
    lambda p: p["required_checks"][0].update(workflow_shas=[]),
    lambda p: p["required_checks"][0].update(workflow_shas=["c1" * 19]),
    lambda p: p["required_checks"][0].update(name=""),
    lambda p: p.update(role_eligibility={"principal": "codex"}),
    lambda p: p["role_eligibility"].update(principal=["Codex"]),
    lambda p: p.update(worker_providers={"codex": None}), lambda p: p.update(t1_apps_worker={"900001": 5}),
    lambda p: p.update(t2="enabled"), lambda p: p["t2"].update(workflow_commit_shas="d" * 40),
    lambda p: p["t2"].update(dispatcher_user_ids=["1001"]), lambda p: p["t2"].update(issuer=None),
])
def test_1016_malformed_trusted_policy_fails_closed(mutate: Callable[[dict[str, Any]], Any]) -> None:
    _, policy, ctx = normal_case()
    mutate(policy)
    _rejected_without_receipts("POLICY_INVALID", policy, ctx)


@pytest.mark.parametrize("bad", [None, [], "policy", 7])
def test_1016_non_mapping_policy_or_context_fails_closed(bad: Any) -> None:
    receipts, policy, ctx = normal_case()
    assert_rejected("POLICY_INVALID", receipts, bad, ctx)
    assert_rejected("POLICY_INVALID", receipts, policy, bad)


def test_1016_positive_controls_audit_policy_t2_disabled_and_empty_t1_still_valid() -> None:
    """The committed AUDIT_ONLY policy (t2: null, t1_apps: []) keeps passing the shape check."""
    audit_policy = yaml.safe_load((Path(__file__).resolve().parents[2]
                                   / "scripts/development/review_attestation/audit-policy.yaml").read_text())
    _, _, ctx = normal_case()
    _trivial(ctx)
    audit_policy["required_checks"][0]["workflow_shas"] = ["c1" * 20]
    assert vr.verify([], audit_policy, ctx).gate_satisfied
    assert vr.verify(*normal_case()).gate_satisfied
    assert vr.verify(*architecture_case()).gate_satisfied
