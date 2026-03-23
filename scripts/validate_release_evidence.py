"""TS-CICD-G7-VAL-001

Validate Gate 7 release evidence bundles before production promotion.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ReleaseEvidenceValidationError(ValueError):
    """Raised when a release bundle is incomplete or inconsistent."""


@dataclass(frozen=True)
class ReleaseEvidenceValidationResult:
    release_id: str
    commit_sha: str
    bundle_dir: Path


REQUIRED_SUITE_NAMES = ("backend", "frontend", "security", "evaluation", "reliability")
REQUIRED_SIGNOFF_ROLES = ("product", "security", "operations", "release_authority")
REQUIRED_BUNDLE_FILES = ("manifest.yaml", "signoff.md", "performance.md", "disaster-recovery.md")


def _load_manifest(manifest_path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ReleaseEvidenceValidationError("manifest.yaml must contain a mapping at the top level")
    return loaded


def _require_non_empty_mapping_value(mapping: dict[str, Any], key: str, context: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ReleaseEvidenceValidationError(f"{context} '{key}' is required")
    return value.strip()


def validate_release_bundle(bundle_dir: Path, expected_commit_sha: str | None = None) -> ReleaseEvidenceValidationResult:
    if not bundle_dir.exists():
        raise ReleaseEvidenceValidationError(f"Release bundle directory does not exist: {bundle_dir}")

    for file_name in REQUIRED_BUNDLE_FILES:
        if not (bundle_dir / file_name).exists():
            raise ReleaseEvidenceValidationError(f"Required bundle file is missing: {file_name}")

    manifest = _load_manifest(bundle_dir / "manifest.yaml")

    release_id = _require_non_empty_mapping_value(manifest, "release_id", "manifest")
    commit_sha = _require_non_empty_mapping_value(manifest, "commit_sha", "manifest")

    if expected_commit_sha and commit_sha != expected_commit_sha:
        raise ReleaseEvidenceValidationError(
            f"manifest commit SHA '{commit_sha}' does not match expected '{expected_commit_sha}'"
        )

    required_suites = manifest.get("required_suites")
    if not isinstance(required_suites, dict):
        raise ReleaseEvidenceValidationError("manifest required_suites mapping is required")

    for suite_name in REQUIRED_SUITE_NAMES:
        suite_payload = required_suites.get(suite_name)
        if not isinstance(suite_payload, dict):
            raise ReleaseEvidenceValidationError(f"required suite '{suite_name}' is missing")
        if suite_payload.get("status") != "pass":
            raise ReleaseEvidenceValidationError(f"required suite '{suite_name}' is not green")
        _require_non_empty_mapping_value(suite_payload, "artifact", f"required suite '{suite_name}'")

    signoff = manifest.get("manual_signoff")
    if not isinstance(signoff, dict):
        raise ReleaseEvidenceValidationError("manual_signoff mapping is required")
    for role_name in REQUIRED_SIGNOFF_ROLES:
        _require_non_empty_mapping_value(signoff, role_name, "manual_signoff")

    performance = manifest.get("performance")
    if not isinstance(performance, dict) or performance.get("result") != "pass":
        raise ReleaseEvidenceValidationError("performance result must be 'pass'")
    _require_non_empty_mapping_value(performance, "report", "performance")

    dr_evidence = manifest.get("dr_evidence")
    if not isinstance(dr_evidence, dict) or dr_evidence.get("result") != "pass":
        raise ReleaseEvidenceValidationError("dr_evidence result must be 'pass'")
    _require_non_empty_mapping_value(dr_evidence, "report", "dr_evidence")

    return ReleaseEvidenceValidationResult(
        release_id=release_id,
        commit_sha=commit_sha,
        bundle_dir=bundle_dir,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Gate 7 release evidence bundle")
    parser.add_argument("--bundle-dir", required=True, help="Path to evidence/releases/<release-id>")
    parser.add_argument("--commit-sha", help="Expected commit SHA for the release candidate")
    args = parser.parse_args()

    result = validate_release_bundle(Path(args.bundle_dir), expected_commit_sha=args.commit_sha)
    print(f"Gate 7 bundle OK: release_id={result.release_id} commit_sha={result.commit_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
