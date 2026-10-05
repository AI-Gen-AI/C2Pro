#!/usr/bin/env python3
"""Build non-authoritative machine-readable evidence for #867 B1-12."""

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

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTROL_PATH = "validation/product/c2pro-master-product-control-v1.yaml"
RUN_PATH = Path("apps/web/playwright/.prod-b1/run.json")
VERIFIER_PATH = Path("evidence/product-qualification/runtime/b1-12-verifier.json")
OUTPUT_ROOT = Path("evidence/product-qualification")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class BuildError(RuntimeError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    target = REPO_ROOT / path
    if not target.is_file():
        raise BuildError(f"missing evidence file: {path}")
    value = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BuildError(f"{path} must contain a JSON object")
    return value


def _digest(path: Path) -> str:
    return hashlib.sha256((REPO_ROOT / path).read_bytes()).hexdigest()


def _sha(value: str, label: str) -> str:
    normalized = value.strip().lower()
    if not SHA_RE.fullmatch(normalized):
        raise BuildError(f"{label} must be a 40-character Git SHA")
    return normalized


def _control_baseline(control_sha: str) -> str:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if head != control_sha:
        raise BuildError("control commit must equal checked-out HEAD")
    value = yaml.safe_load((REPO_ROOT / CONTROL_PATH).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BuildError("Product Control must be a mapping")
    production = value.get("production_position")
    if not isinstance(production, dict):
        raise BuildError("Product Control production_position missing")
    baseline = production.get("reconciled_against_main_sha")
    if not isinstance(baseline, str) or not SHA_RE.fullmatch(baseline):
        raise BuildError("Product Control production baseline invalid")
    return baseline


def build(
    *,
    control_commit_sha: str,
    backend_commit_sha: str,
    backend_deployment_id: str,
    frontend_commit_sha: str,
    frontend_deployment_id: str,
    github_run_id: int,
    github_run_attempt: int,
) -> dict[str, Any]:
    run = _load_json(RUN_PATH)
    verifier = _load_json(VERIFIER_PATH)
    if run.get("schema") != "c2pro-b1-12-production-run/v1":
        raise BuildError("unexpected B1 browser evidence schema")
    if run.get("relogin_verified") is not True:
        raise BuildError("browser did not prove relogin durability")
    if run.get("second_authoritative_observation_evaluated") is not True:
        raise BuildError("browser did not prove a second authoritative observation")
    if verifier.get("verdict") != "PASS":
        raise BuildError("B1-12 verifier did not PASS")
    checks = verifier.get("checks")
    if not isinstance(checks, list) or not checks or any(
        not isinstance(item, dict) or item.get("passed") is not True for item in checks
    ):
        raise BuildError("B1-12 verifier contains failed/malformed checks")

    verifier_evidence = verifier.get("evidence")
    if not isinstance(verifier_evidence, dict):
        raise BuildError("B1-12 verifier evidence missing")
    if run.get("project_id") != verifier_evidence.get("project_id"):
        raise BuildError("browser/verifier project mismatch")
    if run.get("false_positive_alert_id") != verifier_evidence.get("false_positive_alert_id"):
        raise BuildError("browser/verifier false-positive alert mismatch")
    if run.get("genuine_alert_id") != verifier_evidence.get("genuine_alert_id"):
        raise BuildError("browser/verifier genuine alert mismatch")
    if run.get("post_revision_false_positive_alert_id") != verifier_evidence.get(
        "post_revision_false_positive_alert_id"
    ):
        raise BuildError("browser/verifier post-revision false-positive alert mismatch")

    baseline = _control_baseline(control_commit_sha)
    observed_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    assertions = [
        "canonical_alerts_from_same_finding_set",
        "fresh_session_identity_and_provenance",
        "approve_does_not_improve_canonical_score",
        "exact_basis_false_positive",
        "same_version_snapshot_rescore",
        "alert_and_score_durable_after_relogin",
        "unknown_remains_null",
        "new_observation_reopens_stale_disposition",
        "single_family_single_review_single_rescore_authority",
    ]

    return {
        "schema": "c2pro-b1-12-production-evidence-v1",
        "schema_version": 1,
        "lifecycle_authority": False,
        "repository": "AI-Gen-AI/C2Pro",
        "control_ref": CONTROL_PATH,
        "control_commit_sha": control_commit_sha,
        "control_baseline_sha": baseline,
        "gate_id": "B1-12-PROD-ACCEPTANCE",
        "issue": 867,
        "environment": "production",
        "observed_at": observed_at,
        "runtime_bindings": {
            "backend": {
                "provider": "railway",
                "commit_sha": backend_commit_sha,
                "deployment_id": backend_deployment_id,
                "terminal_state": "SUCCESS",
            },
            "frontend": {
                "provider": "vercel",
                "commit_sha": frontend_commit_sha,
                "deployment_id": frontend_deployment_id,
                "terminal_state": "READY",
            },
        },
        "scenario": {
            "project_id": run["project_id"],
            "contract_document_id": run["contract_document_id"],
            "genuine_rule": run["genuine_rule"],
            "genuine_alert_id": run["genuine_alert_id"],
            "false_positive_rule": run["false_positive_rule"],
            "false_positive_alert_id": run["false_positive_alert_id"],
            "post_revision_false_positive_alert_id": run[
                "post_revision_false_positive_alert_id"
            ],
            "finding_key": verifier_evidence.get("finding_key"),
            "reviewed_observation_key": verifier_evidence.get("reviewed_observation_key"),
            "current_observation_key": verifier_evidence.get("current_observation_key"),
        },
        "score_evidence": {
            "source_result_id": verifier_evidence.get("source_result_id"),
            "rescore_result_id": verifier_evidence.get("rescore_result_id"),
            "latest_result_id": verifier_evidence.get("latest_result_id"),
            "source_score": verifier_evidence.get("source_score"),
            "rescored_score": verifier_evidence.get("rescored_score"),
            "latest_score": verifier_evidence.get("latest_score"),
            "score_version": verifier_evidence.get("latest_score_version"),
            "missing_dimensions": verifier_evidence.get("latest_missing_dimensions"),
        },
        "assertions": [{"id": item, "status": "PASS"} for item in assertions],
        "evidence_refs": [
            {
                "id": "browser-run",
                "kind": "ui_report",
                "ref": "artifact:playwright/.prod-b1/run.json",
                "sha256": _digest(RUN_PATH),
            },
            {
                "id": "db-verifier",
                "kind": "test_report",
                "ref": "artifact:product-qualification/runtime/b1-12-verifier.json",
                "sha256": _digest(VERIFIER_PATH),
            },
            {
                "id": "github-run",
                "kind": "workflow_run",
                "ref": f"github:{github_run_id}:{github_run_attempt}",
                "sha256": None,
            },
        ],
        "validator_verdict": "PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control-commit-sha", required=True)
    parser.add_argument("--backend-commit-sha", required=True)
    parser.add_argument("--backend-deployment-id", required=True)
    parser.add_argument("--frontend-commit-sha", required=True)
    parser.add_argument("--frontend-deployment-id", required=True)
    parser.add_argument("--github-run-id", type=int, required=True)
    parser.add_argument("--github-run-attempt", type=int, required=True)
    args = parser.parse_args()

    bundle = build(
        control_commit_sha=_sha(args.control_commit_sha, "control commit"),
        backend_commit_sha=_sha(args.backend_commit_sha, "backend commit"),
        backend_deployment_id=args.backend_deployment_id,
        frontend_commit_sha=_sha(args.frontend_commit_sha, "frontend commit"),
        frontend_deployment_id=args.frontend_deployment_id,
        github_run_id=args.github_run_id,
        github_run_attempt=args.github_run_attempt,
    )
    output = REPO_ROOT / OUTPUT_ROOT / f"b1-12-prod-gh-{args.github_run_id}-{args.github_run_attempt}.yaml"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml.safe_dump(bundle, sort_keys=False), encoding="utf-8")
    print(f"PASS: wrote B1-12 evidence bundle to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
