#!/usr/bin/env python3
"""CI install drift guard (#685, design authority #684, parent #600).

This is a drift detector, not a malicious-author security boundary.

What it does
------------
1. Parses every GitHub Actions file under ``.github/workflows/**`` and
   ``.github/actions/**`` (``.yml`` / ``.yaml``) with a duplicate-key-rejecting
   SafeLoader.
2. Enumerates every step ``run:`` block. A block is *relevant* when its parsed
   text contains a Python package-install indicator (see ``is_relevant``).
3. For each relevant block it builds the effective behavior object
   ``{run, shell, working_directory, env}`` from the exact parsed YAML values
   (no stripping, case folding, whitespace or continuation rewriting;
   ``${{ }}`` expressions stay literal text) and hashes its canonical JSON
   with SHA-256.
4. Authorizes the block only if the committed baseline manifest holds an entry
   for the exact structural context
   (``<file>::jobs.<job_id>::<step_key>`` or ``<file>::runs.steps::<step_key>``,
   ``step_key`` = ``id:<id>`` else ``name:<name>``, never a list index) whose
   stored behavior and digest equal the current ones.

Unknown, changed, ambiguous, stale or duplicated entries, YAML/schema/I-O
errors and an empty scan all fail (non-zero exit). There is no pip-option or
shell parser: any change to a relevant block's behavior requires a reviewed
baseline update.

Threat model
------------
In scope: accidental or unreviewed drift of Python package-install behavior in
workflow/composite-action ``run:`` blocks, including package-source drift via
``PIP_*`` / ``UV_*`` / ``PYTHONPATH`` env, shell and working-directory changes,
and copying/moving an authorized block to a new execution context.

Out of scope (residual risk): an author who changes the guard and the baseline
together; computed, encoded or obfuscated install commands (e.g. ``p''ip``)
that evade the static relevance detector; installs inside invoked scripts,
``uses:`` actions or remote reusable workflows; runtime values of expressions
and variables; compromised runners.

Usage
-----
  python .github/scripts/install_drift_guard.py                    # verify (CI)
  python .github/scripts/install_drift_guard.py --update-baseline  # local operator only

``--update-baseline`` rewrites the manifest deterministically, keeps the
review fields of unchanged contexts and marks new contexts ``TODO`` so the
result cannot pass verification until a human fills in reason, owner and
remediation issue. CI must only verify.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_ROOT = ".github/workflows"
ACTIONS_ROOT = ".github/actions"
SCAN_ROOTS = (WORKFLOWS_ROOT, ACTIONS_ROOT)
YAML_SUFFIXES = (".yml", ".yaml")
MANIFEST_REL = ".github/ci-pip-install-baseline.json"
MANIFEST_SCHEMA = "c2pro-ci-install-drift-baseline/v1"

ENTRY_KEYS = {
    "context",
    "file",
    "sha256",
    "behavior",
    "reason",
    "owner",
    "remediation_issue",
}
BEHAVIOR_KEYS = {"run", "shell", "working_directory", "env"}
PLACEHOLDER_PREFIX = "TODO"
SHA256_RE = re.compile(r"[0-9a-f]{64}")
ISSUE_RE = re.compile(r"#[0-9]+")
STEP_KEY_RE = r"(?:id|name):.+"
RELEVANT_ENV_RE = re.compile(r"(?:PIP_|UV_).*|PYTHONPATH", re.IGNORECASE | re.DOTALL)

_B = r"(?<![A-Za-z0-9_])"  # token start
_E = r"(?![A-Za-z0-9_])"  # token end
# Deliberately simple and conservative. Deterministic false positives
# (pip-audit, python3-pip, the word "requirements") are accepted; split or
# computed spellings are a documented false-negative limitation.
RELEVANCE_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        rf"{_B}pip(?:3(?:\.[0-9]+)?)?{_E}",  # pip, pip3, pip3.X, 'pip', $PIP, python -m pip
        rf"{_B}pipx{_E}",
        rf"{_B}pipenv{_E}",
        r"requirements",
        r"\.whl",
        r"ensurepip",
        r"easy_install",
        rf"{_B}uv\s+(?:pip|sync|add){_E}",
        rf"{_B}poetry\s+(?:install|add){_E}",
        rf"{_B}conda\s+install{_E}",
        rf"{_B}(?:PIP|UV)_[A-Z0-9_]*",  # env-based package source, e.g. >> $GITHUB_ENV
        rf"{_B}PYTHONPATH{_E}",
    )
]

_SCALAR_ENV_TYPES = (str, int, bool, type(None))


class GuardError(Exception):
    """Structural problem that prevents a trustworthy baseline update."""


@dataclass(frozen=True)
class Finding:
    code: str
    file: str | None
    context: str | None
    message: str

    def __str__(self) -> str:
        where = self.context or self.file or "-"
        return f"{self.code} {where}: {self.message}"


@dataclass(frozen=True)
class Block:
    context: str
    file: str
    behavior: dict[str, Any]


@dataclass
class _Scan:
    blocks: list[Block]
    findings: list[Finding]
    files: int
    run_steps: int


# ------------------------------------------------------------------ YAML input
class _UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate mapping keys (PyYAML keeps the last)."""

    def construct_mapping(self, node, deep=False):
        if isinstance(node, yaml.MappingNode):
            seen = set()
            for key_node, _ in node.value:
                if key_node.tag == "tag:yaml.org,2002:merge":
                    continue
                key = self.construct_object(key_node, deep=True)
                try:
                    duplicate = key in seen
                except TypeError:
                    raise yaml.constructor.ConstructorError(
                        None,
                        None,
                        f"unhashable mapping key {key!r}",
                        key_node.start_mark,
                    )
                if duplicate:
                    raise yaml.constructor.ConstructorError(
                        None,
                        None,
                        f"duplicate mapping key {key!r}",
                        key_node.start_mark,
                    )
                seen.add(key)
        return super().construct_mapping(node, deep=deep)


def load_yaml(text: str) -> Any:
    """Parse exactly one YAML document; duplicate keys raise YAMLError."""
    return yaml.load(text, Loader=_UniqueKeyLoader)


# --------------------------------------------------------------- relevance
def is_relevant(run: str) -> bool:
    return any(p.search(run) for p in RELEVANCE_PATTERNS)


# ------------------------------------------------------------ canonical digest
def canonical_json(behavior: dict[str, Any]) -> str:
    return json.dumps(
        behavior, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )


def behavior_digest(behavior: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(behavior).encode("utf-8")).hexdigest()


# -------------------------------------------------------------------- scanning
def _discover(repo_root: Path) -> tuple[list[Path], list[Finding]]:
    files: list[Path] = []
    findings: list[Finding] = []
    for root_rel in SCAN_ROOTS:
        base = repo_root / root_rel
        if base.is_symlink():
            findings.append(
                Finding("SCHEMA_ERROR", root_rel, None, "scan root is a symlink")
            )
            continue
        if not base.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
            current = Path(dirpath)
            for name in sorted(dirnames):
                if (current / name).is_symlink():
                    rel = (current / name).relative_to(repo_root).as_posix()
                    findings.append(
                        Finding(
                            "SCHEMA_ERROR",
                            rel,
                            None,
                            "symlinked directory in scan root",
                        )
                    )
            for name in sorted(filenames):
                path = current / name
                if not name.lower().endswith(YAML_SUFFIXES):
                    continue
                if path.is_symlink():
                    rel = path.relative_to(repo_root).as_posix()
                    findings.append(
                        Finding(
                            "SCHEMA_ERROR",
                            rel,
                            None,
                            "symlinked YAML file in scan root",
                        )
                    )
                    continue
                files.append(path)
    return sorted(files), findings


class _SchemaError(Exception):
    pass


def _opt_str(value: Any, what: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise _SchemaError(f"{what} must be a string, got {type(value).__name__}")
    return value


def _mapping(value: Any, what: str) -> dict[Any, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise _SchemaError(f"{what} must be a mapping, got {type(value).__name__}")
    return value


def _run_defaults(owner: dict[Any, Any], what: str) -> dict[str, str | None]:
    defaults = _mapping(owner.get("defaults"), f"{what} defaults")
    run = _mapping(defaults.get("run"), f"{what} defaults.run")
    return {
        "shell": _opt_str(run.get("shell"), f"{what} defaults.run.shell"),
        "working-directory": _opt_str(
            run.get("working-directory"), f"{what} defaults.run.working-directory"
        ),
    }


def _relevant_env(scopes: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    env: dict[str, Any] = {}
    for what, value in scopes:
        if value is None:
            continue
        if not isinstance(value, dict):
            raise _SchemaError(
                f"{what} env is not a literal mapping; relevant env cannot be resolved"
            )
        for key, val in value.items():
            if not isinstance(key, str):
                raise _SchemaError(f"{what} env key {key!r} is not a string")
            if RELEVANT_ENV_RE.fullmatch(key):
                if not isinstance(val, _SCALAR_ENV_TYPES):
                    raise _SchemaError(
                        f"{what} env {key} must be a scalar, got {type(val).__name__}"
                    )
                env[key] = val
    return env


def _step_key(step: dict[Any, Any]) -> str | None:
    step_id = _opt_str(step.get("id"), "step id")
    if step_id:
        return f"id:{step_id}"
    name = _opt_str(step.get("name"), "step name")
    if name:
        return f"name:{name}"
    return None


def _first(*values: str | None) -> str | None:
    for value in values:
        if value is not None:
            return value
    return None


def _scan_steps(
    rel: str,
    scope: str,
    steps: Any,
    inherited_shell: str | None,
    inherited_wd: str | None,
    env_scopes: list[tuple[str, Any]],
    recognized: set,
    path_prefix: tuple[Any, ...],
    out: list[tuple[str, Block]],
    findings: list[Finding],
) -> int:
    if not isinstance(steps, list):
        raise _SchemaError(f"{scope} steps must be a list, got {type(steps).__name__}")
    run_steps = 0
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            raise _SchemaError(
                f"{scope} step #{index + 1} must be a mapping, got {type(step).__name__}"
            )
        if "run" not in step:
            continue
        run_steps += 1
        recognized.add(path_prefix + (index, "run"))
        run = step["run"]
        if not isinstance(run, str):
            raise _SchemaError(
                f"{scope} step #{index + 1} run must be a string, got {type(run).__name__}"
            )
        if not is_relevant(run):
            continue
        key = _step_key(step)
        if key is None:
            findings.append(
                Finding(
                    "MISSING_STEP_KEY",
                    rel,
                    None,
                    f"{scope} step #{index + 1} is an install-relevant run block without id or name; "
                    "add a unique step id",
                )
            )
            continue
        behavior = {
            "run": run,
            "shell": _first(_opt_str(step.get("shell"), "step shell"), inherited_shell),
            "working_directory": _first(
                _opt_str(step.get("working-directory"), "step working-directory"),
                inherited_wd,
            ),
            "env": _relevant_env(env_scopes + [("step", step.get("env"))]),
        }
        context = f"{rel}::{scope}::{key}"
        out.append((context, Block(context=context, file=rel, behavior=behavior)))
    return run_steps


def _scan_workflow(rel: str, doc: Any, recognized: set, out, findings) -> int:
    if not isinstance(doc, dict):
        raise _SchemaError("workflow must be a mapping")
    jobs = doc.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        raise _SchemaError("workflow must have a non-empty `jobs` mapping")
    wf_defaults = _run_defaults(doc, "workflow")
    run_steps = 0
    for job_id, job in jobs.items():
        if not isinstance(job_id, str):
            raise _SchemaError(f"job id {job_id!r} must be a string")
        if not isinstance(job, dict):
            raise _SchemaError(f"job {job_id} must be a mapping")
        job_defaults = _run_defaults(job, f"job {job_id}")
        if "steps" not in job:
            continue
        run_steps += _scan_steps(
            rel,
            f"jobs.{job_id}",
            job["steps"],
            _first(job_defaults["shell"], wf_defaults["shell"]),
            _first(job_defaults["working-directory"], wf_defaults["working-directory"]),
            [("workflow", doc.get("env")), (f"job {job_id}", job.get("env"))],
            recognized,
            ("jobs", job_id, "steps"),
            out,
            findings,
        )
    return run_steps


def _scan_action(rel: str, doc: Any, recognized: set, out, findings) -> int:
    if not isinstance(doc, dict):
        raise _SchemaError("action must be a mapping")
    runs = doc.get("runs")
    if not isinstance(runs, dict):
        raise _SchemaError("action must have a `runs` mapping")
    if "steps" not in runs:
        if runs.get("using") == "composite":
            raise _SchemaError("composite action must have `runs.steps`")
        return 0
    return _scan_steps(
        rel,
        "runs.steps",
        runs["steps"],
        None,
        None,
        [],
        recognized,
        ("runs", "steps"),
        out,
        findings,
    )


def _stray_runs(
    rel: str, node: Any, path: tuple[Any, ...], recognized: set, seen: set, findings
) -> None:
    if isinstance(node, (dict, list)):
        if id(node) in seen:
            return
        seen.add(id(node))
    if isinstance(node, dict):
        for key, value in node.items():
            child = path + (key,)
            if (
                key == "run"
                and isinstance(value, str)
                and child not in recognized
                and is_relevant(value)
            ):
                findings.append(
                    Finding(
                        "UNRECOGNIZED_RUN",
                        rel,
                        None,
                        f"install-relevant `run` at {'.'.join(map(str, child))} is not a step run block",
                    )
                )
            _stray_runs(rel, value, child, recognized, seen, findings)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            _stray_runs(rel, value, path + (index,), recognized, seen, findings)


def _scan(repo_root: Path) -> _Scan:
    files, findings = _discover(repo_root)
    collected: list[tuple[str, Block]] = []
    run_steps = 0
    for path in files:
        rel = path.relative_to(repo_root).as_posix()
        try:
            text = path.read_bytes().decode("utf-8")
            doc = load_yaml(text)
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
            findings.append(
                Finding("YAML_ERROR", rel, None, f"{type(exc).__name__}: {exc}")
            )
            continue
        recognized: set = set()
        file_blocks: list[tuple[str, Block]] = []
        file_findings: list[Finding] = []
        try:
            if rel.startswith(WORKFLOWS_ROOT + "/"):
                count = _scan_workflow(rel, doc, recognized, file_blocks, file_findings)
            else:
                count = _scan_action(rel, doc, recognized, file_blocks, file_findings)
        except _SchemaError as exc:
            findings.append(Finding("SCHEMA_ERROR", rel, None, str(exc)))
            continue
        _stray_runs(rel, doc, (), recognized, set(), file_findings)
        run_steps += count
        findings.extend(file_findings)
        collected.extend(file_blocks)

    by_context: dict[str, list[Block]] = {}
    for context, block in collected:
        by_context.setdefault(context, []).append(block)
    blocks: list[Block] = []
    for context, group in sorted(by_context.items()):
        if len(group) > 1:
            findings.append(
                Finding(
                    "DUPLICATE_CONTEXT",
                    group[0].file,
                    context,
                    f"{len(group)} install-relevant run blocks share this context; add a unique step id",
                )
            )
            continue
        blocks.append(group[0])

    if not files:
        findings.append(
            Finding(
                "EMPTY_SCAN",
                None,
                None,
                "no workflow/action YAML files found under scan roots",
            )
        )
    elif run_steps == 0 and not any(
        f.code in ("YAML_ERROR", "SCHEMA_ERROR") for f in findings
    ):
        findings.append(
            Finding(
                "EMPTY_SCAN",
                None,
                None,
                "no step run blocks found; scanner cannot be trusted",
            )
        )
    return _Scan(
        blocks=blocks, findings=_sorted(findings), files=len(files), run_steps=run_steps
    )


def collect_blocks(repo_root: Path) -> tuple[list[Block], list[Finding]]:
    scan = _scan(Path(repo_root))
    return scan.blocks, scan.findings


def _sorted(findings: Iterable[Finding]) -> list[Finding]:
    return sorted(
        findings, key=lambda f: (f.code, f.file or "", f.context or "", f.message)
    )


# -------------------------------------------------------------------- manifest
def render_manifest(manifest: dict[str, Any]) -> str:
    entries = sorted(
        manifest["entries"],
        key=lambda e: (e["context"], json.dumps(e, sort_keys=True, ensure_ascii=False)),
    )
    body = {"schema": manifest["schema"], "entries": entries}
    return json.dumps(body, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _reject_duplicate_json_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _read_manifest_json(path: Path) -> tuple[Any, str]:
    text = path.read_bytes().decode("utf-8")
    return json.loads(text, object_pairs_hook=_reject_duplicate_json_keys), text


def _valid_manifest_file(file: str) -> bool:
    if "\\" in file or file.startswith("/"):
        return False
    parts = PurePosixPath(file).parts
    if any(part in ("..", ".", "") for part in parts):
        return False
    if not file.lower().endswith(YAML_SUFFIXES):
        return False
    return any(file.startswith(root + "/") for root in SCAN_ROOTS)


def _entry_errors(entry: Any) -> list[str]:
    if not isinstance(entry, dict):
        return ["entry must be an object"]
    errors: list[str] = []
    keys = set(entry)
    if keys != ENTRY_KEYS:
        errors.append(
            f"entry keys must be exactly {sorted(ENTRY_KEYS)}, got {sorted(keys)}"
        )
        return errors
    context, file = entry["context"], entry["file"]
    if not isinstance(context, str) or not isinstance(file, str):
        return ["context and file must be strings"]
    if not _valid_manifest_file(file):
        errors.append(
            f"file {file!r} is outside the scan roots {list(SCAN_ROOTS)} or not a YAML path"
        )
    scope = r"jobs\.[^:]+" if file.startswith(WORKFLOWS_ROOT + "/") else r"runs\.steps"
    if not re.fullmatch(
        re.escape(file) + "::" + scope + "::" + STEP_KEY_RE, context, re.DOTALL
    ):
        errors.append(f"context {context!r} does not match file {file!r}")
    if not isinstance(entry["sha256"], str) or not SHA256_RE.fullmatch(entry["sha256"]):
        errors.append("sha256 must be 64 lowercase hex characters")
    behavior = entry["behavior"]
    if not isinstance(behavior, dict) or set(behavior) != BEHAVIOR_KEYS:
        errors.append(f"behavior keys must be exactly {sorted(BEHAVIOR_KEYS)}")
    else:
        if not isinstance(behavior["run"], str):
            errors.append("behavior.run must be a string")
        for key in ("shell", "working_directory"):
            if not isinstance(behavior[key], (str, type(None))):
                errors.append(f"behavior.{key} must be a string or null")
        env = behavior["env"]
        if not isinstance(env, dict):
            errors.append("behavior.env must be an object")
        else:
            for key, value in env.items():
                if not RELEVANT_ENV_RE.fullmatch(key) or not isinstance(
                    value, _SCALAR_ENV_TYPES
                ):
                    errors.append(
                        f"behavior.env entry {key!r} is not a relevant scalar env value"
                    )
    for key in ("reason", "owner"):
        value = entry[key]
        if (
            not isinstance(value, str)
            or not value.strip()
            or value.strip().upper().startswith(PLACEHOLDER_PREFIX)
        ):
            errors.append(
                f"{key} must be a reviewed, non-placeholder string (got {value!r})"
            )
    if not isinstance(entry["remediation_issue"], str) or not ISSUE_RE.fullmatch(
        entry["remediation_issue"]
    ):
        errors.append("remediation_issue must look like '#600'")
    return errors


def load_manifest(path: Path) -> tuple[list[dict[str, Any]] | None, list[Finding]]:
    rel = MANIFEST_REL
    if not path.is_file():
        return None, [
            Finding("MANIFEST_ERROR", rel, None, "baseline manifest not found")
        ]
    try:
        data, text = _read_manifest_json(path)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return None, [
            Finding("MANIFEST_ERROR", rel, None, f"cannot parse manifest: {exc}")
        ]
    if not isinstance(data, dict) or set(data) != {"schema", "entries"}:
        return None, [
            Finding(
                "MANIFEST_ERROR",
                rel,
                None,
                "manifest must be an object with exactly `schema` and `entries`",
            )
        ]
    if data["schema"] != MANIFEST_SCHEMA:
        return None, [
            Finding(
                "MANIFEST_ERROR",
                rel,
                None,
                f"manifest schema must be {MANIFEST_SCHEMA!r}",
            )
        ]
    if not isinstance(data["entries"], list):
        return None, [Finding("MANIFEST_ERROR", rel, None, "`entries` must be a list")]

    findings: list[Finding] = []
    valid: list[dict[str, Any]] = []
    for index, entry in enumerate(data["entries"]):
        errors = _entry_errors(entry)
        context = (
            entry.get("context")
            if isinstance(entry, dict) and isinstance(entry.get("context"), str)
            else None
        )
        if errors:
            findings.extend(
                Finding("MANIFEST_ERROR", rel, context, f"entry #{index + 1}: {e}")
                for e in errors
            )
            continue
        if behavior_digest(entry["behavior"]) != entry["sha256"]:
            findings.append(
                Finding(
                    "DIGEST_MISMATCH",
                    entry["file"],
                    context,
                    f"stored sha256 {entry['sha256']} != sha256(stored behavior) {behavior_digest(entry['behavior'])}",
                )
            )
        valid.append(entry)
    if not findings and text != render_manifest(data):
        findings.append(
            Finding(
                "MANIFEST_ERROR",
                rel,
                None,
                "manifest is not in canonical form (sorted entries, sorted keys, 2-space indent); "
                "regenerate with --update-baseline and review the diff",
            )
        )
    return valid, findings


# ---------------------------------------------------------------- verification
def _render_behavior(behavior: dict[str, Any]) -> list[str]:
    lines = [
        f"shell: {json.dumps(behavior['shell'], ensure_ascii=False)}",
        f"working_directory: {json.dumps(behavior['working_directory'], ensure_ascii=False)}",
        f"env: {json.dumps(behavior['env'], sort_keys=True, ensure_ascii=False)}",
        "run:",
    ]
    lines.extend(line.replace("\r", "\\r") for line in behavior["run"].split("\n"))
    return lines


def verify(repo_root: Path, manifest_path: Path | None = None) -> list[Finding]:
    repo_root = Path(repo_root)
    scan = _scan(repo_root)
    findings = list(scan.findings)
    entries, manifest_findings = load_manifest(
        manifest_path or repo_root / MANIFEST_REL
    )
    findings.extend(manifest_findings)
    if entries is None:
        return _sorted(findings)

    current = {block.context: block for block in scan.blocks}
    authorized: dict[str, dict[str, Any]] = {}
    for entry in entries:
        context = entry["context"]
        if context in authorized:
            findings.append(
                Finding(
                    "DUPLICATE_ENTRY",
                    entry["file"],
                    context,
                    "context appears more than once in the manifest",
                )
            )
            continue
        authorized[context] = entry

    for context, entry in sorted(authorized.items()):
        block = current.get(context)
        if block is None:
            findings.append(
                Finding(
                    "STALE_ENTRY",
                    entry["file"],
                    context,
                    "no current install-relevant run block has this context; the authorization must be removed "
                    "from the manifest (or the context restored)",
                )
            )
            continue
        actual = behavior_digest(block.behavior)
        if block.behavior != entry["behavior"] or actual != entry["sha256"]:
            diff = "\n".join(
                difflib.unified_diff(
                    _render_behavior(entry["behavior"]),
                    _render_behavior(block.behavior),
                    fromfile="baseline",
                    tofile="current",
                    lineterm="",
                )
            )
            findings.append(
                Finding(
                    "CHANGED_BLOCK",
                    block.file,
                    context,
                    f"expected sha256 {entry['sha256']}, actual sha256 {actual}; baseline reason: {entry['reason']}\n{diff}",
                )
            )

    for context, block in sorted(current.items()):
        if context not in authorized:
            rendered = "\n".join(
                "    " + line for line in _render_behavior(block.behavior)
            )
            findings.append(
                Finding(
                    "UNKNOWN_BLOCK",
                    block.file,
                    context,
                    f"unauthorized install-relevant run block (sha256 {behavior_digest(block.behavior)}); "
                    f"review it and add a baseline entry with --update-baseline:\n{rendered}",
                )
            )
    return _sorted(findings)


# -------------------------------------------------------------- baseline update
def build_manifest(repo_root: Path, existing: dict[str, Any] | None) -> dict[str, Any]:
    blocks, findings = collect_blocks(Path(repo_root))
    if findings:
        raise GuardError(
            "refusing to build a baseline while the scan has errors:\n"
            + "\n".join(map(str, findings))
        )
    previous: dict[str, dict[str, Any]] = {}
    if existing is not None:
        if not isinstance(existing, dict) or not isinstance(
            existing.get("entries"), list
        ):
            raise GuardError(
                "existing manifest is not a valid object with an `entries` list"
            )
        for entry in existing["entries"]:
            if isinstance(entry, dict) and isinstance(entry.get("context"), str):
                previous.setdefault(entry["context"], entry)

    def keep(old: dict[str, Any], key: str, placeholder: str) -> str:
        value = old.get(key)
        return value if isinstance(value, str) else placeholder

    entries = []
    for block in blocks:
        old = previous.get(block.context, {})
        entries.append(
            {
                "context": block.context,
                "file": block.file,
                "sha256": behavior_digest(block.behavior),
                "behavior": block.behavior,
                "reason": keep(
                    old,
                    "reason",
                    f"{PLACEHOLDER_PREFIX}: explain why this install block is needed",
                ),
                "owner": keep(old, "owner", PLACEHOLDER_PREFIX),
                "remediation_issue": keep(old, "remediation_issue", PLACEHOLDER_PREFIX),
            }
        )
    return {"schema": MANIFEST_SCHEMA, "entries": entries}


# ------------------------------------------------------------------------- CLI
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="LOCAL operator action: regenerate the manifest for human review (never in CI)",
    )
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    manifest_path = repo_root / MANIFEST_REL

    if args.update_baseline:
        existing = None
        try:
            if manifest_path.exists():
                existing, _ = _read_manifest_json(manifest_path)
            manifest = build_manifest(repo_root, existing)
        except (OSError, UnicodeDecodeError, ValueError, GuardError) as exc:
            print(f"INSTALL DRIFT GUARD: baseline update refused: {exc}")
            return 2
        manifest_path.write_bytes(render_manifest(manifest).encode("utf-8"))
        todo = sum(
            1
            for e in manifest["entries"]
            if str(e["reason"]).startswith(PLACEHOLDER_PREFIX)
        )
        print(
            f"Wrote {MANIFEST_REL}: {len(manifest['entries'])} entries, {todo} need review (TODO)."
        )
        print(
            "Review the manifest diff; fill reason/owner/remediation_issue before committing."
        )
        return 0

    findings = verify(repo_root, manifest_path)
    if findings:
        print(f"INSTALL DRIFT GUARD: FAIL ({len(findings)} finding(s))")
        for finding in findings:
            print(f"\n[{finding.code}] {finding.context or finding.file or '-'}")
            if finding.file:
                print(f"  file: {finding.file}")
            for line in finding.message.split("\n"):
                print(f"  {line}")
        print(
            "\nThis guard is a drift detector, not a malicious-author security boundary."
        )
        return 1
    blocks, _ = collect_blocks(repo_root)
    print(
        f"INSTALL DRIFT GUARD: PASS ({len(blocks)} authorized install-relevant run blocks)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
