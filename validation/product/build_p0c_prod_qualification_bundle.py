#!/usr/bin/env python3
"""Build a non-authoritative P0c production qualification evidence bundle."""

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
RUN_JSON = Path("apps/web/playwright/.prod-acceptance/p0c-run.json")
VERIFIER_JSON = Path("evidence/product-qualification/runtime/p0c-verifier.json")
OUTPUT_ROOT = Path("evidence/product-qualification")
FULL_SHA_RE = re.compile(r"[0-9a-fA-F]{40}")


class BundleBuildError(RuntimeError):
    """Qualification inputs are incomplete or contradictory."""


def _load_json(path: Path) -> dict[str, Any]:
    full = REPO_ROOT / path
    if not full.is_file():
        raise BundleBuildError(f"missing evidence artifact: {path}")
    value = json.loads(full.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BundleBuildError(f"{path} must contain an object")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256((REPO_ROOT / path).read_bytes()).hexdigest()


def _full_sha(value: str, label: str) -> str:
    normalized = value.strip().lower()
    if not FULL_SHA_RE.fullmatch(normalized):
        raise BundleBuildError(f"{label} must be a 40-character Git SHA")
    return normalized


def _control_at(commit_sha: str) -> dict[str, Any]:
    expected = _full_sha(commit_sha, "control commit")
    actual = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip().lower()
    if actual != expected:
        raise BundleBuildError("control commit must match checked-out commit")
    value = yaml.safe_load((REPO_ROOT / CONTROL_PATH).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BundleBuildError("Product Control must be a mapping")
    return value


def _required(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise BundleBuildError(f"missing {key}")
    return value.strip()


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
    if verifier.get("verdict") != "PASS":
        raise BundleBuildError("P0c post-run verifier did not PASS")
    if run.get("relogin_verified") is not True:
        raise BundleBuildError("browser did not prove relogin durability")
    if run.get("documents_listed_after_revision") != 1:
        raise BundleBuildError("revision journey did not preserve one logical document")
    if run.get("source_processing_outcome") != "analyzed":
        raise BundleBuildError("Contract A did not settle as analyzed")
    if run.get("target_processing_outcome") != "analyzed":
        raise BundleBuildError("Contract B did not settle as analyzed")
    if run.get("negative_source_processing_outcome") != "analyzed":
        raise BundleBuildError("negative baseline did not settle as analyzed")
    if run.get("negative_target_processing_outcome") != "analyzed":
        raise BundleBuildError("negative identical revision did not settle as analyzed")

    verifier_ids = verifier.get("identifiers")
    if not isinstance(verifier_ids, dict):
        raise BundleBuildError("verifier identifiers missing")

    project_id = _required(run, "project_id")
    document_id = _required(run, "document_id")
    source_revision_id = _required(run, "source_revision_id")
    target_revision_id = _required(run, "target_revision_id")
    change_event_id = _required(run, "change_event_id")
    negative_project_id = _required(run, "negative_project_id")
    negative_document_id = _required(run, "negative_document_id")
    negative_source_revision_id = _required(run, "negative_source_revision_id")
    negative_target_revision_id = _required(run, "negative_target_revision_id")
    negative_change_event_id = _required(run, "negative_change_event_id")
    if source_revision_id == target_revision_id:
        raise BundleBuildError("source and target revisions must differ")
    if negative_source_revision_id == negative_target_revision_id:
        raise BundleBuildError("negative source and target revisions must differ")
    if negative_project_id == project_id:
        raise BundleBuildError("negative proof must use an isolated project")

    expected = {
        "project_id": project_id,
        "document_id": document_id,
        "source_revision_id": source_revision_id,
        "target_revision_id": target_revision_id,
        "change_event_id": change_event_id,
        "negative_project_id": negative_project_id,
        "negative_document_id": negative_document_id,
        "negative_source_revision_id": negative_source_revision_id,
        "negative_target_revision_id": negative_target_revision_id,
        "negative_change_event_id": negative_change_event_id,
    }
    for key, value in expected.items():
        if verifier_ids.get(key) != value:
            raise BundleBuildError(f"browser/verifier disagreement for {key}")

    control = _control_at(control_commit_sha)
    position = control.get("production_position")
    if not isinstance(position, dict):
        raise BundleBuildError("Product Control production_position missing")
    control_baseline_sha = _required(position, "reconciled_against_main_sha")

    run_sha = _sha256(RUN_JSON)
    verifier_sha = _sha256(VERIFIER_JSON)
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
            "id": "negative-source-revision",
            "kind": "persisted_entity",
            "ref": f"postgres:document_revision:{negative_source_revision_id}",
            "immutable": True,
            "sha256": None,
        },
        {
            "id": "negative-target-revision",
            "kind": "persisted_entity",
            "ref": f"postgres:document_revision:{negative_target_revision_id}",
            "immutable": True,
            "sha256": None,
        },
        {
            "id": "negative-change-event",
            "kind": "persisted_entity",
            "ref": f"postgres:project_event:{negative_change_event_id}",
            "immutable": True,
            "sha256": None,
        },
        {
            "id": "browser-run",
            "kind": "ui_report",
            "ref": f"artifact:{RUN_JSON.as_posix()}",
            "immutable": False,
            "sha256": run_sha,
        },
        {
            "id": "db-verifier",
            "kind": "test_report",
            "ref": f"artifact:{VERIFIER_JSON.as_posix()}",
            "immutable": False,
            "sha256": verifier_sha,
        },
    ]

    assertions = [
        {
            "id": "durable_revision_bound_events",
            "status": "PASS",
            "evidence_refs": ["source-revision", "target-revision", "change-event", "db-verifier"],
        },
        {
            "id": "timeline_queryable",
            "status": "PASS",
            "evidence_refs": ["browser-run", "change-event", "db-verifier"],
        },
        {
            "id": "semantic_change_source_traceable",
            "status": "PASS",
            "evidence_refs": ["browser-run", "source-revision", "target-revision", "change-event", "db-verifier"],
        },
        {
            "id": "api_ui_projection_parity",
            "status": "PASS",
            "evidence_refs": ["browser-run", "db-verifier"],
        },
        {
            "id": "absent_evidence_does_not_invent_change",
            "status": "PASS",
            "evidence_refs": [
                "browser-run",
                "negative-source-revision",
                "negative-target-revision",
                "negative-change-event",
                "db-verifier",
            ],
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
                "project_id": project_id,
                "document_id": document_id,
                "from_revision_id": source_revision_id,
                "to_revision_id": target_revision_id,
            },
        },
        "assertions": assertions,
        "evidence_refs": evidence_refs,
        "validator_verdict": "PASS",
    }


def _positive_int(raw: str) -> int:
    value = int(raw)
    if value < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control-commit-sha", required=True)
    parser.add_argument("--backend-commit-sha", required=True)
    parser.add_argument("--backend-deployment-id", required=True)
    parser.add_argument("--frontend-commit-sha", required=True)
    parser.add_argument("--frontend-deployment-id", required=True)
    parser.add_argument("--github-run-id", required=True, type=_positive_int)
    parser.add_argument("--github-run-attempt", required=True, type=_positive_int)
    parser.add_argument("--observed-at")
    args = parser.parse_args()

    try:
        bundle = build_bundle(
            control_commit_sha=_full_sha(args.control_commit_sha, "control commit"),
            backend_commit_sha=_full_sha(args.backend_commit_sha, "backend commit"),
            backend_deployment_id=args.backend_deployment_id,
            frontend_commit_sha=_full_sha(args.frontend_commit_sha, "frontend commit"),
            frontend_deployment_id=args.frontend_deployment_id,
            github_run_id=args.github_run_id,
            github_run_attempt=args.github_run_attempt,
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
    print(f"PASS: wrote P0c qualification bundle to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
