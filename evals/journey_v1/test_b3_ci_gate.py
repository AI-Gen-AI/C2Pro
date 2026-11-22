"""B3 · the evals/journey_v1 tests are a REQUIRED CI gate.

Fails if the job is removed from ci.yml, stops gating ``ci-status``, loses
its coverage floor or skip guard, or gains access to provider secrets.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
CI = REPO / ".github" / "workflows" / "ci.yml"
JOB = "evals-journey-v1"
MIN_TESTS = 65  # tests collected under evals/journey_v1 when B3 landed
COVERAGE_FLOOR = 97  # measured 99% on the B3 code; never lower it to pass


def _workflow() -> dict:
    return yaml.safe_load(CI.read_text(encoding="utf-8"))


def _job_text(job: dict) -> str:
    return yaml.safe_dump(job, sort_keys=False)


def test_detect_changes_exposes_an_evals_filter():
    detect = _workflow()["jobs"]["detect-changes"]
    assert "evals_journey_v1" in detect["outputs"]
    filters = next(s for s in detect["steps"] if s.get("id") == "filter")["with"]["filters"]
    evals = yaml.safe_load(filters)["evals_journey_v1"]
    assert "evals/journey_v1/**" in evals
    assert "apps/api/src/analysis/domain/n4_failure_kinds.py" in evals
    assert "apps/api/scripts/real_ai_governor/**" in evals
    assert ".github/workflows/ci.yml" in evals


def test_job_runs_all_evals_tests_with_coverage_floor_and_no_skips():
    job = _workflow()["jobs"][JOB]
    text = _job_text(job)
    assert "evals_journey_v1 == 'true'" in job["if"]
    assert "python -m pytest evals/journey_v1" in text
    floors = [int(v) for v in re.findall(r"--fail-under=(\d+)", text)]
    assert floors
    assert min(floors) >= COVERAGE_FLOOR
    # junit guard: any skip, failure or a drop below MIN_TESTS fails the job
    assert "if skipped or broken or tests < minimum:" in text
    assert int(job["env"]["MIN_TESTS"]) >= MIN_TESTS


def test_job_has_no_provider_secrets_or_network_keys():
    text = _job_text(_workflow()["jobs"][JOB])
    assert "ANTHROPIC_API_KEY" not in text
    assert "OPENAI_API_KEY" not in text
    assert re.findall(r"secrets\.([A-Z_]+)", text) in ([], ["CODECOV_TOKEN"])


def test_ci_status_requires_the_evals_job():
    status = _workflow()["jobs"]["ci-status"]
    assert JOB in status["needs"]
    gate = next(s for s in status["steps"] if s.get("name") == "Evaluate required gates")
    assert gate["env"]["RESULT_EVALS_JOURNEY_V1"] == "${{ needs.evals-journey-v1.result }}"
    required = gate["run"].split("REQUIRED_JOBS=(", 1)[1].split(")", 1)[0]
    assert '"evals-journey-v1:$RESULT_EVALS_JOURNEY_V1"' in required
