"""Frozen RED qualification for GitHub issue #624."""

from core.merge_gate_policy import evaluate_merge_gates, freeze_policy


HEAD = "sealed-head"
APP_ID = 42


def _required_rule(context: str) -> dict:
    return {
        "type": "required_status_checks",
        "parameters": {
            "required_status_checks": [
                {
                    "context": context,
                    "integration_id": APP_ID,
                }
            ]
        },
    }


def _signal(name: str) -> dict:
    return {
        "name": name,
        "status": "success",
        "sha": HEAD,
        "run_id": 700,
        "attempt": 2,
        "integration_id": APP_ID,
    }


def test_non_applicable_active_ruleset_does_not_contribute_required_gate():
    policy = {
        "target_branch": "main",
        "default_branch": "main",
        "rulesets": [
            {
                "id": 10,
                "name": "release-only",
                "target": "branch",
                "enforcement": "active",
                "conditions": {
                    "ref_name": {
                        "include": ["refs/heads/release"],
                        "exclude": [],
                    }
                },
                "rules": [_required_rule("release-build")],
            },
            {
                "id": 11,
                "name": "main-only",
                "target": "branch",
                "enforcement": "active",
                "conditions": {
                    "ref_name": {
                        "include": ["~DEFAULT_BRANCH"],
                        "exclude": [],
                    }
                },
                "rules": [_required_rule("main-build")],
            },
        ],
    }

    frozen = freeze_policy(policy)

    assert frozen["required_gates"] == [
        {
            "context": "main-build",
            "integration_id": APP_ID,
        }
    ]


def test_branch_protection_checks_preserve_app_identity():
    policy = {
        "target_branch": "release",
        "default_branch": "main",
        "rulesets": [],
        "branch_protection": {
            "required_status_checks": {
                "checks": [
                    {
                        "context": "release-build",
                        "app_id": APP_ID,
                    }
                ]
            }
        },
    }

    frozen = freeze_policy(policy)

    assert frozen["required_gates"] == [
        {
            "context": "release-build",
            "integration_id": APP_ID,
        }
    ]


def test_visible_green_checks_without_authoritative_workflow_do_not_authorize_merge():
    policy = {
        "target_branch": "main",
        "default_branch": "main",
        "rulesets": [
            {
                "id": 11,
                "name": "main-only",
                "target": "branch",
                "enforcement": "active",
                "conditions": {
                    "ref_name": {
                        "include": ["~DEFAULT_BRANCH"],
                        "exclude": [],
                    }
                },
                "rules": [_required_rule("main-build")],
            }
        ],
    }

    result = evaluate_merge_gates(
        policy,
        [_signal("main-build")],
        HEAD,
        current_run_id=700,
        current_attempt=2,
        workflow_runs=None,
    )

    assert result["decision"] == "BLOCKED"
    assert "workflow" in result["reason"].lower()
    assert result["gate_matrix"][0]["state"] != "FAILED"
    assert result["workflow_runs"] == []
