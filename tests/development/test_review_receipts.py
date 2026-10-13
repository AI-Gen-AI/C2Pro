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
    assert result.gate_satisfied and result.satisfied_roles == ("principal",), result.violations


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
    assert result.risk_class == "high_blast_radius" and not result.gate_satisfied
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
        lambda r: r[0]["review"].update(implementation_worker_id="codex"),   # implementer
        lambda r: r[0]["review"].update(worker_id="gpt6_orchestrator"),      # eligibility
        lambda r: r[0]["review"].update(worker_id="claude_code"),            # independence
        lambda r: r[0]["result"].update(verdict="BLOCK"),                    # result_consistency
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
