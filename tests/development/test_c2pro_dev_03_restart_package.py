from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / ".c2pro" / "work" / "C2PRO-DEV-03.yaml"
READINESS = ROOT / "validation" / "development" / "c2pro-dev-03-principal-worker-readiness-v2.yaml"
CURRENT = ROOT / ".c2pro" / "control" / "current.yaml"
QUEUE = ROOT / ".c2pro" / "control" / "work-queue.yaml"


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_dev03_restart_package_is_fail_closed_before_activation() -> None:
    readiness = _load(READINESS)
    current = _load(CURRENT)
    queue = _load(QUEUE)

    assert readiness["status"] == "PLANNED_RESTART_PACKAGE_EXECUTION_NOT_AUTHORIZED"
    activation = readiness["activation"]
    assert activation["canonical_current_state_mutated"] is False
    assert activation["canonical_queue_work_ref_mutated"] is False
    assert activation["worker_execution_authorized"] is False
    assert activation["provider_invocation_authorized"] is False
    assert activation["standing_authority_authorized"] is False

    assert "C2PRO-DEV-03" not in current.get("active_work", [])
    queue_item = next(item for item in queue["items"] if item["work_id"] == "C2PRO-DEV-03")
    assert queue_item["work_ref"] is None


def test_dev03_separates_principal_class_route_role_and_job_authority() -> None:
    readiness = _load(READINESS)
    principles = readiness["principles"]

    assert principles["principal_capability_is_not_route_qualification"] is True
    assert principles["route_qualification_is_not_role_eligibility"] is True
    assert principles["role_eligibility_is_not_current_job_authority"] is True
    assert principles["principal_status_does_not_bypass_route_health"] is True

    codex = readiness["principal_workers"]["codex"]
    claude = readiness["principal_workers"]["claude_code"]

    assert codex["principal_capable"] is True
    assert claude["principal_capable"] is True
    assert codex["current_qualified_roles"] == ["BACKEND_ENGINEER"]
    assert claude["current_qualified_roles"] == [
        "SOFTWARE_ARCHITECT",
        "SYSTEM_COHERENCE_REVIEWER",
    ]
    assert set(codex["current_qualified_roles"]) != set(claude["current_qualified_roles"])
    assert codex["standing_authority"] is False
    assert claude["standing_authority"] is False
    assert codex["fresh_job_authority_required"] is True
    assert claude["fresh_job_authority_required"] is True


def test_dev03_claude_route_health_fails_closed() -> None:
    readiness = _load(READINESS)
    claude = readiness["principal_workers"]["claude_code"]

    assert claude["route_qualification_observed"] == "QUALIFIED_BOUNDED"
    assert claude["route_health_observed"] == "BLOCKED_REQUALIFICATION"
    assert claude["live_routable_observed"] is False
    assert (
        readiness["qualification_slices"]["DEV_03R4_CLAUDE_ARCH_COHERENCE"]
        == "BLOCKED_PENDING_ROUTE_HEALTH_REVALIDATION"
    )


def test_dev03_handoff_preserves_work_but_does_not_launder_role() -> None:
    readiness = _load(READINESS)
    handoff = readiness["handoff_contract"]

    for field in (
        "work_id",
        "base_sha",
        "objective",
        "scope",
        "out_of_scope",
        "invariants",
        "acceptance_criteria",
        "completed_work",
        "remaining_work",
        "findings",
        "evidence_refs",
    ):
        assert field in handoff["preserve"]

    reassignment = handoff["reassignment"]
    assert reassignment["worker_change_requires_explicit_transition"] is True
    assert reassignment["role_change_requires_explicit_transition"] is True
    assert reassignment["receiving_route_must_support_role"] is True
    assert reassignment["silent_scope_change"] is False


def test_dev03_work_envelope_keeps_both_principals_eligible_without_selecting_one() -> None:
    work = _load(WORK)
    selection = work["worker_selection"]

    assert work["work_id"] == "C2PRO-DEV-03"
    assert work["review_policy"] == "independent_principal"
    assert selection["eligible_principals"] == ["claude_code", "codex"]
    assert selection["eligible_subordinates"] == []
    assert selection["selected"] is None
