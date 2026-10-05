#!/usr/bin/env python3
"""Validate non-authoritative #867 B1-12 production evidence bundles."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_ASSERTIONS = {
    "canonical_alerts_from_same_finding_set",
    "fresh_session_identity_and_provenance",
    "approve_does_not_improve_canonical_score",
    "exact_basis_false_positive",
    "same_version_snapshot_rescore",
    "alert_and_score_durable_after_relogin",
    "unknown_remains_null",
    "new_observation_reopens_stale_disposition",
    "single_family_single_review_single_rescore_authority",
}


class ValidationError(RuntimeError):
    pass


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(path: Path) -> None:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValidationError("bundle must be a mapping")
    if payload.get("schema") != "c2pro-b1-12-production-evidence-v1":
        raise ValidationError("unexpected schema")
    if payload.get("schema_version") != 1:
        raise ValidationError("unexpected schema version")
    if payload.get("lifecycle_authority") is not False:
        raise ValidationError("B1-12 bundle must not self-promote lifecycle")
    if payload.get("gate_id") != "B1-12-PROD-ACCEPTANCE" or payload.get("issue") != 867:
        raise ValidationError("wrong B1 gate/issue")
    if payload.get("environment") != "production":
        raise ValidationError("B1-12 evidence must bind production")

    runtimes = payload.get("runtime_bindings")
    if not isinstance(runtimes, dict):
        raise ValidationError("runtime bindings missing")
    backend = runtimes.get("backend")
    frontend = runtimes.get("frontend")
    if not isinstance(backend, dict) or backend.get("terminal_state") != "SUCCESS":
        raise ValidationError("Railway backend is not terminal SUCCESS")
    if not isinstance(frontend, dict) or frontend.get("terminal_state") != "READY":
        raise ValidationError("Vercel frontend is not terminal READY")
    if backend.get("commit_sha") != frontend.get("commit_sha"):
        raise ValidationError("this bounded B1 run requires the observed SHA-aligned runtime")

    scenario = payload.get("scenario")
    if not isinstance(scenario, dict):
        raise ValidationError("scenario missing")
    if scenario.get("false_positive_alert_id") != scenario.get(
        "post_revision_false_positive_alert_id"
    ):
        raise ValidationError("finding family did not preserve the canonical alert identity")
    reviewed = scenario.get("reviewed_observation_key")
    current = scenario.get("current_observation_key")
    if not isinstance(reviewed, str) or not reviewed:
        raise ValidationError("reviewed observation basis missing")
    if not isinstance(current, str) or not current or current == reviewed:
        raise ValidationError("new authoritative observation did not change basis")

    score = payload.get("score_evidence")
    if not isinstance(score, dict):
        raise ValidationError("score evidence missing")
    if not score.get("source_result_id") or not score.get("rescore_result_id"):
        raise ValidationError("governed rescore linkage missing")
    if score.get("source_result_id") == score.get("rescore_result_id"):
        raise ValidationError("rescore did not create a distinct canonical result")
    if score.get("score_version") not in {"coherence-v1", "coherence-v2"}:
        raise ValidationError("unsupported/absent score version")

    assertions = payload.get("assertions")
    if not isinstance(assertions, list):
        raise ValidationError("assertions missing")
    passed = {
        item.get("id")
        for item in assertions
        if isinstance(item, dict) and item.get("status") == "PASS"
    }
    missing = REQUIRED_ASSERTIONS - passed
    if missing:
        raise ValidationError(f"missing PASS assertions: {sorted(missing)}")

    refs = payload.get("evidence_refs")
    if not isinstance(refs, list):
        raise ValidationError("evidence refs missing")
    by_id = {item.get("id"): item for item in refs if isinstance(item, dict)}
    for ref_id, rel in (
        ("browser-run", "apps/web/playwright/.prod-b1/run.json"),
        ("db-verifier", "evidence/product-qualification/runtime/b1-12-verifier.json"),
    ):
        ref = by_id.get(ref_id)
        if not isinstance(ref, dict):
            raise ValidationError(f"missing {ref_id}")
        target = REPO_ROOT / rel
        if not target.is_file():
            raise ValidationError(f"missing local evidence payload: {rel}")
        if ref.get("sha256") != _digest(target):
            raise ValidationError(f"digest mismatch: {ref_id}")

    if payload.get("validator_verdict") != "PASS":
        raise ValidationError("bundle does not carry PASS validator verdict")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle")
    args = parser.parse_args()
    try:
        validate(REPO_ROOT / args.bundle)
    except Exception as exc:
        raise SystemExit(f"FAIL: {type(exc).__name__}: {exc}") from exc
    print("PASS: B1-12 production evidence is internally consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
