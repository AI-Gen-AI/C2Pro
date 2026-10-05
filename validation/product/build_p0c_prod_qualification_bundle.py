#!/usr/bin/env python3
"""Build the non-authoritative P0c production-qualification evidence bundle."""

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
RUN_JSON = Path("apps/web/playwright/.prod-p0c/run.json")
VERIFIER_JSON = Path("evidence/product-qualification/runtime/p0c-verifier.json")
OUTPUT_ROOT = Path("evidence/product-qualification")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class BundleBuildError(RuntimeError):
    pass


def _sha(value: str, label: str) -> str:
    normalized = value.strip().lower()
    if not SHA_RE.fullmatch(normalized):
        raise BundleBuildError(f"{label} must be a 40-character Git SHA")
    return normalized


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    target = REPO_ROOT / path
    if not target.is_file():
        raise BundleBuildError(f"missing evidence file: {path}")
    value = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BundleBuildError(f"{path} must contain a JSON object")
    return value


def _control_at_head(control_commit_sha: str) -> dict[str, Any]:
    checked_out = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if checked_out != control_commit_sha:
        raise BundleBuildError("control commit must match checked-out HEAD")
    value = yaml.safe_load((REPO_ROOT / CONTROL_PATH).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BundleBuildError("Product Control must be a mapping")
    return value


def build_bundle(
    *,
    control_commit_sha: str,
    backend_commit_sha: str,
    backend_deployment_id: str,
    frontend_commit_sha: str,
    frontend_deployment_id: str,
    github_run_id: int,
    github_run_attempt: int,
    observed_at: str | None = None,
) -> dict[str, Any]:
    run = _load_json(RUN_JSON)
    verifier = _load_json(VERIFIER_JSON)

    if run.get("classification") != "USABLE":
        raise BundleBuildError("browser P0c journey is not USABLE")
    if run.get("relogin_verified") is not True:
        raise BundleBuildError("browser P0c journey did not prove relogin durability")
    if run.get("unchanged_controls_not_reported_changed") is not True:
        raise BundleBuildError("browser P0c journey did not prove unchanged controls")
    if run.get("all_reported_changes_evidence_backed") is not True:
        raise BundleBuildError("browser P0c journey did not prove evidence-backed changes")
    if verifier.get("verdict") != "PASS":
        raise BundleBuildError("read-only P0c verifier did not PASS")

    identifiers = verifier.get("identifiers")
    if not isinstance(identifiers, dict):
        raise BundleBuildError("P0c verifier identifiers are missing")
    required_ids = (
        "project_id",
        "document_id",
        "from_revision_id",
        "to_revision_id",
        "change_event_id",
    )
    for key in required_ids:
        if not isinstance(identifiers.get(key), str) or not identifiers[key]:
            raise BundleBuildError(f"missing verifier identifier {key}")
        if run.get(key) != identifiers[key]:
            raise BundleBuildError(f"browser/verifier identifier mismatch: {key}")

    checks = verifier.get("checks")
    if not isinstance(checks, list) or not checks or any(
        not isinstance(item, dict) or item.get("passed") is not True for item in checks
    ):
        raise BundleBuildError("P0c verifier contains a failed or malformed check")

    control = _control_at_head(control_commit_sha)
    production = control.get("production_position")
    if not isinstance(production, dict):
        raise BundleBuildError("Product Control production_position is missing")
    baseline = production.get("reconciled_against_main_sha")
    if not isinstance(baseline, str) or not SHA_RE.fullmatch(baseline):
        raise BundleBuildError("Product Control production baseline is invalid")

    run_path = REPO_ROOT / RUN_JSON
    verifier_path = REPO_ROOT / VERIFIER_JSON
    run_digest = _sha256(run_path)
    verifier_digest = _sha256(verifier_path)
    observed = observed_at or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    evidence_refs = [
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
            "id": "source-revision",
            "kind": "persisted_entity",
            "ref": f"postgres:document_revision:{identifiers['from_revision_id']}",
            "immutable": True,
            "sha256": None,
        },
        {
            "id": "target-revision",
            "kind": "persisted_entity",
            "ref": f"postgres:document_revision:{identifiers['to_revision_id']}",
            "immutable": True,
            "sha256": None,
        },
        {
            "id": "change-event",
            "kind": "persisted_entity",
            "ref": f"postgres:project_event:{identifiers['change_event_id']}",
            "immutable": True,
            "sha256": None,
        },
        {
            "id": "browser-run",
            "kind": "ui_report",
            "ref": "artifact:playwright/.prod-p0c/run.json",
            "immutable": False,
            "sha256": run_digest,
        },
        {
            "id": "db-verifier",
            "kind": "test_report",
            "ref": "artifact:product-qualification/runtime/p0c-verifier.json",
            "immutable": False,
            "sha256": verifier_digest,
        },
    ]

    common = ["browser-run", "db-verifier", "source-revision", "target-revision", "change-event"]
    assertions = [
        {"id": "durable_revision_bound_events", "status": "PASS", "evidence_refs": common},
        {"id": "timeline_queryable", "status": "PASS", "evidence_refs": ["browser-run", "change-event"]},
        {"id": "semantic_change_source_traceable", "status": "PASS", "evidence_refs": common},
        {"id": "api_ui_projection_parity", "status": "PASS", "evidence_refs": ["browser-run", "db-verifier"]},
        {
            "id": "absent_evidence_does_not_invent_change",
            "status": "PASS",
            "evidence_refs": ["browser-run", "db-verifier"],
            "note": "Every reported change is evidence-backed and unchanged control facts are absent from the reported changeset.",
        },
    ]

    return {
        "schema": "c2pro-product-qualification-evidence-v1",
        "schema_version": 1,
        "lifecycle_authority": False,
        "repository": REPOSITORY,
        "control_ref": CONTROL_PATH,
        "control_commit_sha": control_commit_sha,
        "control_baseline_sha": baseline,
        "capability_id": "P0c",
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
            "id": "what_changed_two_revisions",
            "identifiers": {
                "project_id": identifiers["project_id"],
                "document_id": identifiers["document_id"],
                "from_revision_id": identifiers["from_revision_id"],
                "to_revision_id": identifiers["to_revision_id"],
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
    parser.add_argument("--github-run-id", required=True, type=int)
    parser.add_argument("--github-run-attempt", required=True, type=int)
    parser.add_argument("--observed-at")
    args = parser.parse_args()

    try:
        bundle = build_bundle(
            control_commit_sha=_sha(args.control_commit_sha, "control commit"),
            backend_commit_sha=_sha(args.backend_commit_sha, "backend commit"),
            backend_deployment_id=args.backend_deployment_id,
            frontend_commit_sha=_sha(args.frontend_commit_sha, "frontend commit"),
            frontend_deployment_id=args.frontend_deployment_id,
            github_run_id=args.github_run_id,
            github_run_attempt=args.github_run_attempt,
            observed_at=args.observed_at,
        )
    except Exception as exc:
        raise SystemExit(
            f"FAIL: P0c qualification bundle build failed ({type(exc).__name__}: {exc})"
        ) from exc

    output = REPO_ROOT / OUTPUT_ROOT / f"p0c-prod-gh-{args.github_run_id}-{args.github_run_attempt}.yaml"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        yaml.safe_dump(bundle, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )
    print(f"PASS: wrote P0c qualification bundle to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
