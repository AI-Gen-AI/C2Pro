#!/usr/bin/env python3
from __future__ import annotations

import copy
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import validate_qualification_evidence as q  # noqa: E402


def _evidence() -> list[dict]:
    return [
        {
            "id": "deploy",
            "kind": "deployment",
            "ref": "deployment:prod:abc",
            "immutable": True,
            "sha256": None,
        },
        {
            "id": "api",
            "kind": "api_capture",
            "ref": "artifact:api-health",
            "immutable": True,
            "sha256": "a" * 64,
        },
        {
            "id": "ui",
            "kind": "ui_report",
            "ref": "artifact:ui-health",
            "immutable": True,
            "sha256": "b" * 64,
        },
    ]


def _doc(capability: str = "P0b") -> dict:
    scenario = {
        "P0b": {
            "id": "single_document_health",
            "identifiers": {
                "project_id": "project-1",
                "document_id": "document-1",
                "source_revision_id": "revision-1",
            },
        },
        "P0c": {
            "id": "what_changed_two_revisions",
            "identifiers": {
                "project_id": "project-1",
                "document_id": "document-1",
                "from_revision_id": "revision-1",
                "to_revision_id": "revision-2",
            },
        },
        "P0d": {
            "id": "current_state_report",
            "identifiers": {
                "project_id": "project-1",
                "state_ref": "snapshot-1",
            },
        },
    }[capability]
    return {
        "schema": q.SCHEMA_ID,
        "schema_version": 1,
        "lifecycle_authority": False,
        "repository": "AI-Gen-AI/C2Pro",
        "capability_id": capability,
        "target_state": "PROD_VALIDATED",
        "environment": "production",
        "deployed_runtime_sha": "1" * 40,
        "observed_at": "2026-09-26T10:00:00Z",
        "scenario": scenario,
        "assertions": [
            {"id": assertion_id, "status": "PASS", "evidence_refs": ["api", "ui"]}
            for assertion_id in q.REQUIRED_ASSERTIONS[capability]
        ],
        "evidence_refs": _evidence(),
        "validator_verdict": "PASS",
    }


def test_schema_declares_evidence_not_authority() -> None:
    schema = yaml.safe_load(
        (HERE / "qualification-evidence.schema.yaml").read_text(encoding="utf-8")
    )
    assert schema["$id"] == q.SCHEMA_ID
    assert schema["additionalProperties"] is False
    assert schema["properties"]["lifecycle_authority"]["const"] is False


def test_p0b_positive_contract() -> None:
    assert q.validate_document(_doc("P0b")) == []


def test_p0c_positive_contract() -> None:
    assert q.validate_document(_doc("P0c")) == []


def test_p0d_positive_contract() -> None:
    assert q.validate_document(_doc("P0d")) == []


def test_unverified_runtime_sha_fails() -> None:
    doc = _doc()
    doc["deployed_runtime_sha"] = "UNVERIFIED"
    problems = q.validate_document(doc)
    assert any("40-character SHA" in problem for problem in problems)


def test_evidence_bundle_cannot_claim_lifecycle_state() -> None:
    doc = _doc()
    doc["prod_validation_status"] = "PROD_VALIDATED"
    problems = q.validate_document(doc)
    assert any("may not own lifecycle fields" in problem for problem in problems)


def test_pass_requires_every_required_assertion() -> None:
    doc = _doc()
    doc["assertions"] = doc["assertions"][:-1]
    problems = q.validate_document(doc)
    assert any("missing required assertions" in problem for problem in problems)


def test_pass_cannot_hide_failed_assertion() -> None:
    doc = _doc()
    doc["assertions"][0]["status"] = "FAIL"
    problems = q.validate_document(doc)
    assert any("PASS contradicts failed assertions" in problem for problem in problems)


def test_assertion_requires_known_evidence_reference() -> None:
    doc = _doc()
    doc["assertions"][0]["evidence_refs"] = ["missing-artifact"]
    problems = q.validate_document(doc)
    assert any("unknown id" in problem for problem in problems)


def test_p0c_requires_distinct_revisions() -> None:
    doc = _doc("P0c")
    doc["scenario"]["identifiers"]["to_revision_id"] = "revision-1"
    problems = q.validate_document(doc)
    assert any("must differ" in problem for problem in problems)


def test_p0d_requires_state_reference() -> None:
    doc = _doc("P0d")
    doc["scenario"]["identifiers"]["state_ref"] = ""
    problems = q.validate_document(doc)
    assert any("state_ref is required" in problem for problem in problems)


def test_unexpected_assertion_fails() -> None:
    doc = _doc()
    doc["assertions"].append(
        {"id": "made_up_gate", "status": "PASS", "evidence_refs": ["api"]}
    )
    problems = q.validate_document(doc)
    assert any("unexpected assertions" in problem for problem in problems)


def _all_tests() -> list:
    return [
        value
        for name, value in sorted(globals().items())
        if name.startswith("test_") and callable(value)
    ]


if __name__ == "__main__":
    failures = 0
    for test in _all_tests():
        try:
            test()
            print(f"PASS  {test.__name__}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL  {test.__name__}: {exc}")
    total = len(_all_tests())
    print(f"\n{total - failures}/{total} passed")
    raise SystemExit(1 if failures else 0)
