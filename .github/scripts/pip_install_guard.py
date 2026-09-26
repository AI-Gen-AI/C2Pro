#!/usr/bin/env python3
"""CI regression guard for unpinned ad-hoc pip installs - policy engine redesign."""

from __future__ import annotations

import re
import shlex
import sys
from pathlib import Path
from typing import List, Tuple

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

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

PIP_EXEC_RE = re.compile(r'^(python[0-9.]*\s+-m\s+)?pip[0-9.]*$', re.IGNORECASE)

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

def normalize_run(run: str) -> str:
    # Remove backslash line continuations
    run = re.sub(r'\\\s*\n', ' ', run)
    return run

def split_logical_commands(run: str) -> List[str]:
    # split on ; && ||
    parts = re.split(r';|&&|\|\|', run)
    return [p.strip() for p in parts if p.strip()]

def extract_pip_commands(cmd: str) -> List[str]:
    # Return list of pip install command substrings found in cmd
    # Find all occurrences of pip ... install
    pattern = re.compile(r'(python[0-9.]*\s+-m\s+)?pip[0-9.]*\s+.*?\binstall\b.*', re.IGNORECASE)
    # We need to avoid matching inside strings? Acceptable for now
    # We'll find matches and return the matched text
    matches = []
    for m in pattern.finditer(cmd):
        # Trim to end of line for safety
        snippet = m.group(0)
        matches.append(snippet)
    return matches

def parse_pip_args(pip_cmd: str):
    try:
        tokens = shlex.split(pip_cmd)
    except ValueError:
        return None
    # Find install token
    try:
        idx = tokens.index('install')
    except ValueError:
        return None
    # Ensure pip executable is before install
    # Check that tokens before install contain pip
    # Simple check
    args = tokens[idx+1:]
    return tokens, args

def is_valid_repo_path(path: str) -> bool:
    # static repo-relative path, no http, no absolute, no ~, no ../, no $ ` ( ) 
    if not path:
        return False
    if re.search(r'[~$`]|\.\.|://', path):
        return False
    if path.startswith('/') or path.startswith('http://') or path.startswith('https://'):
        return False
    # allow only alphanum / . _ -
    if not re.fullmatch(r'[A-Za-z0-9_./-]+', path):
        return False
    return True

def is_upgrade_pip_only(tokens, args):
    # args after install
    # must be --upgrade pip and nothing else positional
    i = 0
    # skip global options before install? already after install
    if len(args) >= 2 and args[0] == '--upgrade' and args[1] == 'pip':
        # ensure no other non-option tokens
        for t in args[2:]:
            if not t.startswith('-'):
                return False
        return True
    return False

def is_canonical_requirements(tokens, args):
    has_req = False
    i = 0
    while i < len(args):
        t = args[i]
        if t in ('-r','--requirement'):
            if i+1 >= len(args):
                return False
            path = args[i+1]
            if not is_valid_repo_path(path):
                return False
            has_req = True
            i += 2
        elif t == '-c' or t.startswith('--constraint'):
            if t == '-c':
                if i+1 >= len(args):
                    return False
                path = args[i+1]
                if not is_valid_repo_path(path):
                    return False
                i += 2
            else:
                # --constraint=path
                if '=' in t:
                    path = t.split('=',1)[1]
                    if not is_valid_repo_path(path):
                        return False
                else:
                    if i+1 >= len(args):
                        return False
                    path = args[i+1]
                    if not is_valid_repo_path(path):
                        return False
                    i += 1
                i += 1
        elif t.startswith('-'):
            # unknown option -> fail closed for canonical
            # allow only known options
            if t not in ('-r','--requirement','-c','--constraint'):
                # allow --constraint with value handled above
                # fail closed
                return False
            i += 1
            if i < len(args) and not args[i].startswith('-'):
                i += 1
        else:
            # positional package
            return False
    return has_req

def is_editable_local_only(tokens, args):
    seen_editable = False
    i = 0
    while i < len(args):
        t = args[i]
        if t == '-e':
            seen_editable = True
            if i+1 >= len(args):
                return False
            target = args[i+1]
            if not (target == '.' or target.startswith('./')):
                return False
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
            if not (target == '.' or target.startswith('./')):
                return False
            i += 1
        elif t.startswith('-'):
            i += 1
            if i < len(args) and not args[i].startswith('-'):
                i += 1
        else:
            # positional package -> not allowed with editable
            return False
    return seen_editable

def normalize_cmd(cmd: str) -> str:
    # collapse whitespace, lower case
    cmd = ' '.join(cmd.split())
    return cmd.lower()

def is_allowed(file_rel: str, line: str) -> bool:
    # backward compatibility wrapper for tests
    return evaluate_pip_command(file_rel, line)

def is_baseline_allowed(file_rel: str, pip_cmd: str) -> bool:
    norm = normalize_cmd(pip_cmd)
    for base_file, base_cmd in BASELINE_EXCEPTIONS:
        if file_rel == base_file and norm == normalize_cmd(base_cmd):
            return True
    return False

def evaluate_pip_command(file_rel: str, pip_cmd: str) -> bool:
    # Returns True if allowed
    parsed = parse_pip_args(pip_cmd)
    if parsed is None:
        return False
    tokens, args = parsed
    # Upgrade pip only
    if is_upgrade_pip_only(tokens, args):
        return True
    # Editable local only
    if '-e' in args or any(t.startswith('--editable') for t in args):
        return is_editable_local_only(tokens, args)
    # Canonical requirements
    if is_canonical_requirements(tokens, args):
        return True
    # Baseline exact match
    if is_baseline_allowed(file_rel, pip_cmd):
        return True
    return False

def scan_file(file_path: Path) -> Tuple[List[Tuple[int,str]], bool]:
    text = file_path.read_text(encoding='utf-8')
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return [], True
    runs = list(find_runs(data))
    findings = []
    for run in runs:
        norm_run = normalize_run(run)
        cmds = split_logical_commands(norm_run)
        for cmd in cmds:
            pip_cmds = extract_pip_commands(cmd)
            for pc in pip_cmds:
                # try to find line number for reporting
                line_no = -1
                # search in raw text for first occurrence of pip command start
                # simple search
                for i, ll in enumerate(text.splitlines(), start=1):
                    if pc.split()[0].lower() in ll.lower() and 'install' in ll.lower():
                        line_no = i
                        break
                findings.append((line_no, pc))
    return findings, False

def scan() -> List[Tuple[str,int,str,str]]:
    violations = []
    roots = [
        REPO_ROOT / ".github" / "workflows",
        REPO_ROOT / ".github" / "actions",
    ]
    for root in roots:
        if not root.exists():
            continue
        for ext in ("*.yml","*.yaml"):
            for fp in root.rglob(ext):
                rel = str(fp.relative_to(REPO_ROOT))
                findings, parse_err = scan_file(fp)
                if parse_err:
                    violations.append((rel, -1, f"YAML parse error in {fp.name}", "parse_error"))
                    continue
                for line_no, pip_cmd in findings:
                    if not evaluate_pip_command(rel, pip_cmd):
                        violations.append((rel, line_no, pip_cmd, "unpinned"))
    return violations

def main():
    violations = scan()
    if violations:
        print("PIP INSTALL GUARD VIOLATIONS FOUND:")
        for rel, line_no, cmd, reason in violations:
            loc = f"{rel}:{line_no}" if line_no != -1 else rel
            print(f"- {loc}: {cmd}")
            if reason == "parse_error":
                print("  Reason: YAML parse failure")
                print("  Remediation: Fix YAML syntax")
            else:
                print("  Reason: Unpinned ad-hoc pip install detected")
                print("  Remediation: Move to requirements.txt or add narrow baseline")
        return 1
    print("PIP INSTALL GUARD: PASS")
    return 0

if __name__ == "__main__":
    sys.exit(main())
