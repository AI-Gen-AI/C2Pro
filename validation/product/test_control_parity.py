#!/usr/bin/env python3
"""Positive + NEGATIVE tests for the product-control parity guard (review fix 1).

Proves the checker (a) passes on the pristine control files, and (b) DETECTS drift:
a contradictory MD value, a missing canonical key, a WBS-status contradiction, and an
out-of-enum status all make the checker report a problem.

Runnable two ways:
    python validation/product/test_control_parity.py     # standalone runner
    pytest validation/product/test_control_parity.py      # pytest
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import check_control_parity as c  # noqa: E402

_MD_TEXT = c._MD.read_text(encoding="utf-8")


def test_pristine_passes() -> None:
    assert c.run() == [], "pristine control files must have zero parity problems"


def test_enums_valid_on_real_yaml() -> None:
    assert c.validate_enums(c.load_yaml()) == [], "every ADR/WBS status must be in its enum"


def _compare_with_mutated_md(mutated_md: str) -> list[str]:
    yaml_canon = c.extract_canonical(c.load_yaml())
    return c.compare(yaml_canon, c.parse_md_block(mutated_md))


def test_md_value_contradiction_detected() -> None:
    mutated = _MD_TEXT.replace(
        "reliability_operability_baseline=CLOSED",
        "reliability_operability_baseline=OPEN",
    )
    problems = _compare_with_mutated_md(mutated)
    assert any("VALUE DRIFT" in p and "reliability_operability_baseline" in p for p in problems), problems


def test_md_missing_key_detected() -> None:
    mutated = _MD_TEXT.replace("adr.ADR-024.realization=DESIGNED\n", "")
    problems = _compare_with_mutated_md(mutated)
    assert any("MD missing" in p and "adr.ADR-024.realization" in p for p in problems), problems


def test_wbs_realization_contradiction_detected() -> None:
    mutated = _MD_TEXT.replace("wbs.PWBS-OPS-TRUST.realization=DEPLOYED", "wbs.PWBS-OPS-TRUST.realization=NONE")
    problems = _compare_with_mutated_md(mutated)
    assert any("VALUE DRIFT" in p and "wbs.PWBS-OPS-TRUST.realization" in p for p in problems), problems


def test_wbs_work_status_contradiction_detected() -> None:
    # DEPLOYED != CLOSED: flipping OPS-TRUST work_status must be caught independently of realization.
    mutated = _MD_TEXT.replace("wbs.PWBS-OPS-TRUST.work_status=ACTIVE", "wbs.PWBS-OPS-TRUST.work_status=CLOSED")
    problems = _compare_with_mutated_md(mutated)
    assert any("VALUE DRIFT" in p and "wbs.PWBS-OPS-TRUST.work_status" in p for p in problems), problems


def test_invalid_work_status_enum_detected() -> None:
    doc = c.load_yaml()
    doc["product_wbs"][0]["work_status"] = "NOT_A_WORK_STATUS"
    problems = c.validate_enums(doc)
    assert any("NOT_A_WORK_STATUS" in p for p in problems), problems


def test_coherence_cutover_contradiction_detected() -> None:
    mutated = _MD_TEXT.replace(
        "coherence.global_authoritative_cutover=NO",
        "coherence.global_authoritative_cutover=YES",
    )
    problems = _compare_with_mutated_md(mutated)
    assert any("VALUE DRIFT" in p and "global_authoritative_cutover" in p for p in problems), problems


def test_missing_block_fails() -> None:
    problems = _compare_with_mutated_md("no canonical block here at all")
    assert any("block missing" in p for p in problems), problems


def test_invalid_enum_detected() -> None:
    doc = c.load_yaml()
    doc["adr_realization"][0]["realization_status"] = "BOGUS_STATE"
    problems = c.validate_enums(doc)
    assert any("BOGUS_STATE" in p for p in problems), problems


def test_invalid_subtrack_enum_detected() -> None:
    doc = c.load_yaml()
    for row in doc["adr_realization"]:
        if str(row.get("adr", "")).startswith("ADR-009"):
            row["subtracks"]["v2"]["deployment_status"] = "NOT_AN_ENUM"
    problems = c.validate_enums(doc)
    assert any("NOT_AN_ENUM" in p for p in problems), problems



# ── P0b L4 slice lifecycle + residual registry (schema_version 4) ─────────────


def test_p0b_slice_statuses_are_canonical_and_parity_checked() -> None:
    """Positive: the five current L4 statuses are exact in BOTH YAML and the MD block."""
    expected = {
        "P0b-L4-1": "DONE",
        "P0b-L4-2": "DONE",
        "P0b-L4-3": "DONE",
        "P0b-L4-4": "PARTIAL",
        "P0b-L4-5": "BLOCKED",
    }
    canon = c.extract_canonical(c.load_yaml())
    md = c.parse_md_block(_MD_TEXT)
    for slice_id, status in expected.items():
        key = f"p0b.slice.{slice_id}.status"
        assert canon[key] == status, f"YAML {key}={canon.get(key)} != {status}"
        assert md[key] == status, f"MD {key}={md.get(key)} != {status}"


def test_invalid_slice_status_detected() -> None:
    """Negative: a slice status outside slice_status must FAIL."""
    doc = c.load_yaml()
    doc["p0b_vertical_contract"]["slices"][0]["slice_status"] = "SHIPPED_ISH"
    problems = c.validate_enums(doc)
    assert any("SHIPPED_ISH" in p for p in problems), problems


def test_legacy_freeform_slice_status_detected() -> None:
    """Negative: the old un-validated `status:` key must not come back."""
    doc = c.load_yaml()
    doc["p0b_vertical_contract"]["slices"][0]["status"] = "planned"
    problems = c.validate_enums(doc)
    assert any("legacy free-form 'status'" in p for p in problems), problems


def test_md_slice_status_contradiction_detected() -> None:
    """Negative: an MD/YAML slice-status contradiction must FAIL."""
    mutated = _MD_TEXT.replace(
        "p0b.slice.P0b-L4-3.status=DONE", "p0b.slice.P0b-L4-3.status=NOT_STARTED"
    )
    problems = _compare_with_mutated_md(mutated)
    assert any("VALUE DRIFT" in p and "p0b.slice.P0b-L4-3.status" in p for p in problems), problems


def test_residual_is_registered_and_parity_checked() -> None:
    """Positive: the granularity residual, its status and its blocking edge are canonical."""
    canon = c.extract_canonical(c.load_yaml())
    md = c.parse_md_block(_MD_TEXT)
    rid = "P0b-R1-EVIDENCE-GRANULARITY"
    assert canon["p0b.residual_ids"] == rid
    assert canon[f"p0b.residual.{rid}.status"] == "PLANNED"
    assert canon[f"p0b.residual.{rid}.blocks"] == "P0b-L4-5"
    for key in ("p0b.residual_ids", f"p0b.residual.{rid}.status", f"p0b.residual.{rid}.blocks"):
        assert md[key] == canon[key], f"MD/YAML drift on {key}"


def test_missing_residual_detected() -> None:
    """Negative: dropping the residual registry must FAIL (open residuals stay explicit)."""
    doc = c.load_yaml()
    doc["p0b_vertical_contract"]["residuals"] = []
    problems = c.validate_enums(doc)
    assert any("no 'residuals' registered" in p for p in problems), problems


def test_invalid_residual_status_detected() -> None:
    """Negative: a residual status outside residual_status must FAIL."""
    doc = c.load_yaml()
    doc["p0b_vertical_contract"]["residuals"][0]["status"] = "MAYBE_LATER"
    problems = c.validate_enums(doc)
    assert any("MAYBE_LATER" in p for p in problems), problems


def test_residual_blocking_contradiction_detected() -> None:
    """Negative: a residual whose blocked slice is not BLOCKED must FAIL."""
    doc = c.load_yaml()
    for sl in doc["p0b_vertical_contract"]["slices"]:
        if sl["id"] == "P0b-L4-5":
            sl["slice_status"] = "NOT_STARTED"
    problems = c.validate_enums(doc)
    assert any("not BLOCKED" in p for p in problems), problems


def test_residual_blocking_unknown_slice_detected() -> None:
    """Negative: a residual blocking a slice id that does not exist must FAIL."""
    doc = c.load_yaml()
    doc["p0b_vertical_contract"]["residuals"][0]["blocks"] = "P0b-L4-9"
    problems = c.validate_enums(doc)
    assert any("not a known P0b slice id" in p for p in problems), problems

def _all_tests() -> list:
    return [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]


if __name__ == "__main__":
    failures = 0
    for t in _all_tests():
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as exc:  # noqa: PERF203
            failures += 1
            print(f"FAIL  {t.__name__}: {exc}")
    total = len(_all_tests())
    print(f"\n{total - failures}/{total} passed")
    raise SystemExit(1 if failures else 0)
