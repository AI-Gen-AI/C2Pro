"""Workflow guard for operator-only real document flow execution.

Suite ID: TASK-OPS-DOCFLOW-012
"""

from __future__ import annotations

from pathlib import Path

WORKFLOW_PATH = (
    Path(__file__).resolve().parents[4]
    / ".github"
    / "workflows"
    / "real-document-operability.yml"
)


def test_real_document_operability_workflow_is_operator_dispatch_only() -> None:
    """Real-document flow must not run as a required PR or push gate."""
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    trigger_block = workflow.split("permissions:", maxsplit=1)[0]

    assert "workflow_dispatch:" in trigger_block
    assert "pull_request:" not in trigger_block
    assert "push:" not in trigger_block


def test_real_document_pytest_gate_requires_explicit_operator_input() -> None:
    """The real-document pytest step must be guarded by operator confirmation."""
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "run_real_document_flow" in workflow
    assert "github.event_name == 'workflow_dispatch'" in workflow
    assert "inputs.run_real_document_flow == 'true'" in workflow
    assert "Real Document Flow | Needs real fixtures + env | No (operator)" in workflow


# ── ACC-01 real-AI functional pilots (manual, paid): their guards are pinned, not trusted ─────────────────────────────────
def _jobs() -> dict:
    import yaml

    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))["jobs"]


def _steps(job: dict) -> list[dict]:
    return job["steps"]


def test_the_real_ai_vertical_needs_the_flag_the_exact_sha_and_the_owners_phrase() -> None:
    condition = _jobs()["real-ai-hitl-vertical"]["if"]
    assert "github.event_name == 'workflow_dispatch'" in condition
    assert "inputs.run_real_ai_hitl_vertical == true" in condition
    assert "inputs.confirm_candidate_sha == github.sha" in condition
    # The owner's phrase is mandatory for the paid run; only the no-spend infrastructure check may skip it.
    assert "(inputs.infrastructure_check_only == true || inputs.owner_authorization == 'OWNER-AUTHORIZED-REAL-AI-HITL-VERTICAL')" in condition


def test_the_infrastructure_check_cannot_reach_the_scenario_or_the_provider() -> None:
    steps = {s["name"]: s for s in _steps(_jobs()["real-ai-hitl-vertical"])}
    for name in (
        "Run the real-AI vertical (browser, REAL provider, human decisions, relogin)",
        "Verify independently in PostgreSQL and against the provider ledger",
    ):
        assert "inputs.infrastructure_check_only != true" in steps[name]["if"], name


def test_the_real_ai_vertical_is_real_for_inference_and_mocked_for_embeddings_and_cannot_skip_the_human_gate() -> None:
    env = _jobs()["real-ai-hitl-vertical"]["env"]
    assert (env["C2PRO_AI_MOCK"], env["C2PRO_EMBEDDINGS_MOCK"], env["C2PRO_SKIP_HITL"]) == ("0", "1", "0")
    assert "OPENAI_API_KEY" not in env, "no embeddings credential exists in this job"
    assert env["AI_MAX_TOKENS_OUTPUT"] == "4096"
    assert env["C2PRO_AI_GOVERNOR_LEDGER"].endswith("playwright-report/real-ai-governor-ledger.jsonl")


def test_every_python_process_that_can_reach_the_provider_loads_the_governor_and_it_is_checked_first() -> None:
    steps = {s["name"]: s for s in _steps(_jobs()["real-ai-hitl-vertical"])}
    governed = [n for n in steps if n.endswith(", governed") or n.startswith("AI call governor self-check")]
    assert len(governed) == 3, governed
    for name in governed:
        assert steps[name]["env"]["PYTHONPATH"].endswith("apps/api/scripts/real_ai_governor"), name
    order = list(steps)
    assert order.index("AI call governor self-check (no provider call)") < order.index("Start Celery worker (document_parsing), governed") < order.index("Start backend API, governed")
    run = steps["Run the real-AI vertical (browser, REAL provider, human decisions, relogin)"]["run"]
    assert "--retries=0" in run and "--workers=1" in run and "--project=real-ai-hitl" in run


def test_the_caps_have_hard_ceilings_and_the_verifier_runs_even_when_the_browser_fails() -> None:
    steps = {s["name"]: s for s in _steps(_jobs()["real-ai-hitl-vertical"])}
    guards = steps["Enforce the experiment guards (fail closed before anything starts)"]["run"]
    assert "1 <= calls <= 20" in guards and "0 < usd <= 2.0" in guards
    verify = steps["Verify independently in PostgreSQL and against the provider ledger"]
    assert verify["if"].startswith("${{ always()"), "runs even when the browser step failed"
    inputs = yaml_inputs()
    assert inputs["governor_max_calls"]["default"] == "12" and inputs["governor_max_usd"]["default"] == "1.00"


def yaml_inputs() -> dict:
    import yaml

    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))[True]["workflow_dispatch"]["inputs"]


def test_the_gate_job_is_skipped_for_either_paid_pilot() -> None:
    condition = _jobs()["real-document-gate"]["if"]
    assert "run_s1_s2_real_ai_pilot" in condition and "run_real_ai_hitl_vertical" in condition


def test_no_paid_job_is_reachable_from_a_push_or_a_pull_request() -> None:
    for name in ("s1-s2-real-ai-pilot", "real-ai-hitl-vertical"):
        assert "workflow_dispatch" in _jobs()[name]["if"], name
