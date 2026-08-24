#!/usr/bin/env python3
"""Validate the compact C2Pro development-control surface.

C2PRO-DEV-01 keeps completed history out of hot state and validates the
machine-readable control files without activating any development runtime.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft7Validator

REPO_ROOT = Path(__file__).resolve().parents[1]
C2PRO_ROOT = REPO_ROOT / ".c2pro"
CONTROL_ROOT = C2PRO_ROOT / "control"
SCHEMA_ROOT = C2PRO_ROOT / "schemas"

CANONICAL = {
    CONTROL_ROOT / "current.yaml": SCHEMA_ROOT / "current.schema.json",
    CONTROL_ROOT / "work-queue.yaml": SCHEMA_ROOT / "work-queue.schema.json",
    CONTROL_ROOT / "legacy-compatibility.yaml": SCHEMA_ROOT / "legacy-compatibility.schema.json",
    CONTROL_ROOT / "context-budget.yaml": SCHEMA_ROOT / "context-budget.schema.json",
}

OPTIONAL_COLLECTIONS = {
    C2PRO_ROOT / "work": SCHEMA_ROOT / "work-envelope.schema.json",
    C2PRO_ROOT / "handoff": SCHEMA_ROOT / "handoff.schema.json",
    C2PRO_ROOT / "evidence": SCHEMA_ROOT / "evidence-reference.schema.json",
}


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected YAML mapping")
    return data


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected JSON object")
    return data


def validate_file(data_path: Path, schema_path: Path) -> list[str]:
    schema = load_json(schema_path)
    Draft7Validator.check_schema(schema)
    validator = Draft7Validator(schema)
    data = load_yaml(data_path)
    errors = []
    for err in sorted(validator.iter_errors(data), key=lambda item: list(item.path)):
        location = ".".join(str(part) for part in err.path) or "root"
        errors.append(f"{data_path.relative_to(REPO_ROOT)} [{location}] {err.message}")
    return errors


def validate_context_budget() -> list[str]:
    budget = load_yaml(CONTROL_ROOT / "context-budget.yaml")
    limit = budget["limits"]["bootstrap_hot_state_max"]
    hot_paths = [REPO_ROOT / path for path in budget["default_hot_files"]]
    total = sum(path.stat().st_size for path in hot_paths)
    if total > limit:
        return [f"default hot state is {total} bytes; limit is {limit} bytes"]
    return []


def validate_transition_invariants() -> list[str]:
    queue = load_yaml(CONTROL_ROOT / "work-queue.yaml")
    current = load_yaml(CONTROL_ROOT / "current.yaml")
    compatibility = load_yaml(CONTROL_ROOT / "legacy-compatibility.yaml")
    errors = []

    if queue["completed_work_retained"] is not False:
        errors.append("work queue must never retain completed history")
    if current["history"]["completed_work_retained_in_hot_state"] is not False:
        errors.append("current state must never retain completed history")
    if compatibility["new_control_runtime_authoritative"] is not False:
        errors.append("DEV-01 must not activate the new runtime authority")
    if compatibility["legacy_open_work_authoritative_until_reconciled"] is not True:
        errors.append("legacy open work must remain authoritative until reconciliation")
    return errors


def main() -> int:
    errors: list[str] = []

    for data_path, schema_path in CANONICAL.items():
        errors.extend(validate_file(data_path, schema_path))

    for directory, schema_path in OPTIONAL_COLLECTIONS.items():
        if not directory.exists():
            continue
        for data_path in sorted(directory.glob("*.yaml")):
            errors.extend(validate_file(data_path, schema_path))

    errors.extend(validate_context_budget())
    errors.extend(validate_transition_invariants())

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    budget = load_yaml(CONTROL_ROOT / "context-budget.yaml")
    total = sum((REPO_ROOT / path).stat().st_size for path in budget["default_hot_files"])
    print(f"C2PRO_CONTROL_VALID=1 bootstrap_hot_bytes={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
