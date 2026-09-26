#!/usr/bin/env python3
"""CI regression guard for unpinned ad-hoc pip installs."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List, Tuple

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

PIP_INSTALL_RE = re.compile(r"\bpip(?:\s+-m\s+pip)?\s+install\b", re.IGNORECASE)
ALLOW_REQUIREMENT = re.compile(r"pip\s+install\s+(-r|--requirement)\s+", re.IGNORECASE)
ALLOW_CONSTRAINT = re.compile(r"(-c|--constraint)\s+", re.IGNORECASE)
ALLOW_UPGRADE_PIP = re.compile(r"pip\s+install\s+--upgrade\s+pip\b", re.IGNORECASE)
ALLOW_EDITABLE = re.compile(r"pip\s+install\s+-e\s+", re.IGNORECASE)

BASELINE_EXCEPTIONS: List[Tuple[str, str]] = [
    (".github/actions/setup-python-backend/action.yml", "pip install python-magic"),
    (".github/workflows/qa-swarm.yml", "pip install python-magic"),
    (".github/workflows/real-document-operability.yml", "pip install python-magic"),
    (".github/workflows/i13-real-e2e-scheduled.yml", "pip install python-magic"),
    (".github/workflows/golden-corpus-evals.yml", 'pip install pyyaml "pydantic>=2.0" pytest'),
    (".github/workflows/openapi-drift.yml", "pip install pyyaml"),
    (".github/workflows/scheduled-drift-checks.yml", "pip install pytest pyyaml"),
    (".github/workflows/c2pro-development-control.yml", 'pip install "pyyaml==6.0.3" "pytest>=9.0.3"'),
    (".github/workflows/c2pro-product-control-guard.yml", 'python -m pip install --disable-pip-version-check "pyyaml==6.0.3"'),
    (".github/workflows/release.yml", 'python -m pip install --quiet pyyaml'),
    (".github/workflows/dependency-audit.yml", "pip install pip-audit"),
    (".github/workflows/ci.yml", 'pip install "$(grep -E \'^ruff==\' apps/api/requirements.txt)"'),
    (".github/workflows/ci.yml", 'pip install "https://github.com/explosion/spacy-models/releases/download/es_core_news_md-3.7.0/es_core_news_md-3.7.0-py3-none-any.whl"'),
    (".github/workflows/evaluation-regression.yml", "pip install pyyaml"),
]

def find_runs(node):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "run" and isinstance(v, str):
                yield v
            elif isinstance(v, (dict, list)):
                yield from find_runs(v)
    elif isinstance(node, list):
        for item in node:
            yield from find_runs(item)

def scan_file(file_path: Path) -> List[Tuple[int, str]]:
    try:
        text = file_path.read_text(encoding="utf-8")
        data = yaml.safe_load(text)
    except Exception:
        return []
    runs = list(find_runs(data))
    findings = []
    lines = text.splitlines()
    for run in runs:
        run_lines = run.splitlines()
        for rl in run_lines:
            stripped = rl.strip()
            if PIP_INSTALL_RE.search(stripped):
                # Find line number where this fragment appears
                for i, ll in enumerate(lines, start=1):
                    if stripped in ll:
                        findings.append((i, ll.strip()))
                        break
    return findings

def is_allowed(file_rel: str, line: str) -> bool:
    if ALLOW_REQUIREMENT.search(line):
        return True
    if ALLOW_CONSTRAINT.search(line):
        return True
    if ALLOW_UPGRADE_PIP.search(line):
        return True
    if ALLOW_EDITABLE.search(line):
        return True
    for base_file, base_cmd in BASELINE_EXCEPTIONS:
        if file_rel == base_file and base_cmd in line:
            return True
    return False

def scan() -> List[Tuple[str, int, str]]:
    violations = []
    workflow_dir = REPO_ROOT / ".github" / "workflows"
    action_dir = REPO_ROOT / ".github" / "actions"
    for dir_path in [workflow_dir, action_dir]:
        if not dir_path.exists():
            continue
        for fp in dir_path.rglob("*.yml"):
            rel = str(fp.relative_to(REPO_ROOT))
            findings = scan_file(fp)
            for line_no, line in findings:
                if not is_allowed(rel, line):
                    violations.append((rel, line_no, line))
    return violations

def main() -> int:
    violations = scan()
    if violations:
        print("PIP INSTALL GUARD VIOLATIONS FOUND:")
        for rel, line_no, line in violations:
            print(f"- {rel}:{line_no}: {line}")
            print(f"  Reason: Unpinned ad-hoc pip install detected")
            print(f"  Remediation: Move to requirements.txt or add a narrow baseline exception with justification")
        return 1
    print("PIP INSTALL GUARD: PASS")
    return 0

if __name__ == "__main__":
    sys.exit(main())
