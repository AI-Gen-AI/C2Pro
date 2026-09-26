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

ALLOWED_CANONICAL_OPTS = {'-r', '--requirement', '-c', '--constraint'}

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

def parse_pip_args(line: str):
    try:
        tokens = shlex.split(line)
    except ValueError:
        return None
    try:
        idx = tokens.index('install')
    except ValueError:
        return None
    args = tokens[idx+1:]
    return args

def is_upgrade_pip(line: str) -> bool:
    args = parse_pip_args(line)
    if args is None:
        return False
    # must contain --upgrade pip and nothing else positional
    seen_upgrade = False
    seen_pip_target = False
    i = 0
    while i < len(args):
        t = args[i]
        if t == '--upgrade':
            if i+1 >= len(args) or args[i+1] != 'pip':
                return False
            seen_upgrade = True
            seen_pip_target = True
            i += 2
            continue
        if t.startswith('-'):
            # allow other flags? fail closed for upgrade case
            # only allow --upgrade
            return False
        # positional package not allowed
        return False
    return seen_upgrade and seen_pip_target

def is_canonical_requirements(line: str) -> bool:
    args = parse_pip_args(line)
    if args is None:
        return False
    has_requirement = False
    i = 0
    while i < len(args):
        t = args[i]
        if t in ('-r','--requirement'):
            has_requirement = True
            i += 1
            if i < len(args):
                i += 1  # skip file
        elif t == '-c' or t.startswith('--constraint'):
            i += 1
            if t == '-c' and i < len(args):
                i += 1
        elif t.startswith('-'):
            # unknown option -> fail closed
            if t not in ALLOWED_CANONICAL_OPTS and not t.startswith('--constraint'):
                return False
            i += 1
            if i < len(args) and not args[i].startswith('-'):
                i += 1
        else:
            # positional package
            return False
    return has_requirement

def is_editable_local(line: str) -> bool:
    args = parse_pip_args(line)
    if args is None:
        return False
    i = 0
    seen_editable = False
    editable_target = None
    while i < len(args):
        t = args[i]
        if t == '-e':
            seen_editable = True
            if i+1 >= len(args):
                return False
            target = args[i+1]
            if not (target.startswith('.') or target.startswith('/')):
                return False
            editable_target = target
            i += 2
        elif t.startswith('--editable'):
            seen_editable = True
            if '=' in t:
                target = t.split('=',1)[1]
            else:
                if i+1 >= len(args):
                    return False
                target = args[i+1]
                i += 1
            if not (target.startswith('.') or target.startswith('/')):
                return False
            editable_target = target
            i += 1
        elif t.startswith('-'):
            i += 1
            if i < len(args) and not args[i].startswith('-'):
                i += 1
        else:
            # positional package not allowed alongside editable
            return False
    return seen_editable and editable_target is not None

def tokens_contain_editable(line: str) -> bool:
    args = parse_pip_args(line)
    if args is None:
        return False
    for t in args:
        if t == '-e' or t.startswith('--editable'):
            return True
    return False

def is_baseline_allowed(file_rel: str, line: str) -> bool:
    pip_cmd = extract_pip_cmd(line)
    for base_file, base_cmd in BASELINE_EXCEPTIONS:
        if file_rel == base_file and pip_cmd.lower() == base_cmd.lower():
            return True
    return False

def is_allowed(file_rel: str, line: str) -> bool:
    if is_upgrade_pip(line):
        return True
    if is_canonical_requirements(line):
        return True
    if tokens_contain_editable(line):
        return is_editable_local(line)
    if is_baseline_allowed(file_rel, line):
        return True
    return False

def scan_file(file_path: Path) -> Tuple[List[Tuple[int, str]], bool]:
    text = file_path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return [], True
    runs = list(find_runs(data))
    findings = []
    # Try to map findings to line numbers where possible
    lines = text.splitlines()
    for run in runs:
        # find all pip install occurrences in run string
        for m in PIP_INSTALL_RE.finditer(run):
            # extract the command line fragment up to next newline
            start = m.start()
            # find end of logical line
            snippet_end = run.find('\n', start)
            if snippet_end == -1:
                snippet = run[start:].strip()
            else:
                snippet = run[start:snippet_end].strip()
            # attempt to locate snippet in raw file for line number
            line_no = -1
            src_line = snippet
            for i, ll in enumerate(lines, start=1):
                if snippet in ll:
                    line_no = i
                    src_line = ll.strip()
                    break
            findings.append((line_no, src_line))
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
