"""TS-G2-CI-GATES-618: tests for policy-derived merge-gate decisions."""
from __future__ import annotations

from core.merge_gate_policy import evaluate_merge_gates, freeze_policy

HEAD = "head-sha"
WORKFLOW = {"sha": HEAD, "run_id": 700, "attempt": 2, "status": "completed"}
POLICY = {
    "target_branch": "main",
    "default_branch": "main",
    "rulesets": [
        {
            "id": 99,
            "target": "branch",
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
    decision = evaluate_merge_gates(POLICY, [signal("build", "in_progress"), signal("secrets", "success")], HEAD, current_run_id=700, current_attempt=2, workflow_runs=[WORKFLOW])

    assert decision["decision"] == "BLOCKED"
    assert decision["reason"] == "required gates pending"
    assert decision["gate_matrix"][0]["state"] == "PENDING"


def test_missing_and_failed_required_gates_block_merge():
    """TS-G2-CI-GATES-618: absent and terminal-failed required gates fail closed."""
    missing = evaluate_merge_gates(POLICY, [signal("build", "success")], HEAD, current_run_id=700, current_attempt=2, workflow_runs=[WORKFLOW])
    failed = evaluate_merge_gates(POLICY, [signal("build", "failure"), signal("secrets", "success")], HEAD, current_run_id=700, current_attempt=2, workflow_runs=[WORKFLOW])

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

    decision = evaluate_merge_gates(POLICY, signals, HEAD, current_run_id=700, current_attempt=2, workflow_runs=[WORKFLOW])

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

    decision = evaluate_merge_gates(POLICY, signals, HEAD, current_run_id=700, current_attempt=2, workflow_runs=[WORKFLOW])

    assert [row["state"] for row in decision["gate_matrix"]] == ["PENDING", "FAILED"]
    assert all(row.get("attempt") == 2 for row in decision["gate_matrix"])


def test_unknown_signal_is_visible_conservative_and_not_a_failed_gate():
    """TS-G2-CI-GATES-618: unknown classification blocks without inventing failure."""
    signals = [signal("build", "success"), signal("secrets", "success"), signal("mystery", "success")]

    decision = evaluate_merge_gates(POLICY, signals, HEAD, current_run_id=700, current_attempt=2, workflow_runs=[WORKFLOW])

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

    decision = evaluate_merge_gates(policy, [check], HEAD, current_run_id=700, current_attempt=2, workflow_runs=[WORKFLOW])

    assert decision["decision"] == "MERGE_ALLOWED"
    assert decision["policy_snapshot"]["source"] == "branch_protection"


def test_ruleset_applicability_and_protection_fallback():
    from copy import deepcopy

    for include, exclude, target, enforcement, expected in [
        (["refs/heads/main"], [], "branch", "active", True),
        (["ma*"], [], "branch", "active", True),
        (["refs/heads/m?in"], [], "branch", "active", True),
        (["~ALL"], ["refs/heads/main"], "branch", "active", False),
        (["~DEFAULT_BRANCH"], ["~ALL"], "branch", "active", False),
        (["refs/heads/release/*"], [], "branch", "active", False),
        (["~ALL"], [], "tag", "active", False),
        (["~ALL"], [], "branch", "evaluate", False),
        ([], [], "branch", "active", False),
    ]:
        policy = deepcopy(POLICY)
        policy["default_branch"] = "main"
        rule = policy["rulesets"][0]
        rule.update(target=target, enforcement=enforcement)
        rule["conditions"]["ref_name"] = {"include": include, "exclude": exclude}
        policy["branch_protection"] = {"required_status_checks": {"contexts": ["fallback"]}}
        frozen = freeze_policy(policy)
        assert frozen["source"] == ("rulesets" if expected else "branch_protection")
        assert frozen["required_gates"][0]["context"] == ("build" if expected else "fallback")
        assert frozen == freeze_policy(deepcopy(policy))

    policy["rulesets"][0].update(target="branch", enforcement="active", rules=[])
    policy["rulesets"][0]["conditions"]["ref_name"]["include"] = ["~ALL"]
    assert freeze_policy(policy)["source"] == "branch_protection"


def test_default_branch_requires_explicit_matching_default():
    from copy import deepcopy

    for default in (None, "release", "refs/heads/main"):
        policy = deepcopy(POLICY)
        policy["default_branch"] = default
        assert bool(freeze_policy(policy)["required_gates"]) == (default == "refs/heads/main")


def test_protection_checks_override_duplicate_legacy_contexts():
    policy = {
        "target_branch": "main",
        "branch_protection": {"required_status_checks": {
            "checks": [{"context": "build", "app_id": 42}],
            "contexts": ["build", "legacy", "legacy"],
        }},
    }
    assert freeze_policy(policy)["required_gates"] == [
        {"context": "build", "integration_id": 42},
        {"context": "legacy", "integration_id": None},
    ]
    result = evaluate_merge_gates(
        policy, [signal("build", "success", integration_id=99), signal("legacy", "success")],
        HEAD, current_run_id=700, current_attempt=2, workflow_runs=[WORKFLOW],
    )
    assert result["decision"] == "BLOCKED"
    assert result["gate_matrix"][0]["state"] == "MISSING"


def test_workflow_authority_requires_current_sha_run_and_attempt():
    checks = [signal("build", "success"), signal("secrets", "success")]
    for runs in (None, [], [{**WORKFLOW, "sha": "old"}],
                 [{**WORKFLOW, "run_id": 699}], [{**WORKFLOW, "attempt": 1}]):
        result = evaluate_merge_gates(
            POLICY, checks, HEAD, current_run_id=700, current_attempt=2, workflow_runs=runs,
        )
        assert result["decision"] == "BLOCKED"
        assert "workflow" in result["reason"]
        assert result["workflow_runs"] == []
        assert {row["state"] for row in result["gate_matrix"]} == {"SUCCESS"}

    for ids in ({}, {"current_run_id": 700}, {"current_attempt": 2}):
        result = evaluate_merge_gates(POLICY, checks, HEAD, workflow_runs=[WORKFLOW], **ids)
        assert result["decision"] == "BLOCKED"

    evidence = {**WORKFLOW, "url": "authoritative-evidence", "conclusion": "failure"}
    result = evaluate_merge_gates(
        POLICY, checks, HEAD, current_run_id=700, current_attempt=2,
        workflow_runs=[{**WORKFLOW, "attempt": 1}, evidence],
    )
    assert result["decision"] == "MERGE_ALLOWED"
    assert result["workflow_runs"] == [evidence]

def test_ruleset_missing_target_defaults_to_branch():
    """A ruleset with omitted target retains GitHub branch-target semantics."""
    policy = {
        "target_branch": "main",
        "default_branch": "main",
        "rulesets": [
            {
                "enforcement": "active",
                "conditions": {
                    "ref_name": {
                        "include": ["~DEFAULT_BRANCH"],
                        "exclude": [],
                    }
                },
                "rules": [
                    {
                        "type": "required_status_checks",
                        "parameters": {
                            "required_status_checks": [
                                {
                                    "context": "compat-probe",
                                    "integration_id": 42,
                                }
                            ]
                        },
                    }
                ],
            }
        ],
    }

    frozen = freeze_policy(policy)

    assert frozen["source"] == "rulesets"
    assert frozen["required_gates"] == [
        {
            "context": "compat-probe",
            "integration_id": 42,
        }
    ]
