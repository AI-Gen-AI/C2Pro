"""No spill into S2/Clerk jobs and hard cost/call caps on the focal runner."""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[5]
WORKFLOW = ROOT / ".github/workflows/acc01-s2-live-ai-uat.yml"


def test_representative_workflow_is_exact_sha_and_mutually_exclusive() -> None:
    w = yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)
    assert len(w["on"]["workflow_dispatch"]["inputs"]) == 10
    jobs = w["jobs"]
    focal = jobs["n4-n12-real-ai-focal"]
    assert "github.event.inputs.n4_n12_focused_sha == github.sha" in focal["if"]
    assert "github.ref_name == 'release/core-candidate-20261108'" in focal["if"]
    for name, job in jobs.items():
        if name != "n4-n12-real-ai-focal":
            assert "n4_n12_focused_sha == ''" in job["if"], name
    assert len(jobs) == 7
    env = focal["env"]
    assert env["AI_MAX_TOKENS_OUTPUT"] == "8192"
    assert env["C2PRO_AI_GOVERNOR_MAX_CALLS"] == "3"
    assert env["C2PRO_AI_GOVERNOR_MAX_USD"] == "1.0"
    assert env["C2PRO_AI_MOCK"] == "0"
    assert env["C2PRO_EMBEDDINGS_MOCK"] == "1"
    assert "S2_E2E_ANTHROPIC_API_KEY" in env["ANTHROPIC_API_KEY"]


def test_representative_workflow_steps_well_formed_and_script_is_scoped() -> None:
    w = yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)
    steps = w["jobs"]["n4-n12-real-ai-focal"]["steps"]
    scripts = "\n".join(str(step.get("run", "")) for step in steps)
    assert "scripts/n4_n12_representative_eval.py" in scripts
    assert "scripts/n4_n12_real_ai_eval.py" not in scripts
    assert "assert count == 3 and cap == 1.0" in scripts
    assert "max_retries" not in scripts
    assert "n4-n12-representative-evaluation.json" in scripts
    assert "scripts/n4_n12_representative_gate.py" in scripts
    assert "Independent oracle gate" in str(steps)
    for step in steps:
        if "run" not in step:
            continue
        command = step["run"]
        check = subprocess.run(["bash", "-n"], input=command, text=True, capture_output=True)
        assert check.returncode == 0, (step["name"], check.stderr)
        if "python - <<'PY2'" in command:
            embedded = command.split("python - <<'PY2'", 1)[1].split("\nPY2", 1)[0].strip()
            ast.parse(embedded)
