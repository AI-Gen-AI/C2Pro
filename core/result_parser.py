"""Parser and validator for c2pro-implementation-result-v1 schema (G1)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
WORK_ID_RE = re.compile(r"^C2PRO-[A-Z0-9-]+$")


def extract_result_block(text: str) -> str:
    """Extracts the YAML result block from text, falling back to whole text if not fenced."""
    fenced = find_fenced_block(text)
    if fenced:
        return fenced
    return text


def find_fenced_block(text: str) -> str | None:
    """Finds a fenced code block with schema: c2pro-implementation-result-v1."""
    pattern = r"```(?:yaml)?\s*\n(schema:\s*c2pro-implementation-result-v1[\s\S]*?)\n```"
    match = re.search(pattern, text)
    if match:
        return match.group(1)
    return None


def parse_result_yaml(yaml_text: str) -> dict[str, Any]:
    """Parses a YAML string into a dictionary."""
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse YAML: {e}")

    if not isinstance(data, dict):
        raise TypeError("Parsed data is not a dictionary mapping")
    return data


def validate_result(result: dict[str, Any], expected_head_sha: str | None = None) -> None:
    """Validates a result dictionary against c2pro-implementation-result-v1 rules."""
    if not isinstance(result, dict):
        raise TypeError("Result must be a dictionary")

    # 1. schema exact
    if result.get("schema") != "c2pro-implementation-result-v1":
        raise ValueError(
            f"Invalid schema: expected 'c2pro-implementation-result-v1', got {result.get('schema')!r}"
        )

    # 2. work_id valid
    work_id = result.get("work_id")
    if not work_id or not isinstance(work_id, str) or not WORK_ID_RE.match(work_id):
        raise ValueError(f"Invalid work_id: {work_id!r}")

    # 3. SHA format
    base_sha = result.get("base_sha")
    if not base_sha or not isinstance(base_sha, str) or not SHA_RE.match(base_sha):
        raise ValueError(f"Invalid base_sha format: {base_sha!r}")

    head_sha = result.get("head_sha")
    if not head_sha or not isinstance(head_sha, str) or not SHA_RE.match(head_sha):
        raise ValueError(f"Invalid head_sha format: {head_sha!r}")

    # 4. head_sha matches expected PR head when supplied by CI
    if expected_head_sha and head_sha != expected_head_sha:
        raise ValueError(
            f"head_sha mismatch: expected PR head {expected_head_sha}, got {head_sha}"
        )

    # 5. branch check
    branch = result.get("branch")
    if not branch or not isinstance(branch, str):
        raise ValueError("branch must be a non-empty string")

    # 6. files_changed is structured (must be a list)
    files_changed = result.get("files_changed")
    if not isinstance(files_changed, list):
        raise TypeError("files_changed must be a list/array")

    # 7. tests is structured (must be a list)
    tests = result.get("tests")
    if not isinstance(tests, list):
        raise TypeError("tests must be a list/array")

    # 8. recommendation enum
    rec = result.get("recommendation")
    if rec not in ["approve", "remediate", "escalate"]:
        raise ValueError(
            f"Invalid recommendation: must be 'approve', 'remediate', or 'escalate', got {rec!r}"
        )

    # 9. JSON schema validation (optional extra layer of verification)
    schema_path = Path(__file__).resolve().parent.parent / ".c2pro" / "schemas" / "implementation-result.schema.yaml"
    if schema_path.exists():
        try:
            import jsonschema
            with open(schema_path, encoding="utf-8") as f:
                schema_data = yaml.safe_load(f)
            jsonschema.validate(instance=result, schema=schema_data)
        except ImportError:
            pass  # jsonschema not installed, fallback to built-in checks
        except Exception as e:  # noqa: BLE001
            raise ValueError(f"JSON schema validation failed: {e}")
