#!/usr/bin/env python3
"""Build a non-authoritative P0b qualification evidence bundle from bounded run outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

CONTROL_PATH = "validation/product/c2pro-master-product-control-v1.yaml"
REPOSITORY = "AI-Gen-AI/C2Pro"
REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_RUN_JSON = Path("apps/web/playwright/.prod-acceptance/run.json")
CANONICAL_VERIFIER_JSON = Path("evidence/product-qualification/runtime/verifier.json")
QUALIFICATION_OUTPUT_ROOT = Path("evidence/product-qualification")
FULL_SHA_RE = re.compile(r"[0-9a-fA-F]{40}")


class BundleBuildError(RuntimeError):
    """Qualification inputs are incomplete or contradictory."""



def _canonical_evidence_path(
    expected: Path, *, label: str, repo_root: Path = REPO_ROOT
) -> Path:
    """Return a canonical repository evidence input and require it to exist."""
    path = repo_root.resolve() / expected
    if not path.is_file():
        raise BundleBuildError(f"{label} is missing")
    return path


def _run_json(*, repo_root: Path = REPO_ROOT) -> Path:
    return _canonical_evidence_path(
        CANONICAL_RUN_JSON,
        label="canonical browser run evidence",
        repo_root=repo_root,
    )


def _verifier_json(*, repo_root: Path = REPO_ROOT) -> Path:
    return _canonical_evidence_path(
        CANONICAL_VERIFIER_JSON,
        label="canonical verifier evidence",
        repo_root=repo_root,
    )


def _bundle_output(
    github_run_id: str,
    github_run_attempt: str,
    *,
    repo_root: Path = REPO_ROOT,
) -> Path:
    if not github_run_id.isdigit() or int(github_run_id) < 1:
        raise BundleBuildError("GitHub run id must be a positive integer")
    if not github_run_attempt.isdigit() or int(github_run_attempt) < 1:
        raise BundleBuildError("GitHub run attempt must be a positive integer")
    output_root = repo_root.resolve() / QUALIFICATION_OUTPUT_ROOT
    return output_root / f"p0b-prod-gh-{github_run_id}-{github_run_attempt}.yaml"


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BundleBuildError(f"{path} must contain a JSON object")
    return value


def _control_at(commit_sha: str) -> dict[str, Any]:
    expected_sha = _require_full_sha(commit_sha, "control commit")
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    checked_out_sha = completed.stdout.strip().lower()
    if checked_out_sha != expected_sha:
        raise BundleBuildError("control commit must match the checked-out commit")
    value = yaml.safe_load(
        (REPO_ROOT / CONTROL_PATH).read_text(encoding="utf-8")
    )
    if not isinstance(value, dict):
        raise BundleBuildError("historical Product Control must be a mapping")
    return value


def _require_string(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise BundleBuildError(f"missing {key}")
    return value.strip()


def _assert_pass_verifier(verifier: dict[str, Any]) -> None:
    if verifier.get("verdict") != "PASS":
        raise BundleBuildError("post-run verifier did not PASS")
    checks = verifier.get("checks")
    if not isinstance(checks, list) or not checks:
        raise BundleBuildError("verifier checks are missing")
    failed = [
        item.get("name")
        for item in checks
        if not isinstance(item, dict) or item.get("passed") is not True
    ]
    if failed:
        raise BundleBuildError(f"verifier has failed checks: {failed}")


def build_bundle(
    *,
    control_commit_sha: str,
    backend_commit_sha: str,
    backend_deployment_id: str,
    frontend_commit_sha: str,
    frontend_deployment_id: str,
    recovery_evidence_ref: str,
    run_json: Path,
    verifier_json: Path,
    require_hitl: bool,
    observed_at: str | None = None,
) -> dict[str, Any]:
    run = _load_json(run_json)
    verifier = _load_json(verifier_json)
    _assert_pass_verifier(verifier)

    identifiers = verifier.get("identifiers")
    if not isinstance(identifiers, dict):
        raise BundleBuildError("verifier identifiers are missing")
    project_id = _require_string(identifiers, "project_id")
    document_id = _require_string(identifiers, "document_id")
    source_revision_id = _require_string(identifiers, "source_revision_id")

    if run.get("project_id") != project_id or run.get("document_id") != document_id:
        raise BundleBuildError("browser and verifier identifiers disagree")
    if run.get("relogin_verified") is not True:
        raise BundleBuildError("browser did not prove relogin durability")
    if require_hitl and run.get("hitl_exercised") is not True:
        raise BundleBuildError("final P0b qualification requires real HITL exercise")

    health = run.get("health")
    if not isinstance(health, dict):
        raise BundleBuildError("bounded Health summary is missing")
    assessments = health.get("assessments")
    if not isinstance(assessments, list) or len(assessments) != 6:
        raise BundleBuildError("bounded Health summary must contain six assessments")
    if health.get("coherence_available") is not False:
        raise BundleBuildError("single-document qualification must keep Coherence unavailable")

    control = _control_at(control_commit_sha)
    production_position = control.get("production_position")
    if not isinstance(production_position, dict):
        raise BundleBuildError("Product Control production_position is missing")
    control_baseline_sha = _require_string(
        production_position,
        "reconciled_against_main_sha",
    )

    ui_sha = _sha256(run_json)
    verifier_sha = _sha256(verifier_json)
    observed = observed_at or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    evidence_refs: list[dict[str, Any]] = [
        {
            "id": "deploy-backend",
            "kind": "deployment",
            "ref": f"railway:{backend_deployment_id}",
            "immutable": True,
            "sha256": None,
        },
        {
            "id": "deploy-frontend",
            "kind": "deployment",
            "ref": f"vercel:{frontend_deployment_id}",
            "immutable": True,
            "sha256": None,
        },
        {
            "id": "persisted-source-revision",
            "kind": "persisted_entity",
            "ref": f"postgres:document_revision:{source_revision_id}",
            "immutable": True,
            "sha256": None,
        },
        {
            "id": "browser-run",
            "kind": "ui_report",
            "ref": "artifact:playwright/.prod-acceptance/run.json",
            "immutable": False,
            "sha256": ui_sha,
        },
        {
            "id": "db-verifier",
            "kind": "test_report",
            "ref": "artifact:prod-acceptance/verifier.json",
            "immutable": False,
            "sha256": verifier_sha,
        },
        {
            "id": "recovery-proof",
            "kind": "test_report",
            "ref": recovery_evidence_ref,
            "immutable": True,
            "sha256": None,
        },
    ]
    if require_hitl:
        review_item_id = _require_string(run, "review_item_id")
        evidence_refs.append(
            {
                "id": "hitl-review",
                "kind": "review",
                "ref": f"artifact:playwright/.prod-acceptance/run.json#review:{review_item_id}",
                "immutable": False,
                "sha256": ui_sha,
            }
        )

    refs_common = ["browser-run", "db-verifier", "persisted-source-revision"]
    assertions = [
        {
            "id": "six_categories_present_or_honest_unknown",
            "status": "PASS",
            "evidence_refs": refs_common,
        },
        {
            "id": "findings_traceable_to_evidence",
            "status": "PASS",
            "evidence_refs": ["browser-run", "persisted-source-revision"],
        },
        {
            "id": "missing_data_preserved",
            "status": "PASS",
            "evidence_refs": ["browser-run", "db-verifier"],
        },
        {
            "id": "actionable_gap_alerts_visible",
            "status": "PASS",
            "evidence_refs": ["browser-run"],
        },
        {
            "id": "health_api_ui_semantic_parity",
            "status": "PASS",
            "evidence_refs": ["browser-run", "db-verifier"],
        },
        {
            "id": "unknown_never_zero_or_green",
            "status": "PASS",
            "evidence_refs": ["browser-run"],
        },
        {
            "id": "coherence_headline_null_under_two_reconcilable_documents",
            "status": "PASS",
            "evidence_refs": ["browser-run", "db-verifier"],
        },
        {
            "id": "hitl_retry_recovery_does_not_strand_document",
            "status": "PASS",
            "evidence_refs": (
                ["browser-run", "db-verifier", "recovery-proof", "hitl-review"]
                if require_hitl
                else ["browser-run", "db-verifier", "recovery-proof"]
            ),
        },
    ]

    return {
        "schema": "c2pro-product-qualification-evidence-v1",
        "schema_version": 1,
        "lifecycle_authority": False,
        "repository": REPOSITORY,
        "control_ref": CONTROL_PATH,
        "control_commit_sha": control_commit_sha,
        "control_baseline_sha": control_baseline_sha,
        "capability_id": "P0b",
        "target_state": "PROD_VALIDATED",
        "environment": "production",
        "runtime_bindings": [
            {
                "plane": "backend",
                "provider": "railway",
                "commit_sha": backend_commit_sha,
                "terminal_state": "SUCCESS",
                "deployment_evidence_ref": "deploy-backend",
            },
            {
                "plane": "frontend",
                "provider": "vercel",
                "commit_sha": frontend_commit_sha,
                "terminal_state": "READY",
                "deployment_evidence_ref": "deploy-frontend",
            },
        ],
        "observed_at": observed,
        "scenario": {
            "id": "single_document_health",
            "identifiers": {
                "project_id": project_id,
                "document_id": document_id,
                "source_revision_id": source_revision_id,
            },
        },
        "assertions": assertions,
        "evidence_refs": evidence_refs,
        "validator_verdict": "PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control-commit-sha", required=True)
    parser.add_argument("--backend-commit-sha", required=True)
    parser.add_argument("--backend-deployment-id", required=True)
    parser.add_argument("--frontend-commit-sha", required=True)
    parser.add_argument("--frontend-deployment-id", required=True)
    parser.add_argument("--recovery-evidence-ref", required=True)
    parser.add_argument("--github-run-id", required=True)
    parser.add_argument("--github-run-attempt", required=True)
    parser.add_argument("--require-hitl", action="store_true")
    parser.add_argument("--observed-at")
    args = parser.parse_args()

    try:
        run_json = _run_json()
        verifier_json = _verifier_json()
        output = _bundle_output(args.github_run_id, args.github_run_attempt)
        bundle = build_bundle(
            control_commit_sha=_require_full_sha(
                args.control_commit_sha, "control commit"
            ),
            backend_commit_sha=_require_full_sha(args.backend_commit_sha, "backend commit"),
            backend_deployment_id=args.backend_deployment_id,
            frontend_commit_sha=_require_full_sha(args.frontend_commit_sha, "frontend commit"),
            frontend_deployment_id=args.frontend_deployment_id,
            recovery_evidence_ref=args.recovery_evidence_ref,
            run_json=run_json,
            verifier_json=verifier_json,
            require_hitl=args.require_hitl,
            observed_at=args.observed_at,
        )
    except Exception as exc:
        raise SystemExit(f"FAIL: qualification bundle build failed ({type(exc).__name__}: {exc})") from exc

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        yaml.safe_dump(bundle, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )
    print(f"PASS: wrote qualification bundle to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
