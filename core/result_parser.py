"""Parser and validator for c2pro-implementation-result-v1 schema (G1)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
WORK_ID_RE = re.compile(r"^C2PRO-[A-Z0-9-]+$")
REVIEW_WORK_ID_RE = re.compile(r"^C2PRO-DEV-[0-9]{2}$")

REVIEW_REQUIRED_FIELDS = {
    "schema",
    "schema_version",
    "work_id",
    "role",
    "worker_id",
    "reviewed_pr",
    "reviewed_head_sha",
    "verdict",
    "blocking",
    "non_blocking",
    "architecture_drift",
    "security_concern",
    "scope_deviation",
    "recommended_action",
}
REVIEW_ALLOWED_ROLES = {"independent_reviewer", "qa", "security", "specialist"}
REVIEW_ALLOWED_VERDICTS = {"PASS", "PASS_WITH_FINDINGS", "BLOCK"}
REVIEW_ALLOWED_ACTIONS = {"approve", "remediate", "escalate"}


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


def _validate_review_string_list(field: str, value: object) -> None:
    if not isinstance(value, list):
        raise TypeError(f"Review {field} must be a list")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"Review {field} entries must be non-empty strings")
    if len(set(value)) != len(value):
        raise ValueError(f"Review {field} entries must be unique")


def _validate_review_shape(result: dict[str, Any]) -> None:
    """Enforce the complete v1 review schema without relying on jsonschema."""
    keys = set(result)
    missing = REVIEW_REQUIRED_FIELDS - keys
    extra = keys - REVIEW_REQUIRED_FIELDS
    if missing:
        raise ValueError(f"Review result missing required fields: {sorted(missing)}")
    if extra:
        raise ValueError(f"Review result has unsupported fields: {sorted(extra)}")

    schema_version = result.get("schema_version")
    if type(schema_version) is not int or schema_version != 1:
        raise ValueError("Review schema_version must be integer 1")

    role = result.get("role")
    if role not in REVIEW_ALLOWED_ROLES:
        raise ValueError(f"Invalid review role: {role!r}")

    worker_id = result.get("worker_id")
    if not isinstance(worker_id, str) or not worker_id.strip():
        raise ValueError("Review worker_id must be a non-empty string")

    _validate_review_string_list("blocking", result.get("blocking"))
    _validate_review_string_list("non_blocking", result.get("non_blocking"))

    for field in ("architecture_drift", "security_concern", "scope_deviation"):
        if type(result.get(field)) is not bool:
            raise TypeError(f"Review {field} must be boolean")

    if result.get("verdict") not in REVIEW_ALLOWED_VERDICTS:
        raise ValueError(f"Invalid review verdict: {result.get('verdict')!r}")
    if result.get("recommended_action") not in REVIEW_ALLOWED_ACTIONS:
        raise ValueError(
            f"Invalid review recommended_action: {result.get('recommended_action')!r}"
        )


def validate_review_result(
    result: dict[str, Any],
    *,
    expected_pr: int,
    expected_head_sha: str,
) -> None:
    """Validate c2pro-review-result-v1 against the live PR identity.

    Shape-only validation is insufficient for review evidence: the caller must
    supply the PR number and current PR head observed from the remote authority.
    A stale review therefore fails before it can be used as promotion evidence.
    """
    if not isinstance(result, dict):
        raise TypeError("Review result must be a dictionary")
    if not isinstance(expected_pr, int) or isinstance(expected_pr, bool) or expected_pr < 1:
        raise ValueError(f"Invalid expected PR number: {expected_pr!r}")
    if not isinstance(expected_head_sha, str) or not SHA_RE.fullmatch(expected_head_sha):
        raise ValueError(f"Invalid expected PR head SHA: {expected_head_sha!r}")

    if result.get("schema") != "c2pro-review-result-v1":
        raise ValueError(
            "Invalid review schema: expected 'c2pro-review-result-v1', "
            f"got {result.get('schema')!r}"
        )

    _validate_review_shape(result)

    work_id = result.get("work_id")
    if not isinstance(work_id, str) or not REVIEW_WORK_ID_RE.fullmatch(work_id):
        raise ValueError(f"Invalid review work_id: {work_id!r}")

    reviewed_pr = result.get("reviewed_pr")
    if (
        not isinstance(reviewed_pr, int)
        or isinstance(reviewed_pr, bool)
        or reviewed_pr < 1
    ):
        raise ValueError(f"Invalid reviewed_pr: {reviewed_pr!r}")
    if reviewed_pr != expected_pr:
        raise ValueError(
            f"reviewed_pr mismatch: expected live PR {expected_pr}, got {reviewed_pr}"
        )

    reviewed_head_sha = result.get("reviewed_head_sha")
    if not isinstance(reviewed_head_sha, str) or not SHA_RE.fullmatch(reviewed_head_sha):
        raise ValueError(f"Invalid reviewed_head_sha: {reviewed_head_sha!r}")
    if reviewed_head_sha != expected_head_sha:
        raise ValueError(
            "reviewed_head_sha mismatch: expected live PR head "
            f"{expected_head_sha}, got {reviewed_head_sha}"
        )

    schema_path = (
        Path(__file__).resolve().parent.parent
        / ".c2pro"
        / "schemas"
        / "review-result.schema.yaml"
    )
    if schema_path.exists():
        try:
            import jsonschema

            with open(schema_path, encoding="utf-8") as handle:
                schema_data = yaml.safe_load(handle)
            jsonschema.validate(instance=result, schema=schema_data)
        except ImportError:
            # Full v1 shape/type validation already ran above. jsonschema is
            # an optional second implementation, never the security boundary.
            pass
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Review JSON schema validation failed: {exc}") from exc

