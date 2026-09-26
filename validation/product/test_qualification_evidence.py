#!/usr/bin/env python3
from __future__ import annotations

import copy
import io
import sys
import tempfile
from contextlib import redirect_stdout
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
            "id": "entity",
            "kind": "persisted_entity",
            "ref": "project:project-1/document:document-1/revision:revision-1",
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
        "control_ref": "validation/product/c2pro-master-product-control-v1.yaml",
        "control_baseline_sha": "2" * 40,
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


def _control(
    reconciled_sha: str = "2" * 40,
    runtime_sha: str = "1" * 40,
) -> dict:
    return {
        "production_position": {
            "reconciled_against_main_sha": reconciled_sha,
            "deployed_runtime_sha": runtime_sha,
        }
    }



def test_positive_bundle_binds_to_canonical_product_control() -> None:
    doc = _doc()
    assert q.validate_document(doc) == []
    assert q.validate_against_control(doc, _control()) == []


def test_control_baseline_sha_must_match_canonical_product_control() -> None:
    doc = _doc()
    problems = q.validate_against_control(doc, _control(reconciled_sha="3" * 40))
    assert any("control_baseline_sha does not match" in problem for problem in problems)


def test_runtime_sha_must_match_canonical_product_control() -> None:
    doc = _doc()
    problems = q.validate_against_control(doc, _control(runtime_sha="4" * 40))
    assert any("deployed_runtime_sha does not match" in problem for problem in problems)


def test_unverified_canonical_runtime_blocks_qualification() -> None:
    problems = q.validate_against_control(_doc(), _control(runtime_sha="UNVERIFIED"))
    assert any("Product Control deployed_runtime_sha" in problem for problem in problems)


def test_unknown_top_level_field_fails_closed() -> None:
    doc = _doc()
    doc["innocent_but_noncanonical"] = True
    problems = q.validate_document(doc)
    assert any("unexpected top-level fields" in problem for problem in problems)


def test_invalid_observed_at_fails() -> None:
    doc = _doc()
    doc["observed_at"] = "yesterday"
    problems = q.validate_document(doc)
    assert any("ISO-8601" in problem for problem in problems)


def test_naive_observed_at_fails() -> None:
    doc = _doc()
    doc["observed_at"] = "2026-09-26T10:00:00"
    problems = q.validate_document(doc)
    assert any("timezone" in problem for problem in problems)


def test_pass_evidence_must_be_immutable_or_content_addressed() -> None:
    doc = _doc()
    doc["evidence_refs"][0]["immutable"] = False
    doc["evidence_refs"][0]["sha256"] = None
    problems = q.validate_document(doc)
    assert any("immutable or content-addressed" in problem for problem in problems)


def test_untyped_other_evidence_kind_is_rejected() -> None:
    doc = _doc()
    doc["evidence_refs"][0]["kind"] = "other"
    problems = q.validate_document(doc)
    assert any("kind is invalid" in problem for problem in problems)


def test_non_string_assertion_evidence_ref_fails_without_crashing() -> None:
    doc = _doc()
    doc["assertions"][0]["evidence_refs"] = [{"not": "an-id"}]
    problems = q.validate_document(doc)
    assert any("entries must be non-empty strings" in problem for problem in problems)


def test_non_string_assertion_note_fails_closed() -> None:
    doc = _doc()
    doc["assertions"][0]["note"] = {"unexpected": "mapping"}
    problems = q.validate_document(doc)
    assert any(".note must be a string or null" in problem for problem in problems)


def test_non_string_scenario_identifier_fails_closed() -> None:
    doc = _doc()
    doc["scenario"]["identifiers"]["extra"] = {"nested": "value"}
    problems = q.validate_document(doc)
    assert any("keys and values must be non-empty strings" in problem for problem in problems)



def test_malformed_enum_types_fail_closed_without_crashing() -> None:
    malformed_cases = [
        ("capability_id", ["P0b"], "unknown capability_id"),
        ("validator_verdict", ["PASS"], "validator_verdict must be PASS or FAIL"),
    ]
    for field, value, expected_problem in malformed_cases:
        doc = _doc()
        doc[field] = value
        problems = q.validate_document(doc)
        assert any(expected_problem in problem for problem in problems)

    doc = _doc()
    doc["evidence_refs"][0]["kind"] = ["deployment"]
    problems = q.validate_document(doc)
    assert any("kind is invalid" in problem for problem in problems)

    doc = _doc()
    doc["assertions"][0]["status"] = ["PASS"]
    problems = q.validate_document(doc)
    assert any(".status must be PASS or FAIL" in problem for problem in problems)


def test_cli_separates_bundle_validity_from_failed_qualification_verdict() -> None:
    doc = _doc()
    doc["assertions"][0]["status"] = "FAIL"
    doc["validator_verdict"] = "FAIL"

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        evidence_dir = root / "evidence"
        evidence_dir.mkdir()
        bundle_path = evidence_dir / "p0b-failed.yaml"
        control_path = root / "control.yaml"
        bundle_path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
        control_path.write_text(yaml.safe_dump(_control(), sort_keys=False), encoding="utf-8")

        old_evidence_dir = q.DEFAULT_EVIDENCE_DIR
        old_control_path = q.DEFAULT_CONTROL_PATH
        old_argv = sys.argv[:]
        try:
            q.DEFAULT_EVIDENCE_DIR = evidence_dir
            q.DEFAULT_CONTROL_PATH = control_path
            sys.argv = ["validate_qualification_evidence.py"]
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = q.main()
        finally:
            q.DEFAULT_EVIDENCE_DIR = old_evidence_dir
            q.DEFAULT_CONTROL_PATH = old_control_path
            sys.argv = old_argv

    rendered = output.getvalue()
    assert exit_code == 0
    assert "PRODUCT_QUALIFICATION_EVIDENCE=VALID" in rendered
    assert "qualification_verdict=FAIL" in rendered
    assert "PRODUCT_QUALIFICATION_EVIDENCE=PASS" not in rendered


def test_unknown_assertion_field_fails_closed() -> None:
    doc = _doc()
    doc["assertions"][0]["promotes_lifecycle"] = True
    problems = q.validate_document(doc)
    assert any("unexpected fields" in problem for problem in problems)


def test_product_control_workflow_watches_and_validates_qualification_evidence() -> None:
    workflow = (HERE.parent.parent / ".github" / "workflows" / "c2pro-product-control-guard.yml").read_text(
        encoding="utf-8"
    )
    assert workflow.count('evidence/product-qualification/**') >= 2
    assert "python validation/product/validate_qualification_evidence.py" in workflow


def test_cli_uses_fixed_repo_evidence_directory_and_control_path() -> None:
    assert q.DEFAULT_EVIDENCE_DIR == q.REPO_ROOT / "evidence" / "product-qualification"
    assert q.DEFAULT_CONTROL_PATH == HERE / "c2pro-master-product-control-v1.yaml"


def test_schema_declares_evidence_not_authority() -> None:
    schema = yaml.safe_load(
        (HERE / "qualification-evidence.schema.yaml").read_text(encoding="utf-8")
    )
    assert schema["$id"] == q.SCHEMA_ID
    assert schema["additionalProperties"] is False
    assert schema["properties"]["lifecycle_authority"]["const"] is False
    assert schema["properties"]["control_ref"]["const"] == "validation/product/c2pro-master-product-control-v1.yaml"
    assert schema["properties"]["control_baseline_sha"]["pattern"] == "^[0-9a-f]{40}$"
    assert schema["properties"]["capability_id"]["enum"] == ["P0b", "P0c", "P0d"]
    for required_key in schema["required"]:
        assert required_key in schema["properties"], required_key


def test_p0b_positive_contract() -> None:
    assert q.validate_document(_doc("P0b")) == []


def test_p0c_positive_contract() -> None:
    assert q.validate_document(_doc("P0c")) == []


def test_p0d_positive_contract() -> None:
    assert q.validate_document(_doc("P0d")) == []


def test_missing_control_baseline_sha_fails() -> None:
    doc = _doc()
    doc["control_baseline_sha"] = "UNVERIFIED"
    problems = q.validate_document(doc)
    assert any("control_baseline_sha" in problem for problem in problems)


def test_pass_requires_deployment_and_persisted_entity_evidence() -> None:
    doc = _doc()
    doc["evidence_refs"] = [
        ref for ref in doc["evidence_refs"] if ref["kind"] not in {"deployment", "persisted_entity"}
    ]
    for assertion in doc["assertions"]:
        assertion["evidence_refs"] = ["api", "ui"]
    problems = q.validate_document(doc)
    assert any("requires deployment evidence" in problem for problem in problems)
    assert any("requires persisted_entity evidence" in problem for problem in problems)


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
