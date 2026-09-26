#!/usr/bin/env python3
"""Validate non-authoritative production-qualification evidence bundles.

The evidence bundle proves a capability-specific production scenario. It never
owns lifecycle state: Product Control remains the sole authority that may
promote a capability to PROD_VALIDATED after this evidence passes review.
"""
from __future__ import annotations

import argparse
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from yaml.constructor import ConstructorError

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
    "review",
}
FORBIDDEN_AUTHORITY_KEYS = {
    "prod_validation_status",
    "lifecycle_status",
    "realization_status",
    "deployment_status",
    "work_status",
}

ALLOWED_TOP_LEVEL_KEYS = {
    "schema",
    "schema_version",
    "lifecycle_authority",
    "repository",
    "control_ref",
    "control_commit_sha",
    "control_baseline_sha",
    "capability_id",
    "target_state",
    "environment",
    "deployed_runtime_sha",
    "observed_at",
    "scenario",
    "assertions",
    "evidence_refs",
    "validator_verdict",
}
ASSERTION_KEYS = {"id", "status", "evidence_refs", "note"}
EVIDENCE_REF_KEYS = {"id", "kind", "ref", "immutable", "sha256"}
SCENARIO_KEYS = {"id", "identifiers"}
CONTROL_REF = "validation/product/c2pro-master-product-control-v1.yaml"
DEFAULT_CONTROL_PATH = Path(__file__).with_name("c2pro-master-product-control-v1.yaml")
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVIDENCE_DIR = REPO_ROOT / "evidence" / "product-qualification"

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


class _NoDuplicateSafeLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate or unhashable mapping keys."""


def _construct_unique_mapping(
    loader: _NoDuplicateSafeLoader,
    node: yaml.nodes.MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as exc:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "mapping keys must be hashable",
                key_node.start_mark,
            ) from exc
        if duplicate:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"duplicate mapping key: {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_NoDuplicateSafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
        value = yaml.load(raw, Loader=_NoDuplicateSafeLoader)
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ValueError(f"cannot parse qualification YAML: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("qualification evidence must be a mapping")
    return value


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_document(doc: dict[str, Any]) -> list[str]:
    problems: list[str] = []

    non_string_top_level = [key for key in doc if not isinstance(key, str)]
    if non_string_top_level:
        problems.append("top-level field names must be strings")
    unknown_top_level = sorted(
        key for key in doc if isinstance(key, str) and key not in ALLOWED_TOP_LEVEL_KEYS
    )
    if unknown_top_level:
        problems.append(
            "unexpected top-level fields: " + ", ".join(unknown_top_level)
        )

    if doc.get("schema") != SCHEMA_ID:
        problems.append(f"schema must be {SCHEMA_ID}")
    schema_version = doc.get("schema_version")
    if type(schema_version) is not int or schema_version != 1:
        problems.append("schema_version must be integer 1")
    if doc.get("lifecycle_authority") is not False:
        problems.append("lifecycle_authority must be false")
    if doc.get("repository") != "AI-Gen-AI/C2Pro":
        problems.append("repository must be AI-Gen-AI/C2Pro")
    if doc.get("control_ref") != CONTROL_REF:
        problems.append("control_ref must point to the canonical Product Control YAML")
    control_commit_sha = doc.get("control_commit_sha")
    if (
        not isinstance(control_commit_sha, str)
        or not SHA_RE.fullmatch(control_commit_sha)
    ):
        problems.append("control_commit_sha must be an exact 40-character SHA")
    control_sha = doc.get("control_baseline_sha")
    if not isinstance(control_sha, str) or not SHA_RE.fullmatch(control_sha):
        problems.append("control_baseline_sha must be an exact 40-character SHA")
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
    capability_valid = isinstance(capability, str) and capability in REQUIRED_ASSERTIONS
    if not capability_valid:
        problems.append(f"unknown capability_id: {capability!r}")

    runtime_sha = doc.get("deployed_runtime_sha")
    if not isinstance(runtime_sha, str) or not SHA_RE.fullmatch(runtime_sha):
        problems.append(
            "deployed_runtime_sha must be an exact observed 40-character SHA"
        )

    observed_at = doc.get("observed_at")
    if not _non_empty_string(observed_at):
        problems.append("observed_at is required")
    else:
        try:
            parsed_observed_at = datetime.fromisoformat(
                observed_at.replace("Z", "+00:00")
            )
            if parsed_observed_at.tzinfo is None:
                problems.append("observed_at must include a timezone")
        except ValueError:
            problems.append("observed_at must be an ISO-8601 date-time")

    if capability_valid:
        problems.extend(_validate_scenario(capability, doc.get("scenario")))

    evidence = doc.get("evidence_refs")
    evidence_ids: set[str] = set()
    evidence_kinds: set[str] = set()
    if not isinstance(evidence, list) or not evidence:
        problems.append("evidence_refs must be a non-empty list")
    else:
        for index, ref in enumerate(evidence):
            where = f"evidence_refs[{index}]"
            if not isinstance(ref, dict):
                problems.append(f"{where} must be a mapping")
                continue
            if any(not isinstance(key, str) for key in ref):
                problems.append(f"{where} field names must be strings")
            extra_ref_fields = sorted(
                key for key in ref if isinstance(key, str) and key not in EVIDENCE_REF_KEYS
            )
            if extra_ref_fields:
                problems.append(
                    f"{where} has unexpected fields: "
                    + ", ".join(extra_ref_fields)
                )
            ref_id = ref.get("id")
            if not _non_empty_string(ref_id):
                problems.append(f"{where}.id is required")
            elif ref_id in evidence_ids:
                problems.append(f"duplicate evidence id: {ref_id}")
            else:
                evidence_ids.add(ref_id)
            kind = ref.get("kind")
            if not isinstance(kind, str) or kind not in ALLOWED_KINDS:
                problems.append(f"{where}.kind is invalid")
            else:
                evidence_kinds.add(kind)
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
    elif capability_valid:
        expected = set(REQUIRED_ASSERTIONS[capability])
        seen: set[str] = set()
        for index, row in enumerate(assertion_rows):
            where = f"assertions[{index}]"
            if not isinstance(row, dict):
                problems.append(f"{where} must be a mapping")
                continue
            if any(not isinstance(key, str) for key in row):
                problems.append(f"{where} field names must be strings")
            extra_assertion_fields = sorted(
                key for key in row if isinstance(key, str) and key not in ASSERTION_KEYS
            )
            if extra_assertion_fields:
                problems.append(
                    f"{where} has unexpected fields: "
                    + ", ".join(extra_assertion_fields)
                )
            assertion_id = row.get("id")
            if not _non_empty_string(assertion_id):
                problems.append(f"{where}.id is required")
                continue
            if assertion_id in seen:
                problems.append(f"duplicate assertion id: {assertion_id}")
            seen.add(assertion_id)
            status = row.get("status")
            if not isinstance(status, str) or status not in {"PASS", "FAIL"}:
                problems.append(f"{where}.status must be PASS or FAIL")
            else:
                assertion_statuses[assertion_id] = status
            note = row.get("note")
            if note is not None and not isinstance(note, str):
                problems.append(f"{where}.note must be a string or null")
            refs = row.get("evidence_refs")
            if not isinstance(refs, list) or not refs:
                problems.append(f"{where}.evidence_refs must be non-empty")
            else:
                for ref_id in refs:
                    if not _non_empty_string(ref_id):
                        problems.append(
                            f"{where}.evidence_refs entries must be non-empty strings"
                        )
                        continue
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
    if verdict == "PASS":
        for required_kind in ("deployment", "persisted_entity"):
            if required_kind not in evidence_kinds:
                problems.append(
                    f"validator_verdict PASS requires {required_kind} evidence"
                )
        if isinstance(evidence, list):
            for index, ref in enumerate(evidence):
                if not isinstance(ref, dict):
                    continue
                if ref.get("immutable") is not True and ref.get("sha256") is None:
                    problems.append(
                        f"evidence_refs[{index}] must be immutable or content-addressed for PASS"
                    )
    if not isinstance(verdict, str) or verdict not in {"PASS", "FAIL"}:
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

    if any(not isinstance(key, str) for key in scenario):
        problems.append("scenario field names must be strings")
    extra_scenario_fields = sorted(
        key for key in scenario if isinstance(key, str) and key not in SCENARIO_KEYS
    )
    if extra_scenario_fields:
        problems.append(
            "scenario has unexpected fields: "
            + ", ".join(extra_scenario_fields)
        )

    if scenario.get("id") != expected_id:
        problems.append(
            f"{capability} scenario.id must be {expected_id}"
        )

    identifiers = scenario.get("identifiers")
    if not isinstance(identifiers, dict):
        return problems + ["scenario.identifiers must be a mapping"]

    for key, value in identifiers.items():
        if not _non_empty_string(key) or not _non_empty_string(value):
            problems.append(
                "scenario.identifiers keys and values must be non-empty strings"
            )
    for key in required_identifiers:
        if not _non_empty_string(identifiers.get(key)):
            problems.append(f"scenario.identifiers.{key} is required")

    if capability == "P0c":
        before = identifiers.get("from_revision_id")
        after = identifiers.get("to_revision_id")
        if _non_empty_string(before) and before == after:
            problems.append("P0c from_revision_id and to_revision_id must differ")

    return problems


def validate_against_control(
    doc: dict[str, Any], control: dict[str, Any]
) -> list[str]:
    """Bind a non-authoritative evidence bundle to canonical Product Control truth."""
    problems: list[str] = []
    production = control.get("production_position")
    if not isinstance(production, dict):
        return ["Product Control production_position must be a mapping"]

    control_sha = production.get("reconciled_against_main_sha")
    if doc.get("control_baseline_sha") != control_sha:
        problems.append(
            "control_baseline_sha does not match Product Control "
            "production_position.reconciled_against_main_sha"
        )

    control_runtime = production.get("deployed_runtime_sha")
    if not isinstance(control_runtime, str) or not SHA_RE.fullmatch(control_runtime):
        problems.append(
            "Product Control deployed_runtime_sha must be an exact observed 40-character SHA"
        )
    elif doc.get("deployed_runtime_sha") != control_runtime:
        problems.append(
            "deployed_runtime_sha does not match Product Control production runtime"
        )

    return problems


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=check,
        capture_output=True,
        text=True,
    )


def _canonical_main_ref() -> str:
    for candidate in ("origin/main", "main"):
        result = _git("rev-parse", "--verify", "--quiet", candidate, check=False)
        if result.returncode == 0:
            return candidate
    raise ValueError("cannot verify canonical main ancestry: no origin/main or main ref")


def load_control_at_commit(commit_sha: str) -> dict[str, Any]:
    """Load canonical Product Control from an immutable commit on main history."""
    if not isinstance(commit_sha, str) or not SHA_RE.fullmatch(commit_sha):
        raise ValueError("control_commit_sha must be an exact 40-character SHA")

    canonical_main = _canonical_main_ref()
    ancestry = _git(
        "merge-base",
        "--is-ancestor",
        commit_sha,
        canonical_main,
        check=False,
    )
    if ancestry.returncode != 0:
        raise ValueError(
            "control_commit_sha must be an ancestor of canonical main history"
        )

    snapshot = _git("show", f"{commit_sha}:{CONTROL_REF}", check=False)
    if snapshot.returncode != 0:
        raise ValueError(
            "control_commit_sha does not contain the canonical Product Control YAML"
        )

    control = yaml.safe_load(snapshot.stdout)
    if not isinstance(control, dict):
        raise ValueError("historical Product Control snapshot must be a mapping")
    return control


def validate_path(
    path: Path,
    control_loader: Any = load_control_at_commit,
) -> list[str]:
    try:
        doc = load_yaml(path)
    except ValueError as exc:
        return [str(exc)]

    problems = validate_document(doc)
    if problems:
        return problems

    try:
        control = control_loader(doc["control_commit_sha"])
    except (KeyError, TypeError, ValueError) as exc:
        return [f"historical Product Control binding failed: {exc}"]

    problems.extend(validate_against_control(doc, control))
    return problems


def main(control_loader: Any = load_control_at_commit) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate committed product-qualification evidence bundles from "
            "evidence/product-qualification/. Arbitrary filesystem paths are "
            "intentionally unsupported."
        )
    )
    parser.parse_args()

    if not DEFAULT_EVIDENCE_DIR.exists():
        print("PRODUCT_QUALIFICATION_EVIDENCE=NO_BUNDLES")
        return 0

    bundle_paths = sorted(DEFAULT_EVIDENCE_DIR.glob("*.yaml"))
    if not bundle_paths:
        print("PRODUCT_QUALIFICATION_EVIDENCE=NO_BUNDLES")
        return 0

    failed = False
    for bundle_path in bundle_paths:
        problems = validate_path(bundle_path, control_loader)
        if problems:
            failed = True
            print(
                "PRODUCT_QUALIFICATION_EVIDENCE=INVALID "
                f"bundle={bundle_path.name}"
            )
            for problem in problems:
                print(f"  - {problem}")
            continue

        doc = load_yaml(bundle_path)
        print(
            "PRODUCT_QUALIFICATION_EVIDENCE=VALID "
            f"bundle={bundle_path.name} "
            f"capability={doc['capability_id']} "
            f"qualification_verdict={doc['validator_verdict']} "
            f"runtime_sha={doc['deployed_runtime_sha']}"
        )

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
