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
RUN_JSON = Path("apps/web/playwright/.p0c-prod/run.json")
TIMELINE_JSON = Path("apps/web/playwright/.p0c-prod/timeline.json")
DETAIL_JSON = Path("apps/web/playwright/.p0c-prod/change-detail.json")
VERIFIER_JSON = Path("evidence/product-qualification/runtime/p0c-verifier.json")
OUTPUT_ROOT = Path("evidence/product-qualification")
FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class BundleBuildError(RuntimeError):
    """P0c evidence inputs are incomplete or contradictory."""


def _require_sha(value: str, label: str) -> str:
    normalized = value.strip().lower()
    if not FULL_SHA_RE.fullmatch(normalized):
        raise BundleBuildError(f"{label} must be a 40-character Git SHA")
    return normalized


def _path(relative: Path, label: str) -> Path:
    path = REPO_ROOT / relative
    if not path.is_file():
        raise BundleBuildError(f"{label} is missing")
    return path


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BundleBuildError(f"{path} must contain a JSON object")
    return value


def _string(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise BundleBuildError(f"missing {key}")
    return value.strip()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _control(control_commit_sha: str) -> dict[str, Any]:
    expected = _require_sha(control_commit_sha, "control commit")
    actual = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip().lower()
    if actual != expected:
        raise BundleBuildError("control commit must match checked-out HEAD")
    value = yaml.safe_load((REPO_ROOT / CONTROL_PATH).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BundleBuildError("Product Control must be a mapping")
    return value


def _assert_verifier(verifier: dict[str, Any]) -> None:
    if verifier.get("verdict") != "PASS":
        raise BundleBuildError("P0c durable verifier did not PASS")
    checks = verifier.get("checks")
    if not isinstance(checks, list) or not checks:
        raise BundleBuildError("P0c durable verifier checks are missing")
    failed = [
        row.get("name") if isinstance(row, dict) else "<invalid>"
        for row in checks
        if not isinstance(row, dict) or row.get("passed") is not True
    ]
    if failed:
        raise BundleBuildError(f"P0c durable verifier has failed checks: {failed}")


def _output(run_id: int, attempt: int) -> Path:
    if run_id < 1 or attempt < 1:
        raise BundleBuildError("GitHub run id/attempt must be positive")
    return REPO_ROOT / OUTPUT_ROOT / f"p0c-prod-gh-{run_id}-{attempt}.yaml"


def build_bundle(
    *,
    control_commit_sha: str,
    backend_commit_sha: str,
    backend_deployment_id: str,
    frontend_commit_sha: str,
    frontend_deployment_id: str,
    observed_at: str | None = None,
) -> dict[str, Any]:
    run_path = _path(RUN_JSON, "P0c browser run")
    timeline_path = _path(TIMELINE_JSON, "P0c timeline capture")
    detail_path = _path(DETAIL_JSON, "P0c change-detail capture")
    verifier_path = _path(VERIFIER_JSON, "P0c durable verifier")

    run = _json(run_path)
    timeline = _json(timeline_path)
    detail = _json(detail_path)
    verifier = _json(verifier_path)
    _assert_verifier(verifier)

    project_id = _string(run, "project_id")
    document_id = _string(run, "document_id")
    from_revision_id = _string(run, "from_revision_id")
    to_revision_id = _string(run, "to_revision_id")
    change_event_id = _string(run, "change_event_id")

    verifier_ids = verifier.get("identifiers")
    if not isinstance(verifier_ids, dict):
        raise BundleBuildError("P0c verifier identifiers are missing")
    for key, expected in {
        "project_id": project_id,
        "document_id": document_id,
        "from_revision_id": from_revision_id,
        "to_revision_id": to_revision_id,
        "change_event_id": change_event_id,
    }.items():
        if verifier_ids.get(key) != expected:
            raise BundleBuildError(f"browser/verifier identifier mismatch: {key}")

    if from_revision_id == to_revision_id:
        raise BundleBuildError("P0c source and target revisions must differ")
    if run.get("pj01_classification") != "USABLE":
        raise BundleBuildError("P0c canonical PJ-01 evaluator is not USABLE")
    if run.get("blocking_findings") != []:
        raise BundleBuildError("P0c browser run contains blocking findings")
    if run.get("documents_listed") != 1 or run.get("processing_outcome") != "analyzed":
        raise BundleBuildError("P0c browser journey did not preserve one analyzed logical document")

    negative = run.get("negative_control")
    if (
        not isinstance(negative, dict)
        or negative.get("mode") != "unchanged_declared_facts_not_reported_changed"
        or not isinstance(negative.get("fact_count"), int)
        or negative["fact_count"] < 1
    ):
        raise BundleBuildError("P0c unchanged-fact negative control is missing")

    timeline_items = timeline.get("items")
    if not isinstance(timeline_items, list):
        raise BundleBuildError("timeline capture has no items")
    matching_timeline = [
        item
        for item in timeline_items
        if isinstance(item, dict)
        and item.get("event_id") == change_event_id
        and item.get("event_type") == "revision.changed"
    ]
    if len(matching_timeline) != 1:
        raise BundleBuildError("timeline capture does not contain the exact revision.changed event")

    if detail.get("event_id") != change_event_id:
        raise BundleBuildError("change-detail capture event id disagrees with browser journey")
    provenance = detail.get("provenance")
    if not isinstance(provenance, dict):
        raise BundleBuildError("change-detail provenance is missing")
    if provenance.get("source_revision_id") != from_revision_id:
        raise BundleBuildError("change-detail source revision disagrees")
    if provenance.get("target_revision_id") != to_revision_id:
        raise BundleBuildError("change-detail target revision disagrees")
    changes = detail.get("changes")
    if not isinstance(changes, list) or not changes:
        raise BundleBuildError("change-detail capture contains no material changes")
    if any(
        not isinstance(change, dict)
        or not isinstance(change.get("evidence_refs"), list)
        or not change["evidence_refs"]
        for change in changes
    ):
        raise BundleBuildError("every P0c material change must contain evidence refs")

    control = _control(control_commit_sha)
    production = control.get("production_position")
    if not isinstance(production, dict):
        raise BundleBuildError("Product Control production_position is missing")
    control_baseline_sha = _string(production, "reconciled_against_main_sha")

    observed = observed_at or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    browser_sha = _sha256(run_path)
    timeline_sha = _sha256(timeline_path)
    detail_sha = _sha256(detail_path)
    verifier_sha = _sha256(verifier_path)

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
            "id": "browser-run",
            "kind": "ui_report",
            "ref": "artifact:playwright/.p0c-prod/run.json",
            "immutable": False,
            "sha256": browser_sha,
        },
        {
            "id": "timeline-api",
            "kind": "api_capture",
            "ref": "artifact:playwright/.p0c-prod/timeline.json",
            "immutable": False,
            "sha256": timeline_sha,
        },
        {
            "id": "change-detail-api",
            "kind": "api_capture",
            "ref": "artifact:playwright/.p0c-prod/change-detail.json",
            "immutable": False,
            "sha256": detail_sha,
        },
        {
            "id": "db-verifier",
            "kind": "test_report",
            "ref": "artifact:product-qualification/runtime/p0c-verifier.json",
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
        "control_commit_sha": _require_sha(control_commit_sha, "control commit"),
        "control_baseline_sha": control_baseline_sha,
        "capability_id": "P0c",
        "target_state": "PROD_VALIDATED",
        "environment": "production",
        "runtime_bindings": [
            {
                "plane": "backend",
                "provider": "railway",
                "commit_sha": _require_sha(backend_commit_sha, "backend commit"),
                "terminal_state": "SUCCESS",
                "deployment_evidence_ref": "deploy-backend",
            },
            {
                "plane": "frontend",
                "provider": "vercel",
                "commit_sha": _require_sha(frontend_commit_sha, "frontend commit"),
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
                "evidence_refs": ["browser-run", "timeline-api", "change-event"],
            },
            {
                "id": "semantic_change_source_traceable",
                "status": "PASS",
                "evidence_refs": ["change-detail-api", "source-revision", "target-revision", "db-verifier"],
            },
            {
                "id": "api_ui_projection_parity",
                "status": "PASS",
                "evidence_refs": ["browser-run", "timeline-api", "change-detail-api"],
            },
            {
                "id": "absent_evidence_does_not_invent_change",
                "status": "PASS",
                "evidence_refs": ["browser-run", "change-detail-api"],
                "note": (
                    "Bounded negative control: the canonical PJ-01 evaluator requires every "
                    "fixture-declared unchanged control fact to be absent from reported changes."
                ),
            },
        ],
        "evidence_refs": evidence_refs,
        "validator_verdict": "PASS",
    }


def _positive_int(raw: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
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
            control_commit_sha=args.control_commit_sha,
            backend_commit_sha=args.backend_commit_sha,
            backend_deployment_id=args.backend_deployment_id,
            frontend_commit_sha=args.frontend_commit_sha,
            frontend_deployment_id=args.frontend_deployment_id,
            observed_at=args.observed_at,
        )
        output = _output(args.github_run_id, args.github_run_attempt)
    except Exception as exc:
        raise SystemExit(
            f"FAIL: P0c qualification bundle build failed ({type(exc).__name__}: {exc})"
        ) from exc

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        yaml.safe_dump(bundle, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )
    print(f"PASS: wrote P0c qualification bundle to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
