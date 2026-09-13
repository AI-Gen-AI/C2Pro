"""TS-G2-CI-GATES-618: tests for policy-derived merge-gate decisions."""
from __future__ import annotations

from core.merge_gate_policy import evaluate_merge_gates, freeze_policy

HEAD = "head-sha"
POLICY = {
    "target_branch": "main",
    "rulesets": [
        {
            "id": 99,
            "name": "dynamic policy",
            "enforcement": "active",
            "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
            "rules": [
                {
                    "type": "required_status_checks",
                    "parameters": {
                        "required_status_checks": [
                            {"context": "build", "integration_id": 42},
                            {"context": "secrets", "integration_id": 42},
                        ]
                    },
                }
            ],
        }
    ],
}


def signal(name: str, status: str, *, attempt: int = 2, sha: str = HEAD, **extra):
    """Build one GitHub signal for the current workflow attempt."""
    return {
        "name": name,
        "status": status,
        "sha": sha,
        "run_id": 700,
        "attempt": attempt,
        "integration_id": 42,
        **extra,
    }


def test_ruleset_discovery_freezes_dynamic_contexts_and_integration_identity():
    """TS-G2-CI-GATES-618: active rulesets, rather than a fixed list, define gates."""
    snapshot = freeze_policy(POLICY)

    assert snapshot["required_gates"] == [
        {"context": "build", "integration_id": 42},
        {"context": "secrets", "integration_id": 42},
    ]
    assert snapshot["snapshot_hash"]


def test_pending_required_gate_is_blocked_pending_not_failed():
    """TS-G2-CI-GATES-618: pending is a distinct non-terminal state."""
    decision = evaluate_merge_gates(POLICY, [signal("build", "in_progress"), signal("secrets", "success")], HEAD)

    assert decision["decision"] == "BLOCKED"
    assert decision["reason"] == "required gates pending"
    assert decision["gate_matrix"][0]["state"] == "PENDING"


def test_missing_and_failed_required_gates_block_merge():
    """TS-G2-CI-GATES-618: absent and terminal-failed required gates fail closed."""
    missing = evaluate_merge_gates(POLICY, [signal("build", "success")], HEAD)
    failed = evaluate_merge_gates(POLICY, [signal("build", "failure"), signal("secrets", "success")], HEAD)

    assert missing["decision"] == "BLOCKED"
    assert {row["state"] for row in missing["gate_matrix"]} == {"SUCCESS", "MISSING"}
    assert failed["decision"] == "BLOCKED"
    assert failed["reason"] == "required gates failed"


def test_advisory_failure_does_not_block_successful_required_gates():
    """TS-G2-CI-GATES-618: visible non-policy failures remain advisory."""
    signals = [
        signal("build", "success"),
        signal("secrets", "success"),
        signal("codecov/patch", "failure", classification="ADVISORY_CHECK"),
        signal("workflow telemetry", "completed", classification="OBSERVABILITY_SIGNAL"),
    ]

    decision = evaluate_merge_gates(POLICY, signals, HEAD)

    assert decision["decision"] == "MERGE_ALLOWED"
    assert [item["classification"] for item in decision["signals"]] == [
        "REQUIRED_GATE", "REQUIRED_GATE", "ADVISORY_CHECK", "OBSERVABILITY_SIGNAL"
    ]


def test_current_sha_and_attempt_supersede_older_success():
    """TS-G2-CI-GATES-618: stale SHA and earlier attempts cannot satisfy gates."""
    signals = [
        signal("build", "success", attempt=1),
        signal("build", "in_progress", attempt=2),
        signal("secrets", "success", sha="old-sha"),
        signal("secrets", "failure"),
    ]

    decision = evaluate_merge_gates(POLICY, signals, HEAD)

    assert [row["state"] for row in decision["gate_matrix"]] == ["PENDING", "FAILED"]
    assert all(row.get("attempt") == 2 for row in decision["gate_matrix"])


def test_unknown_signal_is_visible_conservative_and_not_a_failed_gate():
    """TS-G2-CI-GATES-618: unknown classification blocks without inventing failure."""
    signals = [signal("build", "success"), signal("secrets", "success"), signal("mystery", "success")]

    decision = evaluate_merge_gates(POLICY, signals, HEAD)

    assert decision["decision"] == "BLOCKED"
    assert decision["reason"] == "unclassified signals require resolution"
    unknown = decision["signals"][-1]
    assert unknown["classification"] == "UNCLASSIFIED"
    assert unknown["state"] == "SUCCESS"
    assert all(row["context"] != "mystery" for row in decision["gate_matrix"])


def test_incomplete_authoritative_workflow_blocks_visible_successes():
    """TS-G2-CI-GATES-618: partial check materialization cannot imply workflow completion."""
    signals = [signal("build", "success"), signal("secrets", "success")]

    decision = evaluate_merge_gates(
        POLICY,
        signals,
        HEAD,
        current_run_id=700,
        current_attempt=2,
        workflow_runs=[{"run_id": 700, "attempt": 2, "sha": HEAD, "status": "in_progress"}],
    )

    assert decision["decision"] == "BLOCKED"
    assert decision["reason"] == "authoritative workflow pending"
    assert all(row["state"] == "PENDING" for row in decision["gate_matrix"])


def test_branch_protection_context_without_app_accepts_any_integration():
    """TS-G2-CI-GATES-618: branch-protection fallback preserves optional app identity."""
    policy = {
        "target_branch": "release",
        "branch_protection": {"required_status_checks": {"contexts": ["release-build"]}},
    }
    check = signal("release-build", "success", integration_id=987)

    decision = evaluate_merge_gates(policy, [check], HEAD)

    assert decision["decision"] == "MERGE_ALLOWED"
    assert decision["policy_snapshot"]["source"] == "branch_protection"
