"""Contract tests for C2PRO-DEV-01 compact development control."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft7Validator

REPO_ROOT = Path(__file__).resolve().parents[4]
C2PRO_ROOT = REPO_ROOT / ".c2pro"
CONTROL_ROOT = C2PRO_ROOT / "control"
SCHEMA_ROOT = C2PRO_ROOT / "schemas"


def _yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _schema(name: str) -> dict:
    data = json.loads((SCHEMA_ROOT / name).read_text(encoding="utf-8"))
    Draft7Validator.check_schema(data)
    return data


@pytest.mark.parametrize(
    ("data_name", "schema_name"),
    [
        ("current.yaml", "current.schema.json"),
        ("work-queue.yaml", "work-queue.schema.json"),
        ("legacy-compatibility.yaml", "legacy-compatibility.schema.json"),
        ("context-budget.yaml", "context-budget.schema.json"),
    ],
)
def test_canonical_control_files_validate(data_name: str, schema_name: str) -> None:
    Draft7Validator(_schema(schema_name)).validate(_yaml(CONTROL_ROOT / data_name))


def test_queue_schema_cannot_retain_completed_work() -> None:
    queue = _yaml(CONTROL_ROOT / "work-queue.yaml")
    queue["open_work"] = [
        {
            "work_id": "C2P-DEV-9999",
            "role": "implementation_lead",
            "status": "completed",
            "priority": "P1",
            "risk_class": "normal",
            "work_ref": ".c2pro/work/C2P-DEV-9999.yaml",
            "base_sha": "a" * 40,
        }
    ]
    errors = list(Draft7Validator(_schema("work-queue.schema.json")).iter_errors(queue))
    assert errors, "completed status must be invalid in the open-only hot queue"


def test_work_identity_survives_worker_handoff() -> None:
    work = {
        "schema": "c2pro-work-envelope-v1",
        "work_id": "C2P-DEV-9999",
        "campaign_id": None,
        "role": "implementation_lead",
        "status": "in_progress",
        "risk_class": "normal",
        "base_sha": "a" * 40,
        "branch": "feat/example",
        "scope": ["apps/api/src/example.py"],
        "out_of_scope": ["production runtime"],
        "allowed_tools": ["pytest"],
        "forbidden_paths": [".env"],
        "acceptance_criteria": ["bounded change passes tests"],
        "required_tests": ["python -m pytest tests/unit/test_example.py"],
        "evidence_required": ["commit", "ci"],
        "review_policy": "independent_principal",
        "worker_selection": {"preferred": "claude_code", "fallback": ["codex"]},
        "timeout_resource_policy": "AF-DEV bounded default",
        "dependencies": [],
        "architecture_refs": [],
    }
    Draft7Validator(_schema("work-envelope.schema.json")).validate(work)

    reassigned = copy.deepcopy(work)
    reassigned["worker_selection"] = {"preferred": "codex", "fallback": ["claude_code"]}
    Draft7Validator(_schema("work-envelope.schema.json")).validate(reassigned)

    invariant_fields = [
        "work_id",
        "campaign_id",
        "role",
        "base_sha",
        "branch",
        "scope",
        "out_of_scope",
        "acceptance_criteria",
        "required_tests",
        "review_policy",
    ]
    assert {key: work[key] for key in invariant_fields} == {
        key: reassigned[key] for key in invariant_fields
    }


def test_handoff_is_compact_and_does_not_require_chain_of_thought() -> None:
    handoff = {
        "schema": "c2pro-handoff-v1",
        "work_id": "C2P-DEV-9999",
        "role": "implementation_lead",
        "base_sha": "a" * 40,
        "current_head": "b" * 40,
        "current_worker": "claude_code",
        "handoff_reason": "quota_exhausted",
        "completed": ["implemented bounded parser"],
        "remaining": ["run focused tests"],
        "files_changed": ["apps/api/src/example.py"],
        "required_tests_remaining": ["python -m pytest tests/unit/test_example.py"],
        "known_findings": [],
        "forbidden_scope_reminder": ["production runtime"],
        "next_worker": "codex",
    }
    Draft7Validator(_schema("handoff.schema.json")).validate(handoff)
    assert "chain_of_thought" not in handoff
    assert "conversation_transcript" not in handoff


def test_evidence_schema_accepts_references_not_raw_logs() -> None:
    evidence = {
        "schema": "c2pro-evidence-reference-v1",
        "work_id": "C2P-DEV-9999",
        "head_sha": "b" * 40,
        "references": [
            {
                "type": "ci_run",
                "ref": "github-actions:12345",
                "status": "PASS",
                "summary": "required checks green",
            }
        ],
    }
    Draft7Validator(_schema("evidence-reference.schema.json")).validate(evidence)

    with_raw_log = copy.deepcopy(evidence)
    with_raw_log["raw_log"] = "large duplicated CI output"
    errors = list(
        Draft7Validator(_schema("evidence-reference.schema.json")).iter_errors(with_raw_log)
    )
    assert errors, "raw log payloads must not be part of the evidence-reference contract"


def test_bootstrap_hot_context_is_under_budget() -> None:
    budget = _yaml(CONTROL_ROOT / "context-budget.yaml")
    total = sum((REPO_ROOT / path).stat().st_size for path in budget["default_hot_files"])
    assert total <= budget["limits"]["bootstrap_hot_state_max"]


def test_legacy_no_loss_transition_remains_fail_closed() -> None:
    compatibility = _yaml(CONTROL_ROOT / "legacy-compatibility.yaml")
    queue = _yaml(CONTROL_ROOT / "work-queue.yaml")

    assert compatibility["new_control_runtime_authoritative"] is False
    assert compatibility["legacy_open_work_authoritative_until_reconciled"] is True
    assert queue["authority_status"] == "bootstrap_non_authoritative_for_legacy_open_work"
    assert "require_explicit_crosswalk_before_retiring_any_legacy_open_work" in compatibility[
        "no_loss_rules"
    ]
