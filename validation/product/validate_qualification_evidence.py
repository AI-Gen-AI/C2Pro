#!/usr/bin/env python3
"""Validate non-authoritative production-qualification evidence bundles.

The evidence bundle proves a capability-specific production scenario. It never
owns lifecycle state: Product Control remains the sole authority that may
promote a capability to PROD_VALIDATED after this evidence passes review.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import yaml

SCHEMA_ID = "c2pro-product-qualification-evidence-v1"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ALLOWED_KINDS = {
    "release_bundle",
    "deployment",
    "persisted_entity",
    "api_capture",
    "ui_report",
    "runtime_log",
    "test_report",
    "other",
}
FORBIDDEN_AUTHORITY_KEYS = {
    "prod_validation_status",
    "lifecycle_status",
    "realization_status",
    "deployment_status",
    "work_status",
}

REQUIRED_ASSERTIONS: dict[str, tuple[str, ...]] = {
    "P0b": (
        "six_categories_present_or_honest_unknown",
        "findings_traceable_to_evidence",
        "missing_data_preserved",
        "actionable_gap_alerts_visible",
        "health_api_ui_semantic_parity",
        "unknown_never_zero_or_green",
        "coherence_headline_null_under_two_reconcilable_documents",
        "hitl_retry_recovery_does_not_strand_document",
    ),
    "P0c": (
        "durable_revision_bound_events",
        "timeline_queryable",
        "semantic_change_source_traceable",
        "api_ui_projection_parity",
        "absent_evidence_does_not_invent_change",
    ),
    "P0d": (
        "authoritative_domain_sources_only",
        "six_category_health_semantics_match_p0b",
        "honest_null_survives_api_ui_export",
        "same_state_is_reproducible",
    ),
}

SCENARIO_CONTRACT: dict[str, tuple[str, tuple[str, ...]]] = {
    "P0b": (
        "single_document_health",
        ("project_id", "document_id", "source_revision_id"),
    ),
    "P0c": (
        "what_changed_two_revisions",
        ("project_id", "document_id", "from_revision_id", "to_revision_id"),
    ),
    "P0d": (
        "current_state_report",
        ("project_id", "state_ref"),
    ),
}


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("qualification evidence must be a mapping")
    return value


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_document(doc: dict[str, Any]) -> list[str]:
    problems: list[str] = []

    if doc.get("schema") != SCHEMA_ID:
        problems.append(f"schema must be {SCHEMA_ID}")
    if doc.get("schema_version") != 1:
        problems.append("schema_version must be 1")
    if doc.get("lifecycle_authority") is not False:
        problems.append("lifecycle_authority must be false")
    if doc.get("repository") != "AI-Gen-AI/C2Pro":
        problems.append("repository must be AI-Gen-AI/C2Pro")
    if doc.get("target_state") != "PROD_VALIDATED":
        problems.append("target_state must be PROD_VALIDATED")
    if doc.get("environment") != "production":
        problems.append("environment must be production")

    forbidden = FORBIDDEN_AUTHORITY_KEYS.intersection(doc)
    if forbidden:
        problems.append(
            "evidence bundle may not own lifecycle fields: "
            + ", ".join(sorted(forbidden))
        )

    capability = doc.get("capability_id")
    if capability not in REQUIRED_ASSERTIONS:
        problems.append(f"unknown capability_id: {capability!r}")

    runtime_sha = doc.get("deployed_runtime_sha")
    if not isinstance(runtime_sha, str) or not SHA_RE.fullmatch(runtime_sha):
        problems.append(
            "deployed_runtime_sha must be an exact observed 40-character SHA"
        )

    if not _non_empty_string(doc.get("observed_at")):
        problems.append("observed_at is required")

    if capability in SCENARIO_CONTRACT:
        problems.extend(_validate_scenario(capability, doc.get("scenario")))

    evidence = doc.get("evidence_refs")
    evidence_ids: set[str] = set()
    if not isinstance(evidence, list) or not evidence:
        problems.append("evidence_refs must be a non-empty list")
    else:
        for index, ref in enumerate(evidence):
            where = f"evidence_refs[{index}]"
            if not isinstance(ref, dict):
                problems.append(f"{where} must be a mapping")
                continue
            ref_id = ref.get("id")
            if not _non_empty_string(ref_id):
                problems.append(f"{where}.id is required")
            elif ref_id in evidence_ids:
                problems.append(f"duplicate evidence id: {ref_id}")
            else:
                evidence_ids.add(ref_id)
            if ref.get("kind") not in ALLOWED_KINDS:
                problems.append(f"{where}.kind is invalid")
            if not _non_empty_string(ref.get("ref")):
                problems.append(f"{where}.ref is required")
            if not isinstance(ref.get("immutable"), bool):
                problems.append(f"{where}.immutable must be boolean")
            sha256 = ref.get("sha256")
            if sha256 is not None and (
                not isinstance(sha256, str) or not SHA256_RE.fullmatch(sha256)
            ):
                problems.append(f"{where}.sha256 must be 64 lowercase hex chars")

    assertion_rows = doc.get("assertions")
    assertion_statuses: dict[str, str] = {}
    if not isinstance(assertion_rows, list) or not assertion_rows:
        problems.append("assertions must be a non-empty list")
    elif capability in REQUIRED_ASSERTIONS:
        expected = set(REQUIRED_ASSERTIONS[capability])
        seen: set[str] = set()
        for index, row in enumerate(assertion_rows):
            where = f"assertions[{index}]"
            if not isinstance(row, dict):
                problems.append(f"{where} must be a mapping")
                continue
            assertion_id = row.get("id")
            if not _non_empty_string(assertion_id):
                problems.append(f"{where}.id is required")
                continue
            if assertion_id in seen:
                problems.append(f"duplicate assertion id: {assertion_id}")
            seen.add(assertion_id)
            status = row.get("status")
            if status not in {"PASS", "FAIL"}:
                problems.append(f"{where}.status must be PASS or FAIL")
            else:
                assertion_statuses[assertion_id] = status
            refs = row.get("evidence_refs")
            if not isinstance(refs, list) or not refs:
                problems.append(f"{where}.evidence_refs must be non-empty")
            else:
                for ref_id in refs:
                    if ref_id not in evidence_ids:
                        problems.append(
                            f"{where}.evidence_refs references unknown id {ref_id!r}"
                        )
        missing = expected - seen
        extra = seen - expected
        if missing:
            problems.append(
                "missing required assertions: " + ", ".join(sorted(missing))
            )
        if extra:
            problems.append(
                "unexpected assertions: " + ", ".join(sorted(extra))
            )

    verdict = doc.get("validator_verdict")
    if verdict not in {"PASS", "FAIL"}:
        problems.append("validator_verdict must be PASS or FAIL")
    elif verdict == "PASS":
        failed = sorted(
            assertion_id
            for assertion_id, status in assertion_statuses.items()
            if status != "PASS"
        )
        if failed:
            problems.append(
                "validator_verdict PASS contradicts failed assertions: "
                + ", ".join(failed)
            )

    return problems


def _validate_scenario(capability: str, scenario: Any) -> list[str]:
    problems: list[str] = []
    expected_id, required_identifiers = SCENARIO_CONTRACT[capability]
    if not isinstance(scenario, dict):
        return ["scenario must be a mapping"]

    if scenario.get("id") != expected_id:
        problems.append(
            f"{capability} scenario.id must be {expected_id}"
        )

    identifiers = scenario.get("identifiers")
    if not isinstance(identifiers, dict):
        return problems + ["scenario.identifiers must be a mapping"]

    for key in required_identifiers:
        if not _non_empty_string(identifiers.get(key)):
            problems.append(f"scenario.identifiers.{key} is required")

    if capability == "P0c":
        before = identifiers.get("from_revision_id")
        after = identifiers.get("to_revision_id")
        if _non_empty_string(before) and before == after:
            problems.append("P0c from_revision_id and to_revision_id must differ")

    return problems


def validate_path(path: Path) -> list[str]:
    return validate_document(load_yaml(path))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()

    problems = validate_path(args.path)
    if problems:
        print("PRODUCT_QUALIFICATION_EVIDENCE=FAIL")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    doc = load_yaml(args.path)
    print(
        "PRODUCT_QUALIFICATION_EVIDENCE=PASS "
        f"capability={doc['capability_id']} "
        f"runtime_sha={doc['deployed_runtime_sha']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
