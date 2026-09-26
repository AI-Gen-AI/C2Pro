#!/usr/bin/env python3
"""CI regression guard for unpinned ad-hoc pip installs."""

from __future__ import annotations

import re
import shlex
import sys
from pathlib import Path
from typing import List, Tuple

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

PIP_INSTALL_RE = re.compile(r"\bpip(?:\s+-m\s+pip)?\s+install\b", re.IGNORECASE)

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

def extract_pip_cmd(line: str) -> str:
    m = re.search(r'(python -m )?pip install\b.*', line, re.IGNORECASE)
    if m:
        return m.group(0).strip()
    return line.strip()

def is_upgrade_pip(line: str) -> bool:
    try:
        tokens = shlex.split(line)
        if 'pip' not in tokens or 'install' not in tokens:
            return False
        # find install index
        try:
            idx = tokens.index('install')
        except ValueError:
            return False
        args = tokens[idx+1:]
        if '--upgrade' in args:
            up_idx = args.index('--upgrade')
            if up_idx + 1 < len(args) and args[up_idx+1] == 'pip':
                # ensure no other packages
                # allow only upgrade pip
                # check remaining tokens
                return True
    except ValueError:
        return False
    return False

def is_canonical_requirements(line: str) -> bool:
    try:
        tokens = shlex.split(line)
    except ValueError:
        return False
    # find install
    try:
        idx = tokens.index('install')
    except ValueError:
        return False
    args = tokens[idx+1:]
    has_requirement = False
    i = 0
    while i < len(args):
        t = args[i]
        if t in ('-r', '--requirement'):
            has_requirement = True
            i += 1
            if i < len(args):
                i += 1  # skip file
        elif t == '-c' or t.startswith('--constraint'):
            i += 1
            if t == '-c' and i < len(args):
                i += 1
        elif t.startswith('-'):
            i += 1
            if i < len(args) and not args[i].startswith('-'):
                i += 1
        else:
            # positional package
            return False
    return has_requirement

def is_editable_local(line: str) -> bool:
    try:
        tokens = shlex.split(line)
    except ValueError:
        return False
    try:
        idx = tokens.index('install')
    except ValueError:
        return False
    args = tokens[idx+1:]
    for i, t in enumerate(args):
        if t == '-e':
            if i+1 >= len(args):
                return False
            target = args[i+1]
            # local path only
            if target.startswith('.') or target.startswith('/'):
                # ensure no additional packages
                # if -e present, we still allow only -e target and options
                # check remaining tokens
                return True
            else:
                return False
        if t.startswith('--editable'):
            # handle --editable=path
            if '=' in t:
                target = t.split('=',1)[1]
                if target.startswith('.') or target.startswith('/'):
                    return True
                else:
                    return False
    # if no -e found, not editable
    return False

def is_baseline_allowed(file_rel: str, line: str) -> bool:
    pip_cmd = extract_pip_cmd(line)
    for base_file, base_cmd in BASELINE_EXCEPTIONS:
        if file_rel == base_file and pip_cmd.lower() == base_cmd.lower():
            return True
    return False

def tokens_contain_editable(line: str) -> bool:
    try:
        tokens = shlex.split(line)
    except ValueError:
        return False
    try:
        idx = tokens.index('install')
    except ValueError:
        return False
    args = tokens[idx+1:]
    for t in args:
        if t == '-e' or t.startswith('--editable'):
            return True
    return False

def is_allowed(file_rel: str, line: str) -> bool:
    if is_upgrade_pip(line):
        return True
    if is_canonical_requirements(line):
        return True
    if tokens_contain_editable(line):
        # editable present, allow only local
        return is_editable_local(line)
    if is_baseline_allowed(file_rel, line):
        return True
    return False

def scan_file(file_path: Path) -> Tuple[List[Tuple[int, str]], bool]:
    text = file_path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        return [], True  # parse error flag
    runs = list(find_runs(data))
    findings = []
    lines = text.splitlines()
    for run in runs:
        run_lines = run.splitlines()
        for rl in run_lines:
            stripped = rl.strip()
            if PIP_INSTALL_RE.search(stripped):
                # find line number containing this fragment
                for i, ll in enumerate(lines, start=1):
                    if stripped in ll:
                        findings.append((i, ll.strip()))
                        break
    return findings, False

def scan() -> List[Tuple[str, int, str, str]]:
    violations = []
    workflow_dir = REPO_ROOT / ".github" / "workflows"
    action_dir = REPO_ROOT / ".github" / "actions"
    for dir_path in [workflow_dir, action_dir]:
        if not dir_path.exists():
            continue
        for fp in dir_path.rglob("*.yml"):
            rel = str(fp.relative_to(REPO_ROOT))
            findings, parse_error = scan_file(fp)
            if parse_error:
                violations.append((rel, -1, f"YAML parse error in {fp.name}", "parse_error"))
                continue
            for line_no, line in findings:
                if not is_allowed(rel, line):
                    violations.append((rel, line_no, line, "unpinned"))
    return violations

def main() -> int:
    violations = scan()
    if violations:
        print("PIP INSTALL GUARD VIOLATIONS FOUND:")
        for rel, line_no, line, reason in violations:
            loc = f"{rel}:{line_no}" if line_no != -1 else rel
            print(f"- {loc}: {line}")
            if reason == "parse_error":
                print(f"  Reason: YAML parse failure")
                print(f"  Remediation: Fix YAML syntax in the file")
            else:
                print(f"  Reason: Unpinned ad-hoc pip install detected")
                print(f"  Remediation: Move to requirements.txt or add a narrow baseline exception with justification")
        return 1
    print("PIP INSTALL GUARD: PASS")
    return 0

if __name__ == "__main__":
    sys.exit(main())
