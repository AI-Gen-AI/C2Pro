#!/usr/bin/env python3
"""Build a non-authoritative P0c qualification evidence bundle from bounded run outputs."""

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
QUALIFICATION_OUTPUT_ROOT = Path("evidence/product-qualification")
FULL_SHA_RE = re.compile(r"[0-9a-fA-F]{40}")
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
RUN_ROOT = REPO_ROOT / "apps/web/playwright/.prod-p0c"
VERIFIER_PATH = REPO_ROOT / "evidence/product-qualification/runtime/p0c-verifier.json"


class BundleBuildError(RuntimeError):
    pass


def _require_full_sha(value: str, label: str) -> str:
    normalized = value.strip().lower()
    if not FULL_SHA_RE.fullmatch(normalized):
        raise BundleBuildError(f"{label} must be a 40-character Git SHA")
    return normalized


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BundleBuildError(f"{path} must contain a JSON object")
    return value


def _canonical_run_path(run_id: str) -> Path:
    if not RUN_ID_RE.fullmatch(run_id) or ".." in run_id:
        raise BundleBuildError("run id is invalid")
    root = RUN_ROOT.resolve()
    candidate = root / run_id / "run.json"
    if candidate.is_symlink():
        raise BundleBuildError("run evidence path must not be a symlink")
    path = candidate.resolve(strict=True)
    if path.parent != (root / run_id).resolve() or not path.is_file():
        raise BundleBuildError("run evidence path is not canonical")
    return path


def _canonical_verifier_path() -> Path:
    if VERIFIER_PATH.is_symlink():
        raise BundleBuildError("verifier evidence path must not be a symlink")
    path = VERIFIER_PATH.resolve(strict=True)
    expected_parent = (REPO_ROOT / "evidence/product-qualification/runtime").resolve()
    if path.parent != expected_parent or path.name != "p0c-verifier.json" or not path.is_file():
        raise BundleBuildError("verifier evidence path is not canonical")
    return path


def _control_at(commit_sha: str) -> dict[str, Any]:
    expected = _require_full_sha(commit_sha, "control commit")
    checked = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip().lower()
    if checked != expected:
        raise BundleBuildError("control commit must match checked-out commit")
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
    run_json: Path,
    verifier_json: Path,
    observed_at: str | None = None,
) -> dict[str, Any]:
    run = _load_json(run_json)
    verifier = _load_json(verifier_json)

    if run.get("classification") != "USABLE":
        raise BundleBuildError("PJ-01 production run is not USABLE")
    facts = run.get("facts")
    if not isinstance(facts, dict) or facts.get("p0cReloginVerified") is not True:
        raise BundleBuildError("browser relogin durability is missing")
    prod = facts.get("p0cProduction")
    no_change = facts.get("p0cNoChange")
    if not isinstance(prod, dict) or not isinstance(no_change, dict):
        raise BundleBuildError("P0c browser evidence is incomplete")
    if no_change.get("changeCause") is not None:
        raise BundleBuildError("negative no-change browser proof is not honest")

    if verifier.get("verdict") != "PASS":
        raise BundleBuildError("read-only P0c verifier did not PASS")
    checks = verifier.get("checks")
    if not isinstance(checks, list) or not checks or any(
        not isinstance(item, dict) or item.get("passed") is not True for item in checks
    ):
        raise BundleBuildError("P0c verifier contains failed checks")
    identifiers = verifier.get("identifiers")
    if not isinstance(identifiers, dict):
        raise BundleBuildError("P0c verifier identifiers are missing")

    project_id = str(identifiers.get("project_id") or "")
    document_id = str(identifiers.get("document_id") or "")
    from_revision_id = str(identifiers.get("source_revision_id") or "")
    to_revision_id = str(identifiers.get("target_revision_id") or "")
    change_event_id = str(identifiers.get("change_event_id") or "")
    no_change_event_id = str(identifiers.get("no_change_event_id") or "")
    no_change_target_revision_id = str(
        identifiers.get("no_change_target_revision_id") or ""
    )
    if not all(
        (
            project_id,
            document_id,
            from_revision_id,
            to_revision_id,
            change_event_id,
            no_change_event_id,
            no_change_target_revision_id,
        )
    ):
        raise BundleBuildError("P0c verifier identifiers are incomplete")
    if from_revision_id == to_revision_id:
        raise BundleBuildError("P0c source and target revisions must differ")

    if (
        str(prod.get("projectId")) != project_id
        or str(prod.get("documentId")) != document_id
        or str(prod.get("sourceRevisionId")) != from_revision_id
        or str(prod.get("targetRevisionId")) != to_revision_id
        or str(prod.get("changeEventId")) != change_event_id
    ):
        raise BundleBuildError("browser and DB verifier identifiers disagree")

    if (
        str(no_change.get("eventId")) != no_change_event_id
        or str(no_change.get("targetRevisionId")) != no_change_target_revision_id
        or no_change.get("fixtureClass") != "byte-distinct-parser-equivalent"
    ):
        raise BundleBuildError(
            "browser and DB verifier no-change identifiers disagree"
        )

    control = _control_at(control_commit_sha)
    production = control.get("production_position")
    if not isinstance(production, dict):
        raise BundleBuildError("Product Control production_position is missing")
    baseline = str(production.get("reconciled_against_main_sha") or "")
    _require_full_sha(baseline, "control baseline")

    run_sha = _sha256(run_json)
    verifier_sha = _sha256(verifier_json)
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
            "ref": f"postgres:document_revision:{from_revision_id}",
            "immutable": True,
            "sha256": None,
        },
        {
            "id": "target-revision",
            "kind": "persisted_entity",
            "ref": f"postgres:document_revision:{to_revision_id}",
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
            "id": "no-change-event",
            "kind": "persisted_entity",
            "ref": f"postgres:project_event:{no_change_event_id}",
            "immutable": True,
            "sha256": None,
        },
        {
            "id": "no-change-target-revision",
            "kind": "persisted_entity",
            "ref": f"postgres:document_revision:{no_change_target_revision_id}",
            "immutable": True,
            "sha256": None,
        },
        {
            "id": "browser-run",
            "kind": "ui_report",
            "ref": f"artifact:apps/web/playwright/.prod-p0c/{run_json.parent.name}/run.json",
            "immutable": False,
            "sha256": run_sha,
        },
        {
            "id": "db-verifier",
            "kind": "test_report",
            "ref": "artifact:evidence/product-qualification/runtime/p0c-verifier.json",
            "immutable": False,
            "sha256": verifier_sha,
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
                "project_id": project_id,
                "document_id": document_id,
                "from_revision_id": from_revision_id,
                "to_revision_id": to_revision_id,
            },
        },
        "assertions": [
            {
                "id": "durable_revision_bound_events",
                "status": "PASS",
                "evidence_refs": ["source-revision", "target-revision", "change-event", "db-verifier"],
            },
            {
                "id": "timeline_queryable",
                "status": "PASS",
                "evidence_refs": ["browser-run", "change-event"],
            },
            {
                "id": "semantic_change_source_traceable",
                "status": "PASS",
                "evidence_refs": ["browser-run", "db-verifier", "source-revision", "target-revision"],
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
                    "db-verifier",
                    "no-change-event",
                    "no-change-target-revision",
                ],
                "note": "Approved byte-distinct parser-equivalent Contract B derivative persisted as an empty changeset with change_cause=null.",
            },
        ],
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
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--github-run-id", required=True, type=_positive_int)
    parser.add_argument("--github-run-attempt", required=True, type=_positive_int)
    parser.add_argument("--observed-at")
    args = parser.parse_args()

    try:
        run_json = _canonical_run_path(args.run_id)
        verifier_json = _canonical_verifier_path()
        bundle = build_bundle(
            control_commit_sha=_require_full_sha(args.control_commit_sha, "control commit"),
            backend_commit_sha=_require_full_sha(args.backend_commit_sha, "backend commit"),
            backend_deployment_id=args.backend_deployment_id,
            frontend_commit_sha=_require_full_sha(args.frontend_commit_sha, "frontend commit"),
            frontend_deployment_id=args.frontend_deployment_id,
            run_json=run_json,
            verifier_json=verifier_json,
            observed_at=args.observed_at,
        )
        output = REPO_ROOT / QUALIFICATION_OUTPUT_ROOT / (
            f"p0c-prod-gh-{args.github_run_id}-{args.github_run_attempt}.yaml"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            yaml.safe_dump(bundle, sort_keys=False, allow_unicode=False),
            encoding="utf-8",
        )
    except Exception as exc:
        raise SystemExit(
            f"FAIL: P0c qualification bundle build failed ({type(exc).__name__}: {exc})"
        ) from exc

    print(f"PASS: wrote P0c qualification bundle to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
