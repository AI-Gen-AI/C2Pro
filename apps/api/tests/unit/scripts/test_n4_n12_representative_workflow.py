"""No spill into S2/Clerk jobs and hard cost/call caps on the focal runner."""

from __future__ import annotations

import ast
import os
import subprocess
import sysconfig
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
    gate_step = next(s for s in steps if s.get("name", "").startswith("Independent oracle gate"))
    assert gate_step["if"] == "always()"
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



def test_spacy_cache_output_heredoc_writes_exact_newline(tmp_path: Path) -> None:
    """Run the actual CI heredoc: a literal backslash-n is not a line break."""
    workflow = yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)
    steps = workflow["jobs"]["n4-n12-real-ai-focal"]["steps"]
    step = next(
        s for s in steps if s["name"] == "Resolve spaCy model cache directory"
    )
    output = tmp_path / "github-output"
    completed = subprocess.run(
        ["bash"],
        input=step["run"],
        cwd=ROOT,
        env={**os.environ, "GITHUB_OUTPUT": str(output)},
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    expected = f"site={sysconfig.get_path('purelib')}\n".encode()
    assert output.read_bytes() == expected
    assert output.read_bytes().endswith(b"\x0a")
    assert b"\\n" not in output.read_bytes()


def test_representative_workflow_blocks_before_provider_when_spanish_ner_missing() -> None:
    """Privacy NER must load before the governed paid calls; no regex-only bypass."""
    workflow = yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)
    steps = workflow["jobs"]["n4-n12-real-ai-focal"]["steps"]
    names = [step["name"] for step in steps]
    privacy_step = "Fail closed if Spanish PII NER is unavailable"
    provider_step = "Execute N4 Sonnet then N12 adversarial and chained critiques"
    assert names.index(privacy_step) < names.index(provider_step)
    assert names.index("Install pinned Spanish spaCy model if missing") < names.index(privacy_step)
    assert names.index("Restore pinned Spanish spaCy model (privacy preflight)") < names.index(privacy_step)
    cache = next(step for step in steps if step["name"].startswith("Restore pinned Spanish"))
    assert "es_core_news_md*" in cache["with"]["path"]
    assert "3.7.0" in cache["with"]["key"]
    privacy_run = next(step["run"] for step in steps if step["name"] == privacy_step)
    assert 'spacy.load("es_core_news_md")' in privacy_run
    assert 'PiiAnonymizerService._get_analyzer() is not None' in privacy_run
    assert "bypass_anonymization" not in "\n".join(str(s.get("run", "")) for s in steps)
