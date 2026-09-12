from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = ROOT / "scripts" / "development" / "validate_c2pro_control.py"
SPEC = importlib.util.spec_from_file_location("validate_c2pro_control", VALIDATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def test_canonical_control_plane_validates_and_meets_hot_budget() -> None:
    total = validator.validate()
    current = validator.load_yaml(ROOT / ".c2pro" / "control" / "current.yaml")
    assert total <= current["context_budget"]["bootstrap_hot_max_bytes"]
    assert total <= 16 * 1024


def test_work_queue_contains_only_open_work() -> None:
    queue = validator.load_yaml(ROOT / ".c2pro" / "control" / "work-queue.yaml")
    assert queue["items"]
    assert {item["status"] for item in queue["items"]} <= validator.OPEN_STATES
    assert all(item["status"] != "completed" for item in queue["items"])
    assert all(item["work_id"] != "C2PRO-DEV-01" for item in queue["items"])


def _synthetic_active_work_fixture(monkeypatch: pytest.MonkeyPatch) -> tuple[dict, dict, dict]:
    """Explicit synthetic active-work fixture, independent of whichever
    work_id (if any) is live-canonical-active today. These tests exercise a
    structural property of the work-envelope shape itself (model/provider
    independence, identity stability across principal reassignment) --
    that property must hold regardless of what is currently active, and
    must not silently stop being exercised once active_work is legitimately
    empty (e.g. right after a legacy closure)."""
    work = {
        "work_id": "C2PRO-DEV-SYNTH",
        "role": "orchestrator",
        "base_sha": "b" * 40,
        "scope": ["synthetic"],
        "out_of_scope": [],
        "acceptance_criteria": ["synthetic"],
        "worker_selection": {
            "selected": None,
            "eligible_principals": list(validator.PRINCIPAL_WORKERS),
            "eligible_subordinates": [],
        },
    }
    current = {"baseline": {"main_sha": "b" * 40}, "active_work": ["C2PRO-DEV-SYNTH"]}
    queue = {"items": [{"work_id": "C2PRO-DEV-SYNTH", "work_ref": "synthetic/work.yaml", "role": "orchestrator"}]}

    def fake_load(path: Path):
        if str(path).endswith("synthetic/work.yaml"):
            return work
        raise AssertionError(f"unexpected load_yaml call in this synthetic fixture: {path}")

    monkeypatch.setattr(validator, "load_yaml", fake_load)
    return current, queue, work


def test_active_work_identity_is_model_independent(monkeypatch: pytest.MonkeyPatch) -> None:
    current, queue, _work = _synthetic_active_work_fixture(monkeypatch)
    active_id = current["active_work"][0]
    item = next(item for item in queue["items"] if item["work_id"] == active_id)
    work = validator.load_yaml(ROOT / item["work_ref"])
    assert work["work_id"] == active_id
    assert work["base_sha"] == current["baseline"]["main_sha"]
    assert work["worker_selection"]["selected"] is None
    assert work["role"] == item["role"]
    assert "model" not in work
    assert "provider" not in work


def test_same_work_can_move_between_principals_without_identity_change(monkeypatch: pytest.MonkeyPatch) -> None:
    current, queue, _work = _synthetic_active_work_fixture(monkeypatch)
    active_id = current["active_work"][0]
    item = next(item for item in queue["items"] if item["work_id"] == active_id)
    work = validator.load_yaml(ROOT / item["work_ref"])
    initial_identity = validator.stable_work_identity(work)

    claude_assignment = copy.deepcopy(work)
    claude_assignment["worker_selection"]["selected"] = "claude_code"
    codex_assignment = copy.deepcopy(work)
    codex_assignment["worker_selection"]["selected"] = "codex"

    assert validator.stable_work_identity(claude_assignment) == initial_identity
    assert validator.stable_work_identity(codex_assignment) == initial_identity
    assert claude_assignment["worker_selection"]["selected"] != codex_assignment["worker_selection"]["selected"]


def test_canonical_roles_are_model_and_worker_neutral() -> None:
    profiles = validator.validate_role_profiles()
    assert set(profiles) == validator.CANONICAL_ROLES
    for profile in profiles.values():
        assert not (validator.mapping_keys(profile) & validator.ROLE_FORBIDDEN_KEYS)


def test_only_claude_and_codex_are_principal_gate_eligible() -> None:
    profiles = validator.validate_role_profiles()
    routing = validator.validate_routing(profiles)
    workers = routing["workers"]
    principal_gate_eligible = {worker_id for worker_id, config in workers.items() if config["principal_gate_eligible"]}
    assert principal_gate_eligible == {"claude_code", "codex"}
    for worker_id in validator.SUBORDINATE_WORKERS:
        assert workers[worker_id]["class"] == "subordinate"
        assert workers[worker_id]["principal_gate_eligible"] is False


def test_material_self_approval_is_forbidden() -> None:
    profiles = validator.validate_role_profiles()
    routing = validator.validate_routing(profiles)
    review_policy = validator.validate_review_policy()
    assert routing["principal_gate"]["material_reviewer_must_differ_from_implementation_worker"] is True
    assert routing["principal_gate"]["same_worker_dual_role_does_not_satisfy_independence"] is True
    assert review_policy["principal_independence"]["material_or_higher_same_worker_review_forbidden"] is True


def test_high_risk_work_requires_principal_challenger_and_synthesis() -> None:
    policy = validator.validate_review_policy()
    for risk in ("architecture", "security", "high_blast_radius"):
        config = policy["risk_classes"][risk]
        assert config["independent_principal_review"] == "required"
        assert config["challenger"] == "required"
        assert config["orchestrator_synthesis"] is True


def test_open_ended_model_debate_is_not_default() -> None:
    policy = validator.validate_review_policy()
    assert policy["challenger_policy"]["open_ended_debate_default"] is False
    assert policy["challenger_policy"]["directed_adjudication_round_max"] == 1


def test_queue_validator_rejects_completed_history(monkeypatch: pytest.MonkeyPatch) -> None:
    current = validator.load_yaml(ROOT / ".c2pro" / "control" / "current.yaml")
    queue = validator.load_yaml(ROOT / ".c2pro" / "control" / "work-queue.yaml")
    invalid = copy.deepcopy(queue)
    invalid["items"][0]["status"] = "completed"
    real_load = validator.load_yaml

    def fake_load(path: Path):
        if path == validator.CONTROL / "work-queue.yaml":
            return invalid
        return real_load(path)

    monkeypatch.setattr(validator, "load_yaml", fake_load)
    with pytest.raises(ValueError, match="historical/completed status forbidden"):
        validator.validate_queue(current)


def test_current_validator_rejects_completed_history_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    current = validator.load_yaml(ROOT / ".c2pro" / "control" / "current.yaml")
    invalid = copy.deepcopy(current)
    invalid["history"]["completed_work_in_hot_state"] = True
    real_load = validator.load_yaml

    def fake_load(path: Path):
        if path == validator.CONTROL / "current.yaml":
            return invalid
        return real_load(path)

    monkeypatch.setattr(validator, "load_yaml", fake_load)
    with pytest.raises(ValueError, match="completed history is forbidden"):
        validator.validate_current()


def test_routing_validator_rejects_subordinate_principal_promotion(monkeypatch: pytest.MonkeyPatch) -> None:
    profiles = validator.validate_role_profiles()
    routing = validator.load_yaml(ROOT / ".c2pro" / "control" / "routing.yaml")
    invalid = copy.deepcopy(routing)
    invalid["workers"]["gemini_cli"]["principal_gate_eligible"] = True
    real_load = validator.load_yaml

    def fake_load(path: Path):
        if path == validator.CONTROL / "routing.yaml":
            return invalid
        return real_load(path)

    monkeypatch.setattr(validator, "load_yaml", fake_load)
    with pytest.raises(ValueError, match="cannot satisfy principal gate"):
        validator.validate_routing(profiles)


def test_review_policy_rejects_unbounded_debate(monkeypatch: pytest.MonkeyPatch) -> None:
    policy = validator.load_yaml(ROOT / ".c2pro" / "control" / "review-policy.yaml")
    invalid = copy.deepcopy(policy)
    invalid["challenger_policy"]["open_ended_debate_default"] = True
    real_load = validator.load_yaml

    def fake_load(path: Path):
        if path == validator.CONTROL / "review-policy.yaml":
            return invalid
        return real_load(path)

    monkeypatch.setattr(validator, "load_yaml", fake_load)
    with pytest.raises(ValueError, match="open-ended debate must remain disabled"):
        validator.validate_review_policy()


def test_handoff_proof_skipped_when_active_work_is_empty() -> None:
    """A legitimate canonical state exists right after a work item closes and
    before the next one is picked up: active_work == []. There is no
    principal to hand work off between, so the proof is inapplicable, not
    violated -- this must not raise."""
    current = {"active_work": []}
    queue = {"items": []}
    routing = validator.load_yaml(ROOT / ".c2pro" / "control" / "routing.yaml")
    validator.validate_identity_preserving_principal_handoff(current, queue, routing)


def test_handoff_proof_still_enforced_for_invalid_non_empty_active_work() -> None:
    """The empty-active-work allowance must not become a general escape
    hatch: a genuinely broken active-work entry must still fail exactly as
    before."""
    current = {"active_work": ["C2PRO-DEV-BROKEN"]}
    queue = {"items": [{"work_id": "C2PRO-DEV-BROKEN", "work_ref": None}]}
    routing = validator.load_yaml(ROOT / ".c2pro" / "control" / "routing.yaml")
    with pytest.raises(ValueError, match="active work requires work_ref"):
        validator.validate_identity_preserving_principal_handoff(current, queue, routing)


def test_handoff_proof_passes_for_valid_active_work(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: a genuinely valid single active work item must still pass
    the full identity-preserving-handoff proof."""
    work = {
        "work_id": "C2PRO-DEV-SYNTH",
        "role": "orchestrator",
        "base_sha": "a" * 40,
        "scope": ["synthetic"],
        "out_of_scope": [],
        "acceptance_criteria": ["synthetic"],
        "worker_selection": {
            "eligible_principals": list(validator.PRINCIPAL_WORKERS),
            "eligible_subordinates": [],
            "selected": None,
        },
    }
    current = {"active_work": ["C2PRO-DEV-SYNTH"]}
    queue = {"items": [{"work_id": "C2PRO-DEV-SYNTH", "work_ref": "synthetic/work.yaml", "role": "orchestrator"}]}
    routing = validator.load_yaml(ROOT / ".c2pro" / "control" / "routing.yaml")

    def fake_load(path: Path):
        if str(path).endswith("synthetic/work.yaml"):
            return work
        raise AssertionError(f"unexpected load_yaml call in this synthetic fixture: {path}")

    monkeypatch.setattr(validator, "load_yaml", fake_load)
    validator.validate_identity_preserving_principal_handoff(current, queue, routing)


def test_other_invariants_still_enforced_when_active_work_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """The empty-active-work skip must be narrowly scoped to the handoff
    proof ONLY: every other control-plane invariant must keep running, and
    keep failing, on a genuinely broken input elsewhere in the pipeline."""
    current = validator.load_yaml(ROOT / ".c2pro" / "control" / "current.yaml")
    empty_current = dict(current)
    empty_current["active_work"] = []

    broken_review_policy = copy.deepcopy(
        validator.load_yaml(ROOT / ".c2pro" / "control" / "review-policy.yaml")
    )
    broken_review_policy["challenger_policy"]["open_ended_debate_default"] = True

    real_load = validator.load_yaml

    def fake_load(path: Path):
        if path == validator.CONTROL / "current.yaml":
            return empty_current
        if path == validator.CONTROL / "review-policy.yaml":
            return broken_review_policy
        return real_load(path)

    monkeypatch.setattr(validator, "load_yaml", fake_load)
    with pytest.raises(ValueError, match="open-ended debate must remain disabled"):
        validator.validate()


def test_validate_succeeds_fully_when_active_work_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """The full validate() pipeline -- schema, current, queue, work
    envelopes, roles, routing, review policy, the now-skippable handoff
    proof, legacy transition, workspace policy, context budget -- must
    complete successfully end to end when active_work is legitimately
    empty (e.g. immediately after C2PRO-DEV-02's legacy closure)."""
    current = validator.load_yaml(ROOT / ".c2pro" / "control" / "current.yaml")
    empty_current = dict(current)
    empty_current["active_work"] = []
    real_load = validator.load_yaml

    def fake_load(path: Path):
        if path == validator.CONTROL / "current.yaml":
            return empty_current
        return real_load(path)

    monkeypatch.setattr(validator, "load_yaml", fake_load)
    total = validator.validate()
    assert total > 0


def test_legacy_sources_are_noncanonical_and_not_deleted_early() -> None:
    policy = validator.load_yaml(ROOT / ".c2pro" / "control" / "legacy-compatibility.yaml")
    assert policy["canonical_write_target"] == ".c2pro"
    for source in policy["legacy_sources"].values():
        assert source["canonical"] is False
        assert source["delete_before_reconciliation"] is False


def test_schema_artifacts_are_closed_draft_2020_12_objects() -> None:
    validator.validate_schema_artifacts()


# ---------------------------------------------------------------------------
# --verify-against-git (G2 continuation, Task 4; corrected post-merge
# semantics, Gemini-identified self-reference defect fix).
#
# baseline.main_sha means "the authoritative main commit consumed as INPUT
# to the current reconciliation/work cycle" -- NOT "the SHA of the commit
# containing current.yaml". The two are indistinguishable while active work
# is in flight (nothing should have advanced main out from under it, so
# exact equality is the right, tight invariant) but are NECESSARILY
# different immediately after current.yaml's own change merges to main:
# the merge commit (or squash commit) that carries current.yaml's new
# baseline value cannot itself be that value -- it doesn't exist yet at
# commit time. Once active_work is empty (the legitimate post-merge/idle
# state), an ancestor relationship is correct and sufficient; divergence
# (not even an ancestor) is never acceptable in either state.
# ---------------------------------------------------------------------------

import subprocess  # noqa: E402


def _fake_git(responses: dict[tuple, object]):
    def _run(cmd: list[str]) -> str:
        key = tuple(cmd)
        if key not in responses:
            raise AssertionError(f"Unexpected command: {cmd}")
        value = responses[key]
        if isinstance(value, Exception):
            raise value
        return value

    return _run


# --- 1. active_work non-empty + exact equality => PASS ---------------------
def test_baseline_matches_git_truth_passes_on_exact_match_with_active_work() -> None:
    current = {"baseline": {"main_sha": "abc123"}, "active_work": ["C2PRO-DEV-99"]}
    run_fn = _fake_git({("git", "rev-parse", "origin/main"): "abc123"})
    validator.validate_baseline_matches_git_truth(current, run_fn=run_fn)  # must not raise


# --- 2. active_work non-empty + recorded ancestor but stale => FAIL --------
def test_baseline_matches_git_truth_rejects_stale_baseline_with_active_work() -> None:
    """Active work requires the baseline to exactly match origin/main -- any
    advancement of main requires explicit reconciliation before active work
    may continue."""
    current = {"baseline": {"main_sha": "OLD_SHA"}, "active_work": ["C2PRO-DEV-99"]}
    run_fn = _fake_git(
        {
            ("git", "rev-parse", "origin/main"): "NEW_SHA",
            ("git", "merge-base", "--is-ancestor", "OLD_SHA", "origin/main"): "",
        }
    )
    with pytest.raises(ValueError, match="active work"):
        validator.validate_baseline_matches_git_truth(current, run_fn=run_fn)


# --- 3. active_work empty + exact equality => PASS --------------------------
def test_baseline_matches_git_truth_passes_on_exact_match_with_no_active_work() -> None:
    current = {"baseline": {"main_sha": "abc123"}, "active_work": []}
    run_fn = _fake_git({("git", "rev-parse", "origin/main"): "abc123"})
    validator.validate_baseline_matches_git_truth(current, run_fn=run_fn)  # must not raise


# --- 4. active_work empty + recorded valid ancestor => PASS (the core fix) -
def test_baseline_matches_git_truth_allows_ancestor_baseline_when_idle() -> None:
    """The self-reference fix: a legitimate post-merge/idle state (no active
    work) where the recorded baseline is an ancestor of -- but not equal
    to -- origin/main must PASS, not fail. This is the exact situation
    current.yaml is in immediately after its own change merges to main: the
    merge/squash commit that carries the new baseline value cannot equal
    that value at commit time."""
    current = {"baseline": {"main_sha": "OLD_SHA"}, "active_work": []}
    run_fn = _fake_git(
        {
            ("git", "rev-parse", "origin/main"): "NEW_SHA",
            ("git", "merge-base", "--is-ancestor", "OLD_SHA", "origin/main"): "",
        }
    )
    validator.validate_baseline_matches_git_truth(current, run_fn=run_fn)  # must not raise


# --- 5. active_work empty + diverged SHA => FAIL ----------------------------
def test_baseline_matches_git_truth_rejects_diverged_baseline_when_idle() -> None:
    current = {"baseline": {"main_sha": "OLD_SHA"}, "active_work": []}
    run_fn = _fake_git(
        {
            ("git", "rev-parse", "origin/main"): "NEW_SHA",
            ("git", "merge-base", "--is-ancestor", "OLD_SHA", "origin/main"): subprocess.CalledProcessError(1, []),
        }
    )
    with pytest.raises(ValueError, match="diverged"):
        validator.validate_baseline_matches_git_truth(current, run_fn=run_fn)


def test_baseline_matches_git_truth_rejects_diverged_baseline_with_active_work() -> None:
    """Divergence MUST always fail, independent of active_work state -- it
    is never a legitimate idle/post-merge condition, only a corrupted or
    hand-typed value."""
    current = {"baseline": {"main_sha": "OLD_SHA"}, "active_work": ["C2PRO-DEV-99"]}
    run_fn = _fake_git(
        {
            ("git", "rev-parse", "origin/main"): "NEW_SHA",
            ("git", "merge-base", "--is-ancestor", "OLD_SHA", "origin/main"): subprocess.CalledProcessError(1, []),
        }
    )
    with pytest.raises(ValueError, match="diverged"):
        validator.validate_baseline_matches_git_truth(current, run_fn=run_fn)


# --- 6. missing/invalid SHA => FAIL -----------------------------------------
def test_baseline_matches_git_truth_rejects_missing_sha() -> None:
    """A missing baseline.main_sha must fail fast, before ever shelling out
    to git -- there is nothing to check reachability for."""
    current = {"baseline": {}, "active_work": []}

    def _run(cmd: list[str]) -> str:
        raise AssertionError(f"git must not be invoked for a missing SHA: {cmd}")

    with pytest.raises(ValueError, match="missing"):
        validator.validate_baseline_matches_git_truth(current, run_fn=_run)


def test_baseline_matches_git_truth_rejects_invalid_unreachable_sha() -> None:
    """A syntactically-present but unreachable/nonexistent SHA (never a real
    commit in this repository's history) must fail exactly like a genuine
    divergence -- it is not, and can never become, an ancestor."""
    current = {"baseline": {"main_sha": "not_a_real_object"}, "active_work": []}
    run_fn = _fake_git(
        {
            ("git", "rev-parse", "origin/main"): "NEW_SHA",
            (
                "git",
                "merge-base",
                "--is-ancestor",
                "not_a_real_object",
                "origin/main",
            ): subprocess.CalledProcessError(128, []),
        }
    )
    with pytest.raises(ValueError, match="diverged"):
        validator.validate_baseline_matches_git_truth(current, run_fn=run_fn)


# --- 7. simulated squash merge of G2 => PASS after fix ----------------------
def test_baseline_matches_git_truth_passes_after_simulated_squash_merge() -> None:
    """Simulates the exact scenario Gemini identified: this branch's
    baseline.main_sha (the pre-merge origin/main tip it was reconciled
    against) is committed as part of the branch; a squash merge then
    creates ONE new commit on origin/main whose sole parent is that
    pre-merge tip. The recorded baseline is therefore an ancestor, never
    equal, of the new tip -- and with no active work in flight
    post-reconciliation, that must be accepted."""
    pre_merge_main = "32eba9431ddaab198088a09fe9294ae5ecc38318"
    squash_commit = "f2380b0dec5db7c3768394be1d25ee2c4541683f"
    current = {"baseline": {"main_sha": pre_merge_main}, "active_work": []}
    run_fn = _fake_git(
        {
            ("git", "rev-parse", "origin/main"): squash_commit,
            ("git", "merge-base", "--is-ancestor", pre_merge_main, "origin/main"): "",
        }
    )
    validator.validate_baseline_matches_git_truth(current, run_fn=run_fn)  # must not raise


# --- 8. simulated normal (two-parent) merge commit => PASS after fix -------
def test_baseline_matches_git_truth_passes_after_simulated_normal_merge_commit() -> None:
    """Same self-reference situation, but via a genuine two-parent merge
    commit rather than a squash -- git merge-base --is-ancestor treats both
    topologies identically (reachable via first-parent history either way),
    so the same fix covers both merge strategies without special-casing."""
    pre_merge_main = "32eba9431ddaab198088a09fe9294ae5ecc38318"
    merge_commit = "abc000def111abc000def111abc000def111abc"
    current = {"baseline": {"main_sha": pre_merge_main}, "active_work": []}
    run_fn = _fake_git(
        {
            ("git", "rev-parse", "origin/main"): merge_commit,
            ("git", "merge-base", "--is-ancestor", pre_merge_main, "origin/main"): "",
        }
    )
    validator.validate_baseline_matches_git_truth(current, run_fn=run_fn)  # must not raise


def _real_current_main_sha() -> str:
    current = validator.load_yaml(ROOT / ".c2pro" / "control" / "current.yaml")
    return current["baseline"]["main_sha"]


def test_validate_accepts_verify_against_git_flag_with_injectable_run_fn() -> None:
    """validate() must thread verify_against_git + run_fn through without
    otherwise changing behavior when the flag is False (the default)."""
    total_without_flag = validator.validate()
    total_with_matching_git = validator.validate(
        verify_against_git=True,
        run_fn=_fake_git({("git", "rev-parse", "origin/main"): _real_current_main_sha()}),
    )
    assert total_without_flag == total_with_matching_git


def test_main_supports_verify_against_git_cli_flag() -> None:
    exit_code = validator.main(
        ["--verify-against-git"],
        run_fn=_fake_git({("git", "rev-parse", "origin/main"): _real_current_main_sha()}),
    )
    assert exit_code == 0


def test_main_verify_against_git_passes_now_that_the_drift_is_reconciled() -> None:
    """Regression against the REAL repository: current.yaml's baseline was
    genuinely stale relative to origin/main until the C2PRO-DEV-02 legacy
    closure (core.legacy_closure) reconciled it -- see
    .c2pro/control/reconciliation-history.yaml. Uses the real default
    git_run_fn -- no fake -- so this is a true end-to-end proof the CLI
    wiring works against real git, and that the drift this check exists to
    catch is now actually resolved, not merely tolerated."""
    exit_code = validator.main(["--verify-against-git"])
    assert exit_code == 0
