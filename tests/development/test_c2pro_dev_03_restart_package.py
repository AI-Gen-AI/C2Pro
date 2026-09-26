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


def test_dev03_codex_route_qualification_does_not_hide_provider_degradation() -> None:
    readiness = _load(READINESS)
    codex = readiness["principal_workers"]["codex"]

    assert codex["route_qualification_observed"] == "QUALIFIED_LIVE"
    assert codex["provider_invocation_state_observed"] == "DEGRADED_EXTERNAL_AUTH_PATH"
    assert codex["fresh_endpoint_preflight_required"] is True
    assert (
        readiness["qualification_slices"]["DEV_03R3_CODEX_BOUNDED_IMPLEMENTATION"]
        == "BLOCKED_PENDING_FRESH_ENDPOINT_PREFLIGHT"
    )


def test_dev03_material_promotion_is_blocked_without_principal_review_route() -> None:
    readiness = _load(READINESS)
    gate = readiness["principal_review_gate"]

    assert gate["current_status"] == "BLOCKED_NO_COMPATIBLE_LIVE_PRINCIPAL_REVIEW_ROUTE_PROVEN"
    assert gate["c2pro_authority_class_of_academy_reviewer"] == "SUBORDINATE"
    assert gate["subordinate_may_satisfy_c2pro_principal_gate"] is False
    assert gate["claude_independent_review_lead_qualification"] == "NOT_QUALIFIED"
    assert gate["material_same_worker_self_review_forbidden"] is True
    assert gate["qualification_inheritance_forbidden"] is True
    assert (
        readiness["qualification_slices"]["DEV_03R8_PRINCIPAL_REVIEW_ROUTE"]
        == "BLOCKED_NO_COMPATIBLE_ROUTE_PROVEN"
    )


def test_dev03_handoff_preserves_work_but_does_not_launder_role() -> None:
    readiness = _load(READINESS)
    handoff = readiness["handoff_contract"]

    for field in (
        "work_id",
        "role",
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
    assert reassignment["role_is_immutable_within_same_work"] is True
    assert reassignment["role_change_requires_new_or_child_work_identity"] is True
    assert reassignment["receiving_route_must_support_same_role"] is True
    assert reassignment["silent_scope_change"] is False
    assert (
        readiness["qualification_slices"]["DEV_03R7_SAME_ROLE_PRINCIPAL_HANDOFF"]
        == "BLOCKED_NO_SHARED_QUALIFIED_ROLE_ROUTE_PROVEN"
    )


def test_dev03_work_envelope_keeps_both_principals_eligible_without_selecting_one() -> None:
    work = _load(WORK)
    selection = work["worker_selection"]

    assert work["work_id"] == "C2PRO-DEV-03"
    assert work["review_policy"] == "independent_principal"
    assert selection["eligible_principals"] == ["claude_code", "codex"]
    assert selection["eligible_subordinates"] == []
    assert selection["selected"] is None
