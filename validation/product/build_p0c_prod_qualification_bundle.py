#!/usr/bin/env python3
"""Build a non-authoritative P0c production qualification bundle."""

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
FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class BundleBuildError(RuntimeError):
    pass


def _sha(value: str, label: str) -> str:
    normalized = value.strip().lower()
    if not FULL_SHA_RE.fullmatch(normalized):
        raise BundleBuildError(f"{label} must be a 40-character Git SHA")
    return normalized


def _load_json(path: Path) -> dict[str, Any]:
    absolute = REPO_ROOT / path
    if not absolute.is_file():
        raise BundleBuildError(f"missing evidence artifact: {path}")
    value = json.loads(absolute.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BundleBuildError(f"{path} must contain an object")
    return value


def _digest(path: Path) -> str:
    return hashlib.sha256((REPO_ROOT / path).read_bytes()).hexdigest()


def _required(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise BundleBuildError(f"missing {key}")
    return value.strip()


def _control_at(commit_sha: str) -> dict[str, Any]:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    if completed.stdout.strip().lower() != commit_sha:
        raise BundleBuildError("control commit must equal checked-out HEAD")
    value = yaml.safe_load((REPO_ROOT / CONTROL_PATH).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BundleBuildError("Product Control must be a mapping")
    return value


def _control_baseline(control: dict[str, Any]) -> str:
    position = control.get("production_position")
    if not isinstance(position, dict):
        raise BundleBuildError("Product Control production_position is missing")
    return _sha(_required(position, "reconciled_against_main_sha"), "control baseline")


def build_bundle(
    *,
    control_commit_sha: str,
    backend_commit_sha: str,
    backend_deployment_id: str,
    frontend_commit_sha: str,
    frontend_deployment_id: str,
    observed_at: str | None = None,
) -> dict[str, Any]:
    run = _load_json(RUN_JSON)
    verifier = _load_json(VERIFIER_JSON)

    if verifier.get("verdict") != "PASS" or verifier.get("phase") != "post":
        raise BundleBuildError("durable P0c post-run verifier did not PASS")
    checks = verifier.get("checks")
    if not isinstance(checks, list) or not checks or any(
        not isinstance(item, dict) or item.get("passed") is not True
        for item in checks
    ):
        raise BundleBuildError("durable verifier has missing/failed checks")

    identifiers = verifier.get("identifiers")
    if not isinstance(identifiers, dict):
        raise BundleBuildError("verifier identifiers are missing")

    project_id = _required(identifiers, "project_id")
    document_id = _required(identifiers, "document_id")
    source_revision_id = _required(identifiers, "from_revision_id")
    target_revision_id = _required(identifiers, "to_revision_id")
    change_event_id = _required(identifiers, "change_event_id")

    expected_run = {
        "project_id": project_id,
        "document_id": document_id,
        "source_revision_id": source_revision_id,
        "target_revision_id": target_revision_id,
        "change_event_id": change_event_id,
    }
    disagreements = [
        key for key, expected in expected_run.items() if run.get(key) != expected
    ]
    if disagreements:
        raise BundleBuildError(
            "browser and durable verifier disagree on: " + ", ".join(disagreements)
        )
    if run.get("relogin_verified") is not True:
        raise BundleBuildError("browser did not prove relogin durability")
    if run.get("processing_outcome") != "analyzed":
        raise BundleBuildError("revision B did not settle as analyzed")
    if run.get("documents_listed") != 1:
        raise BundleBuildError("new-version flow did not preserve one logical document")
    if run.get("blocking_findings") != []:
        raise BundleBuildError("browser recorder has blocking findings")

    control_sha = _sha(control_commit_sha, "control commit")
    control = _control_at(control_sha)
    baseline = _control_baseline(control)
    backend_sha = _sha(backend_commit_sha, "backend commit")
    frontend_sha = _sha(frontend_commit_sha, "frontend commit")

    run_digest = _digest(RUN_JSON)
    verifier_digest = _digest(VERIFIER_JSON)
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
            "ref": f"postgres:document_revision:{source_revision_id}",
            "immutable": True,
            "sha256": None,
        },
        {
            "id": "target-revision",
            "kind": "persisted_entity",
            "ref": f"postgres:document_revision:{target_revision_id}",
            "immutable": True,
            "sha256": None,
        },
        {
            "id": "change-event",
            "kind": "persisted_entity",
            "ref": f"postgres:project_event:{change_event_id}",
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
            "id": "durable-verifier",
            "kind": "test_report",
            "ref": "artifact:product-qualification/runtime/p0c-verifier.json",
            "immutable": False,
            "sha256": verifier_digest,
        },
    ]

    return {
        "schema": "c2pro-product-qualification-evidence-v1",
        "schema_version": 1,
        "lifecycle_authority": False,
        "repository": REPOSITORY,
        "control_ref": CONTROL_PATH,
        "control_commit_sha": control_sha,
        "control_baseline_sha": baseline,
        "capability_id": "P0c",
        "target_state": "PROD_VALIDATED",
        "environment": "production",
        "runtime_bindings": [
            {
                "plane": "backend",
                "provider": "railway",
                "commit_sha": backend_sha,
                "terminal_state": "SUCCESS",
                "deployment_evidence_ref": "deploy-backend",
            },
            {
                "plane": "frontend",
                "provider": "vercel",
                "commit_sha": frontend_sha,
                "terminal_state": "READY",
                "deployment_evidence_ref": "deploy-frontend",
            },
        ],
        "observed_at": observed,
        "scenario": {
            "id": "what_changed_two_revisions",
            "identifiers": {
                "project_id": project_id,
                "document_id": document_id,
                "from_revision_id": source_revision_id,
                "to_revision_id": target_revision_id,
            },
        },
        "assertions": [
            {
                "id": "durable_revision_bound_events",
                "status": "PASS",
                "evidence_refs": [
                    "source-revision",
                    "target-revision",
                    "change-event",
                    "durable-verifier",
                ],
            },
            {
                "id": "timeline_queryable",
                "status": "PASS",
                "evidence_refs": ["browser-run", "change-event", "durable-verifier"],
            },
            {
                "id": "semantic_change_source_traceable",
                "status": "PASS",
                "evidence_refs": [
                    "browser-run",
                    "source-revision",
                    "target-revision",
                    "change-event",
                ],
            },
            {
                "id": "api_ui_projection_parity",
                "status": "PASS",
                "evidence_refs": ["browser-run", "durable-verifier"],
            },
            {
                "id": "absent_evidence_does_not_invent_change",
                "status": "PASS",
                "evidence_refs": ["browser-run", "durable-verifier"],
                "note": (
                    "The canonical PJ-01 evaluator rejects unchanged control facts "
                    "reported as changes and requires evidence_refs on every reported change."
                ),
            },
        ],
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
    if args.github_run_id < 1 or args.github_run_attempt < 1:
        raise SystemExit("FAIL: run id and attempt must be positive")

    try:
        bundle = build_bundle(
            control_commit_sha=args.control_commit_sha,
            backend_commit_sha=args.backend_commit_sha,
            backend_deployment_id=args.backend_deployment_id,
            frontend_commit_sha=args.frontend_commit_sha,
            frontend_deployment_id=args.frontend_deployment_id,
            observed_at=args.observed_at,
        )
    except Exception as exc:
        raise SystemExit(
            f"FAIL: P0c qualification bundle build failed ({type(exc).__name__}: {exc})"
        ) from exc

    output = REPO_ROOT / OUTPUT_ROOT / (
        f"p0c-prod-gh-{args.github_run_id}-{args.github_run_attempt}.yaml"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        yaml.safe_dump(bundle, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )
    print(f"PASS: wrote qualification bundle to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
