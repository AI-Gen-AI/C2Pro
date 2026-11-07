"""Regression: the manual real-AI UAT must enable and verify the real CORE gates.

This test parses YAML only. It never dispatches CI, contacts AI, or writes a database.
"""

from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parents[5] / ".github/workflows/acc01-s2-live-ai-uat.yml"


def test_s3_real_ai_workflow_pins_feature_flags_and_checks_before_paid_provider():
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    job = workflow["jobs"]["integral-s1-s8"]
    env = job["env"]
    for flag in ("FEATURE_V3_COHERENCE_LLM", "FEATURE_V3_PROJECT_GRAPH"):
        value = env[flag]
        assert "integral_ai_mode == 'real-ai'" in value
        assert "'true' || 'false'" in value

    steps = job["steps"]
    names = [step["name"] for step in steps]
    gate_name = "Require effective N8 and ProjectGraph flags for tenant A (real-ai only)"
    provider_name = "Require genuine noncached Anthropic provider response (real-ai only)"
    assert (
        names.index("Prepare the two tenants in the isolated database (no journey data)")
        < names.index(gate_name)
        < names.index(provider_name)
    )
    gate = steps[names.index(gate_name)]
    assert gate["if"] == "github.event.inputs.integral_ai_mode == 'real-ai'"
    assert "TenantFlagsService" in gate["run"]
    assert "feature_v3_coherence_llm" in gate["run"]
    assert "settings.feature_v3_project_graph" in gate["run"]
    assert "settings.skip_hitl or settings.ai_mock" in gate["run"]
    # The gate starts in a fresh interpreter; previous CI steps do not share
    # SQLAlchemy's module-level session factory.
    assert "from src.core.database import get_raw_session, init_db" in gate["run"]
    assert gate["run"].index("await init_db()") < gate["run"].index("async with get_raw_session()")

    mode = steps[
        names.index("Enforce the mode and its guards (fail closed before anything is started)")
    ]
    assert "integral_confirm_real_ai_sha" in mode["run"]
    assert "GITHUB_SHA" in mode["run"]
