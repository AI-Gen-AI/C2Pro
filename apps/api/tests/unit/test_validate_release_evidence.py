"""TS-CICD-G7-VAL-001

Regression checks for Gate 7 release evidence validation.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


def _load_module():
    repo_root = Path(__file__).resolve().parents[4]
    module_path = repo_root / "scripts" / "validate_release_evidence.py"
    spec = importlib.util.spec_from_file_location("validate_release_evidence", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_release_bundle(bundle_dir: Path, manifest_text: str) -> None:
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "manifest.yaml").write_text(manifest_text, encoding="utf-8")
    (bundle_dir / "signoff.md").write_text("# signoff\n", encoding="utf-8")
    (bundle_dir / "performance.md").write_text("# performance\n", encoding="utf-8")
    (bundle_dir / "disaster-recovery.md").write_text("# dr\n", encoding="utf-8")


def test_validator_rejects_manifest_when_required_suite_is_not_green(tmp_path: Path) -> None:
    module = _load_module()
    bundle_dir = tmp_path / "evidence" / "releases" / "2026-03-22-rc1"

    _write_release_bundle(
        bundle_dir,
        """
release_id: 2026-03-22-rc1
commit_sha: abc123
required_suites:
  backend:
    status: pass
    artifact: backend-release-summary
  frontend:
    status: fail
    artifact: frontend-release-summary
  security:
    status: pass
    artifact: security-release-summary
  evaluation:
    status: pass
    artifact: evaluation-release-summary
  reliability:
    status: pass
    artifact: i13-release-summary
swagger_workbook:
  status: complete
  unchecked_items: []
manual_signoff:
  product: Product Owner
  security: Security Owner
  operations: Ops Owner
  release_authority: Release Owner
performance:
  result: pass
  report: performance.md
dr_evidence:
  result: pass
  report: disaster-recovery.md
waivers: []
""".strip(),
    )

    with pytest.raises(module.ReleaseEvidenceValidationError, match="frontend"):
        module.validate_release_bundle(bundle_dir, expected_commit_sha="abc123")


def test_validator_rejects_manifest_when_required_signoff_owner_is_missing(tmp_path: Path) -> None:
    module = _load_module()
    bundle_dir = tmp_path / "evidence" / "releases" / "2026-03-22-rc1"

    _write_release_bundle(
        bundle_dir,
        """
release_id: 2026-03-22-rc1
commit_sha: abc123
required_suites:
  backend:
    status: pass
    artifact: backend-release-summary
  frontend:
    status: pass
    artifact: frontend-release-summary
  security:
    status: pass
    artifact: security-release-summary
  evaluation:
    status: pass
    artifact: evaluation-release-summary
  reliability:
    status: pass
    artifact: i13-release-summary
swagger_workbook:
  status: complete
  unchecked_items: []
manual_signoff:
  product: Product Owner
  security: ""
  operations: Ops Owner
  release_authority: Release Owner
performance:
  result: pass
  report: performance.md
dr_evidence:
  result: pass
  report: disaster-recovery.md
waivers: []
""".strip(),
    )

    with pytest.raises(module.ReleaseEvidenceValidationError, match="security"):
        module.validate_release_bundle(bundle_dir, expected_commit_sha="abc123")


def test_validator_rejects_manifest_when_dr_or_performance_records_fail(tmp_path: Path) -> None:
    module = _load_module()
    bundle_dir = tmp_path / "evidence" / "releases" / "2026-03-22-rc1"

    _write_release_bundle(
        bundle_dir,
        """
release_id: 2026-03-22-rc1
commit_sha: abc123
required_suites:
  backend:
    status: pass
    artifact: backend-release-summary
  frontend:
    status: pass
    artifact: frontend-release-summary
  security:
    status: pass
    artifact: security-release-summary
  evaluation:
    status: pass
    artifact: evaluation-release-summary
  reliability:
    status: pass
    artifact: i13-release-summary
swagger_workbook:
  status: complete
  unchecked_items: []
manual_signoff:
  product: Product Owner
  security: Security Owner
  operations: Ops Owner
  release_authority: Release Owner
performance:
  result: fail
  report: performance.md
dr_evidence:
  result: fail
  report: disaster-recovery.md
waivers: []
""".strip(),
    )

    with pytest.raises(module.ReleaseEvidenceValidationError, match="performance"):
        module.validate_release_bundle(bundle_dir, expected_commit_sha="abc123")


def test_validator_rejects_manifest_when_required_suite_artifact_is_missing(tmp_path: Path) -> None:
    module = _load_module()
    bundle_dir = tmp_path / "evidence" / "releases" / "2026-03-22-rc1"

    _write_release_bundle(
        bundle_dir,
        """
release_id: 2026-03-22-rc1
commit_sha: abc123
required_suites:
  backend:
    status: pass
    artifact: backend-release-summary
  frontend:
    status: pass
    artifact: frontend-release-summary
  security:
    status: pass
    artifact: ""
  evaluation:
    status: pass
    artifact: evaluation-release-summary
  reliability:
    status: pass
    artifact: i13-release-summary
swagger_workbook:
  status: complete
  unchecked_items: []
manual_signoff:
  product: Product Owner
  security: Security Owner
  operations: Ops Owner
  release_authority: Release Owner
performance:
  result: pass
  report: performance.md
dr_evidence:
  result: pass
  report: disaster-recovery.md
waivers: []
""".strip(),
    )

    with pytest.raises(module.ReleaseEvidenceValidationError, match="security"):
        module.validate_release_bundle(bundle_dir, expected_commit_sha="abc123")


def test_validator_rejects_manifest_when_required_reports_are_missing(tmp_path: Path) -> None:
    module = _load_module()
    bundle_dir = tmp_path / "evidence" / "releases" / "2026-03-22-rc1"

    _write_release_bundle(
        bundle_dir,
        """
release_id: 2026-03-22-rc1
commit_sha: abc123
required_suites:
  backend:
    status: pass
    artifact: backend-release-summary
  frontend:
    status: pass
    artifact: frontend-release-summary
  security:
    status: pass
    artifact: security-release-summary
  evaluation:
    status: pass
    artifact: evaluation-release-summary
  reliability:
    status: pass
    artifact: i13-release-summary
swagger_workbook:
  status: complete
  unchecked_items: []
manual_signoff:
  product: Product Owner
  security: Security Owner
  operations: Ops Owner
  release_authority: Release Owner
performance:
  result: pass
  report: ""
dr_evidence:
  result: pass
waivers: []
""".strip(),
    )

    with pytest.raises(module.ReleaseEvidenceValidationError, match="report"):
        module.validate_release_bundle(bundle_dir, expected_commit_sha="abc123")


def test_validator_accepts_complete_bundle_for_matching_commit_sha(tmp_path: Path) -> None:
    module = _load_module()
    bundle_dir = tmp_path / "evidence" / "releases" / "2026-03-22-rc1"

    _write_release_bundle(
        bundle_dir,
        """
release_id: 2026-03-22-rc1
commit_sha: abc123
required_suites:
  backend:
    status: pass
    artifact: backend-release-summary
  frontend:
    status: pass
    artifact: frontend-release-summary
  security:
    status: pass
    artifact: security-release-summary
  evaluation:
    status: pass
    artifact: evaluation-release-summary
  reliability:
    status: pass
    artifact: i13-release-summary
swagger_workbook:
  status: complete
  unchecked_items: []
manual_signoff:
  product: Product Owner
  security: Security Owner
  operations: Ops Owner
  release_authority: Release Owner
performance:
  result: pass
  report: performance.md
dr_evidence:
  result: pass
  report: disaster-recovery.md
waivers: []
""".strip(),
    )

    result = module.validate_release_bundle(bundle_dir, expected_commit_sha="abc123")

    assert result.release_id == "2026-03-22-rc1"
    assert result.commit_sha == "abc123"
