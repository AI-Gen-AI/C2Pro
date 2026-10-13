"""#1009 PR-A: offline review-receipt verifier (AUDIT_ONLY). Synthetic data only; no network.

Behavioural RED: every negative case below is ACCEPTED by an accept-all verifier, so each test
fails until its rule exists. Tamper tests mutate every bound field of a valid receipt; the
ablation test switches each rule off in turn and proves some case then slips through.
"""

from __future__ import annotations

import copy
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


def codes(receipts: list[dict[str, Any]], policy: dict[str, Any], ctx: dict[str, Any], **kw: Any) -> set[str]:
    result = vr.verify(receipts, policy, ctx, **kw)
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
def test_every_rule_is_load_bearing(rule_name: str) -> None:
    for receipts, policy, ctx in _negative_suite():
        assert not vr.verify(copy.deepcopy(receipts), policy, ctx).gate_satisfied
    slipped = [i for i, (receipts, policy, ctx) in enumerate(_negative_suite())
               if vr.verify(copy.deepcopy(receipts), policy, ctx, disabled_rules=frozenset({rule_name})).gate_satisfied]
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
    ctx["check_runs"][0]["conclusion"] = "failure"
    ctx["check_runs"].append({"id": 502, "name": "CI Status", "app_id": CHECK_APP, "head_sha": HEAD,
                              "conclusion": "success", "workflow_path": ".github/workflows/pr-added.yml",
                              "workflow_sha": "f" * 40})
    receipts[0]["result"]["tests_observed"] = []
    reattest(receipts, ctx)
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
    ctx["head_reviews"].append({"source": "T2", "receipt_id": "00000009-0000-4000-8000-000000000009",
                                "worker_id": "codex", "verdict": "BLOCK", "recommended_action": "remediate"})
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
    (lambda c, rid: c["pr"].update(changed_files_complete=False), "DIFF_MISMATCH"),
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
