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

import hashlib
import re
import sys
import tempfile

import yaml
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import check_control_parity as c  # noqa: E402

_MD_TEXT = c._MD.read_text(encoding="utf-8")
_ARCH_BASELINE_TEXT = (_HERE.parents[1] / "docs/architecture/C2PRO_TECHNICAL_BASELINE_2026-10-01.md").read_text(encoding="utf-8")


def test_pristine_passes() -> None:
    assert c.run() == [], "pristine control files must have zero parity problems"


def test_atomic_work_package_table_has_exact_state_and_assigned_role() -> None:
    """All 28 Product task rows must mirror the canonical YAML authority."""
    assert c.validate_work_package_mirror(c.load_yaml(), _MD_TEXT) == []


def test_atomic_work_package_status_drift_fails() -> None:
    row = next(
        line for line in _MD_TEXT.splitlines()
        if line.startswith("| PQ-HITL-03.1 /")
    )
    assert "| IN_PROGRESS |" in row
    changed = _MD_TEXT.replace(row, row.replace("| IN_PROGRESS |", "| PLANNED |"))
    problems = c.validate_work_package_mirror(c.load_yaml(), changed)
    assert any("PQ-HITL-03.1" in p and "status" in p for p in problems), problems


def test_invalid_atomic_status_fails_even_if_human_table_matches() -> None:
    doc = c.load_yaml()
    packages = doc["product_quality_hitl_2026_10_08"]["delivery_specification"]["work_packages"]
    task = next(row for row in packages if row["id"] == "PQ-HITL-03.1")
    task["status"] = "IN_PROGRES"
    row = next(
        line for line in _MD_TEXT.splitlines()
        if line.startswith("| PQ-HITL-03.1 /")
    )
    assert "| IN_PROGRESS |" in row
    changed = _MD_TEXT.replace(row, row.replace("| IN_PROGRESS |", "| IN_PROGRES |"))
    problems = c.validate_work_package_mirror(doc, changed)
    assert any("PQ-HITL-03.1" in p and "status_vocabulary" in p for p in problems), problems


def test_atomic_work_package_role_drift_fails() -> None:
    row = next(
        line for line in _MD_TEXT.splitlines()
        if line.startswith("| PQ-HITL-04.4 /")
    )
    assert "implementation_lead · M · P1" in row
    changed = _MD_TEXT.replace(
        row, row.replace("implementation_lead · M · P1", "qa · M · P1")
    )
    problems = c.validate_work_package_mirror(c.load_yaml(), changed)
    assert any("PQ-HITL-04.4" in p and "role" in p for p in problems), problems


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
    # Value-agnostic: drop the whole `adr.ADR-024.realization=<anything>` line so this test
    # cannot rot when the row's status legitimately changes (it was pinned to DESIGNED and
    # silently became a no-op when ADR-024 moved to WIRED).
    mutated = re.sub(r"^adr\.ADR-024\.realization=.*\n", "", _MD_TEXT, flags=re.MULTILINE)
    assert mutated != _MD_TEXT, "the canonical key must exist before we can test its removal"
    problems = _compare_with_mutated_md(mutated)
    assert any("MD missing" in p and "adr.ADR-024.realization" in p for p in problems), problems


def test_new_architecture_adrs_are_parity_checked() -> None:
    """ADR-026..028 lifecycle state is machine-owned and must project exactly to Markdown."""
    canon = c.extract_canonical(c.load_yaml())
    md = c.parse_md_block(_MD_TEXT)
    expected = {
        "ADR-026": ("Accepted", "WIRED", "NONE", "NONE"),
        "ADR-027": ("Accepted", "WIRED", "NONE", "NONE"),
        "ADR-028": ("Accepted", "SCAFFOLDED", "NONE", "NONE"),
    }
    for adr, (design, realization, deployment, prod_validation) in expected.items():
        values = {
            f"adr.{adr}.design": design,
            f"adr.{adr}.realization": realization,
            f"adr.{adr}.deployment": deployment,
            f"adr.{adr}.prod_validation": prod_validation,
        }
        for key, value in values.items():
            assert canon[key] == value
            assert md[key] == value


def test_adr_design_status_md_drift_is_detected() -> None:
    mutated = _MD_TEXT.replace(
        "adr.ADR-026.design=Accepted",
        "adr.ADR-026.design=Proposed",
    )
    problems = _compare_with_mutated_md(mutated)
    assert any("VALUE DRIFT" in p and "adr.ADR-026.design" in p for p in problems), problems


def test_new_architecture_adr_md_drift_is_detected() -> None:
    mutated = _MD_TEXT.replace(
        "adr.ADR-026.realization=WIRED",
        "adr.ADR-026.realization=DEPLOYED",
    )
    problems = _compare_with_mutated_md(mutated)
    assert any("VALUE DRIFT" in p and "adr.ADR-026.realization" in p for p in problems), problems


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
        "P0b-L4-4": "DONE",
        "P0b-L4-5": "DONE",
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


def _residual(doc: dict, rid: str) -> dict:
    return next(r for r in doc["p0b_vertical_contract"]["residuals"] if r["id"] == rid)


def _make_blocking(res: dict, blocks: str = "P0b-L4-5") -> dict:
    """Turn a residual into a BLOCKING one so the BLOCKING rules can be exercised."""
    res["blocking"] = "BLOCKING"
    res["blocks"] = blocks
    return res


def test_residuals_are_registered_and_parity_checked() -> None:
    """Positive: both residuals, their statuses and their blocking mode are canonical."""
    canon = c.extract_canonical(c.load_yaml())
    md = c.parse_md_block(_MD_TEXT)
    r1, r2 = "P0b-R1-EVIDENCE-GRANULARITY", "P0b-R2-CROSS-DATA-CONTRACT"

    assert canon["p0b.residual_ids"] == f"{r1},{r2}"
    assert canon[f"p0b.residual.{r1}.status"] == "RESOLVED"
    assert canon[f"p0b.residual.{r1}.blocking"] == "NON_BLOCKING"
    assert canon[f"p0b.residual.{r2}.status"] == "PLANNED"
    assert canon[f"p0b.residual.{r2}.blocking"] == "NON_BLOCKING"

    for key in (
        "p0b.residual_ids",
        f"p0b.residual.{r1}.status",
        f"p0b.residual.{r1}.blocking",
        f"p0b.residual.{r2}.status",
        f"p0b.residual.{r2}.blocking",
    ):
        assert md[key] == canon[key], f"MD/YAML drift on {key}"


def test_non_blocking_residual_emits_no_blocks_key() -> None:
    """Positive: a NON_BLOCKING residual has no blocker line to contradict."""
    canon = c.extract_canonical(c.load_yaml())
    for rid in ("P0b-R1-EVIDENCE-GRANULARITY", "P0b-R2-CROSS-DATA-CONTRACT"):
        assert f"p0b.residual.{rid}.blocks" not in canon
    assert "p0b.residual.P0b-R2-CROSS-DATA-CONTRACT.blocks" not in _MD_TEXT


def test_blocking_residual_emits_the_blocks_key() -> None:
    """Positive: a BLOCKING residual still publishes which slice it gates."""
    doc = c.load_yaml()
    _make_blocking(_residual(doc, "P0b-R2-CROSS-DATA-CONTRACT"))
    canon = c.extract_canonical(doc)
    assert canon["p0b.residual.P0b-R2-CROSS-DATA-CONTRACT.blocking"] == "BLOCKING"
    assert canon["p0b.residual.P0b-R2-CROSS-DATA-CONTRACT.blocks"] == "P0b-L4-5"


def test_r2_is_registered_as_planned_and_non_blocking() -> None:
    """Positive: R2 exists as real future work that is NOT a P0b exit gate."""
    res = _residual(c.load_yaml(), "P0b-R2-CROSS-DATA-CONTRACT")
    assert res["status"] == "PLANNED"
    assert res["priority"] == "P1"
    assert res["blocking"] == "NON_BLOCKING"
    assert "blocks" not in res


def test_r1_records_its_resolution_without_erasing_history() -> None:
    """Positive: R1 is RESOLVED, evidences the merge, and keeps the dated blocking truth."""
    res = _residual(c.load_yaml(), "P0b-R1-EVIDENCE-GRANULARITY")
    assert res["status"] == "RESOLVED"
    assert res["blocking"] == "NON_BLOCKING"
    assert "6d3a19e41f169d974e9a0d4ea73d1aec7c0bc4cc" in res["resolved_by"]
    assert "DID block P0b-L4-5" in res["historical_truth"]


def test_l4_5_is_done_only_with_accepted_p0b_qualification() -> None:
    """Current control truth: L4-5 is DONE because P0b has an accepted PASS bundle."""
    doc = c.load_yaml()
    slice_45 = c._p0b_slice(doc, "P0b-L4-5")
    lane = doc["qualification_control"]["lanes"]["P0b"]
    assert slice_45["slice_status"] == "DONE"
    assert lane["qualification_status"] == "PASS"
    assert lane["bundle_ref"]
    assert lane["bundle_sha256"]
    assert "blocked_by" not in slice_45


def test_resolved_residual_is_not_the_current_blocker_and_p0b_has_no_next_slice() -> None:
    """ANTI-DRIFT: completed P0b has no fabricated follow-on slice."""
    doc = c.load_yaml()
    p0b = doc["p0b_vertical_contract"]
    r1 = _residual(doc, "P0b-R1-EVIDENCE-GRANULARITY")

    assert r1["status"] == "RESOLVED", "fixture drifted: this test guards the RESOLVED state"
    for res in p0b["residuals"]:
        if res["status"] == "RESOLVED":
            assert res["blocking"] == "NON_BLOCKING", res["id"]
            assert "blocks" not in res, res["id"]
    assert not [
        res["id"] for res in p0b["residuals"] if res.get("blocks") == "P0b-L4-5"
    ], "P0b-L4-5 is still gated by a residual"

    assert p0b["next_slice"] is None
    assert all(sl["slice_status"] == "DONE" for sl in p0b["slices"])


def test_next_slice_is_parity_checked() -> None:
    """Terminal P0b next_slice=None is represented canonically as NONE."""
    canon = c.extract_canonical(c.load_yaml())
    assert canon["p0b.next_slice"] == "NONE"


def test_missing_next_slice_detected() -> None:
    """Negative: terminal state is explicit null, not an omitted authority field."""
    doc = c.load_yaml()
    del doc["p0b_vertical_contract"]["next_slice"]
    problems = c.validate_enums(doc)
    assert any("missing 'next_slice' field" in p for p in problems), problems


def test_null_next_slice_rejected_when_work_remains() -> None:
    """Negative: null is legal only for a fully completed P0b slice set."""
    doc = c.load_yaml()
    c._p0b_slice(doc, "P0b-L4-5")["slice_status"] = "PARTIAL"
    doc["p0b_vertical_contract"]["next_slice"] = None
    problems = c.validate_enums(doc)
    assert any("may be null only when every P0b slice is DONE" in p for p in problems), problems


def test_unknown_next_slice_detected() -> None:
    """Negative: next_slice must name a real slice."""
    doc = c.load_yaml()
    doc["p0b_vertical_contract"]["next_slice"] = "P0b-L4-9"
    problems = c.validate_enums(doc)
    assert any("not a known P0b slice id" in p for p in problems), problems


def test_done_next_slice_detected() -> None:
    """Negative: a finished slice cannot be the next authorized action."""
    doc = c.load_yaml()
    doc["p0b_vertical_contract"]["next_slice"] = "P0b-L4-1"
    problems = c.validate_enums(doc)
    assert any("already DONE" in p for p in problems), problems


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


def test_missing_blocking_field_detected() -> None:
    """Negative: a residual with no 'blocking' must FAIL — the mode is never assumed."""
    doc = c.load_yaml()
    del _residual(doc, "P0b-R2-CROSS-DATA-CONTRACT")["blocking"]
    problems = c.validate_enums(doc)
    assert any("missing 'blocking'" in p for p in problems), problems


def test_invalid_blocking_value_detected() -> None:
    """Negative: a 'blocking' value outside residual_blocking must FAIL."""
    doc = c.load_yaml()
    _residual(doc, "P0b-R2-CROSS-DATA-CONTRACT")["blocking"] = "SORT_OF"
    problems = c.validate_enums(doc)
    assert any("SORT_OF" in p for p in problems), problems


def test_non_blocking_residual_with_blocks_detected() -> None:
    """Negative: NON_BLOCKING + 'blocks' is a contradiction and must FAIL."""
    doc = c.load_yaml()
    _residual(doc, "P0b-R2-CROSS-DATA-CONTRACT")["blocks"] = "P0b-L4-5"
    problems = c.validate_enums(doc)
    assert any("must omit 'blocks'" in p for p in problems), problems


def test_non_blocking_residual_with_null_blocks_detected() -> None:
    """Negative: absent means absent — a null/empty 'blocks' still reads as an edge."""
    doc = c.load_yaml()
    _residual(doc, "P0b-R2-CROSS-DATA-CONTRACT")["blocks"] = None
    problems = c.validate_enums(doc)
    assert any("must omit 'blocks'" in p for p in problems), problems


def test_blocking_residual_without_blocks_detected() -> None:
    """Negative: BLOCKING with no 'blocks' must FAIL — it must name what it gates."""
    doc = c.load_yaml()
    _residual(doc, "P0b-R2-CROSS-DATA-CONTRACT")["blocking"] = "BLOCKING"
    problems = c.validate_enums(doc)
    assert any("BLOCKING residual is missing 'blocks'" in p for p in problems), problems


def test_residual_blocking_contradiction_detected() -> None:
    """Negative: a BLOCKING residual whose target slice is not BLOCKED must FAIL."""
    doc = c.load_yaml()
    _make_blocking(_residual(doc, "P0b-R2-CROSS-DATA-CONTRACT"))
    for sl in doc["p0b_vertical_contract"]["slices"]:
        if sl["id"] == "P0b-L4-5":
            sl["slice_status"] = "NOT_STARTED"
    problems = c.validate_enums(doc)
    assert any("not BLOCKED" in p for p in problems), problems


def test_residual_blocking_unknown_slice_detected() -> None:
    """Negative: a BLOCKING residual naming a slice id that does not exist must FAIL."""
    doc = c.load_yaml()
    _make_blocking(_residual(doc, "P0b-R2-CROSS-DATA-CONTRACT"), blocks="P0b-L4-9")
    problems = c.validate_enums(doc)
    assert any("not a known P0b slice id" in p for p in problems), problems


def test_md_blocking_contradiction_detected() -> None:
    """Negative: an MD '.blocking' that disagrees with the YAML must FAIL."""
    key = "p0b.residual.P0b-R2-CROSS-DATA-CONTRACT.blocking"
    broken = _MD_TEXT.replace(f"{key}=NON_BLOCKING", f"{key}=BLOCKING")
    assert broken != _MD_TEXT, "fixture did not mutate — the canonical key moved"
    canon = c.extract_canonical(c.load_yaml())
    md = c.parse_md_block(broken)
    assert md[key] != canon[key]



# ── Schema v8 Product Qualification control ──────────────────────────────────




def _demote_p0b_fixture(doc: dict) -> None:
    """Return P0b to the pre-promotion state for isolated guard tests."""
    row = doc["qualification_control"]["lanes"]["P0b"]
    row["qualification_status"] = "REQUIRED"
    row["bundle_ref"] = None
    row["bundle_sha256"] = None
    c._adr_row(doc, "ADR-024")["prod_validation_status"] = "NONE"
    c._p0b_slice(doc, "P0b-L4-5")["slice_status"] = "PARTIAL"
    doc["p0b_vertical_contract"]["next_slice"] = "P0b-L4-5"

def _attach_stub_bundle(
    doc: dict,
    lane: str,
    root: Path,
    *,
    verdict: str = "PASS",
) -> Path:
    if lane != "P0b":
        _demote_p0b_fixture(doc)
    evidence_dir = root / "evidence" / "product-qualification"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    path = evidence_dir / f"{lane.lower()}-qualification.yaml"
    payload = f"capability_id: {lane}\nvalidator_verdict: {verdict}\n"
    path.write_text(payload, encoding="utf-8")
    row = doc["qualification_control"]["lanes"][lane]
    row["qualification_status"] = verdict
    row["bundle_ref"] = str(path.relative_to(root)).replace("\\", "/")
    row["bundle_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return path


def _stub_validator(_path: Path) -> list[str]:
    return []


def _stub_loader_for(lane: str, verdict: str = "PASS"):
    return lambda _path: {"capability_id": lane, "validator_verdict": verdict}


def test_human_projection_current_sections_reflect_accepted_p0b_without_rewriting_history() -> None:
    """Current narrative surfaces must not contradict the canonical P0b PASS state."""
    assert "### P0b — Single-document Health — PROD_VALIDATED / CLOSED" in _MD_TEXT
    assert "| ADR-024 Single-document Activation | Accepted | WIRED | **PARTIAL** | **PROD_VALIDATED** |" in _MD_TEXT
    assert "The #715/#733 qualification mechanism was exercised successfully by A1 #55 and A2 #56" in _MD_TEXT
    assert "**This subsection is historical and is superseded by §2.5" in _MD_TEXT
    assert "**This is a historical 2026-10-03 revalidation;" in _MD_TEXT
    assert "The bounded P0b single-document Health wedge passed production run #56; broader ADR-018" in _MD_TEXT
    assert "L4-1..L4-5 are DONE and the bounded P0b production done-definition passed" in _MD_TEXT
    assert "## 6. P0b vertical contract — accepted production baseline" in _MD_TEXT
    assert "**`L4-5` DONE**" in _MD_TEXT
    assert "revalidated 2026-10-04" in _ARCH_BASELINE_TEXT
    assert "A1 #55 and A2 #56" in _ARCH_BASELINE_TEXT
    assert "`#715` and `#792` are closed" in _ARCH_BASELINE_TEXT
    assert "P0c temporal/change and P0d Current State remain **not production-validated**" in _ARCH_BASELINE_TEXT


def test_schema_v8_current_qualification_control_is_valid_with_p0b_promoted() -> None:
    doc = c.load_yaml()
    assert doc["schema_version"] == 8
    assert c.validate_enums(doc) == []
    assert c.validate_qualification_control(doc) == []

    p0b = doc["qualification_control"]["lanes"]["P0b"]
    assert p0b["qualification_status"] == "PASS"
    assert p0b["bundle_ref"] == "evidence/product-qualification/p0b-prod-gh-37196092728-1.yaml"
    assert p0b["bundle_sha256"] == "d6031d454ac40f30a84a1b9c30f4f5d97ef285d7eb9e8d047a0af97148f6281b"
    assert c._adr_row(doc, "ADR-024")["prod_validation_status"] == "PROD_VALIDATED"
    assert c._p0b_slice(doc, "P0b-L4-5")["slice_status"] == "DONE"

    for lane in ("P0c", "P0d"):
        row = doc["qualification_control"]["lanes"][lane]
        assert row["qualification_status"] == "REQUIRED"
        assert row["bundle_ref"] is None
        assert row["bundle_sha256"] is None


def test_p0b_reconciliation_runtime_binding_is_bound_to_accepted_bundle() -> None:
    doc = c.load_yaml()
    doc["reconciliation_delta_2026_10_04_p0b"]["runtime_binding"]["backend"]["commit_sha"] = "0" * 40
    problems = c.validate_qualification_control(doc)
    assert any(
        "runtime_binding.backend.commit_sha must match accepted bundle" in problem
        for problem in problems
    ), problems


def test_p0b_reconciliation_bundle_record_is_bound_to_lane() -> None:
    doc = c.load_yaml()
    doc["reconciliation_delta_2026_10_04_p0b"]["qualification_bundle"]["sha256"] = "0" * 64
    problems = c.validate_qualification_control(doc)
    assert any(
        "qualification_bundle.sha256 must match qualification[P0b].bundle_sha256" in problem
        for problem in problems
    ), problems


def test_qualification_schema_version_rejects_boolean_true() -> None:
    doc = c.load_yaml()
    doc["qualification_control"]["schema_version"] = True
    problems = c.validate_qualification_control(doc)
    assert any("schema_version must be integer 1" in problem for problem in problems)


def test_qualification_bundle_ref_rejects_symlink() -> None:
    if sys.platform == "win32":
        return
    doc = c.load_yaml()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        evidence_dir = root / "evidence" / "product-qualification"
        evidence_dir.mkdir(parents=True)
        target = evidence_dir / "target.yaml"
        target.write_text("capability_id: P0b\nvalidator_verdict: PASS\n", encoding="utf-8")
        link = evidence_dir / "p0b-qualification.yaml"
        link.symlink_to(target.name)
        row = doc["qualification_control"]["lanes"]["P0b"]
        row["qualification_status"] = "PASS"
        row["bundle_ref"] = "evidence/product-qualification/p0b-qualification.yaml"
        row["bundle_sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
        problems = c.validate_qualification_control(
            doc,
            root=root,
            bundle_validator=_stub_validator,
            bundle_loader=_stub_loader_for("P0b"),
        )
    assert any("must not be a symlink" in problem for problem in problems)


def test_malformed_qualification_lane_and_status_types_fail_closed() -> None:
    doc = c.load_yaml()
    doc["qualification_control"]["lanes"]["P0b"] = []
    problems = c.validate_qualification_control(doc)
    assert any("lane must be a mapping" in problem for problem in problems)

    doc = c.load_yaml()
    doc["qualification_control"]["lanes"]["P0b"]["qualification_status"] = []
    problems = c.validate_qualification_control(doc)
    assert any("invalid qualification_status" in problem for problem in problems)


def test_qualification_evidence_directory_rejects_symlink() -> None:
    if sys.platform == "win32":
        return
    doc = c.load_yaml()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        external = root / "external"
        external.mkdir()
        evidence_parent = root / "evidence"
        evidence_parent.mkdir()
        (evidence_parent / "product-qualification").symlink_to(external, target_is_directory=True)
        problems = c.validate_qualification_control(doc, root=root)
    assert any("evidence_directory path components must not be symlinks" in problem for problem in problems)


def test_invalid_qualification_status_is_rejected() -> None:
    doc = c.load_yaml()
    doc["qualification_control"]["lanes"]["P0b"]["qualification_status"] = "AUTO_PASS"
    problems = c.validate_enums(doc) + c.validate_qualification_control(doc)
    assert any("AUTO_PASS" in problem or "invalid qualification_status" in problem for problem in problems)


def test_shadow_lifecycle_target_records_are_rejected() -> None:
    # ADR family collision: target id ADR-024 must resolve to one canonical row only.
    doc = c.load_yaml()
    shadow_adr = dict(c._adr_row(doc, "ADR-024"))
    shadow_adr["adr"] = "ADR-024-shadow"
    shadow_adr["prod_validation_status"] = "PROD_VALIDATED"
    doc["adr_realization"].append(shadow_adr)
    problems = c.validate_qualification_control(doc)
    assert any(
        "qualification ADR target ADR-024 must resolve exactly once" in problem
        for problem in problems
    )

    # Exact P0b slice duplicate must also fail closed.
    doc = c.load_yaml()
    shadow_slice = dict(c._p0b_slice(doc, "P0b-L4-5"))
    shadow_slice["slice_status"] = "DONE"
    doc["p0b_vertical_contract"]["slices"].append(shadow_slice)
    problems = c.validate_qualification_control(doc)
    assert any(
        "qualification P0b slice target P0b-L4-5 must resolve exactly once" in problem
        for problem in problems
    )

    # Exact WBS duplicate cannot hide a promoted P0d current_state subtrack.
    doc = c.load_yaml()
    source_wbs = c._wbs_row(doc, "PWBS-EXEC-REPORTING")
    shadow_wbs = {
        **source_wbs,
        "subtracks": {
            "current_state": {
                "realization_status": "WIRED",
                "deployment_status": "NONE",
                "prod_validation_status": "PROD_VALIDATED",
            },
            "executive_portfolio": dict(source_wbs["subtracks"]["executive_portfolio"]),
        },
    }
    doc["product_wbs"].append(shadow_wbs)
    problems = c.validate_qualification_control(doc)
    assert any(
        "qualification WBS target PWBS-EXEC-REPORTING must resolve exactly once" in problem
        for problem in problems
    )


def test_qualification_evidence_parent_symlink_is_rejected() -> None:
    if sys.platform == "win32":
        return
    doc = c.load_yaml()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        external = root / "external"
        (external / "product-qualification").mkdir(parents=True)
        (root / "evidence").symlink_to(external, target_is_directory=True)
        problems = c.validate_qualification_control(doc, root=root)
    assert any("path components must not be symlinks" in problem for problem in problems)


def test_run_reports_malformed_lane_without_traceback() -> None:
    doc = c.load_yaml()
    doc["qualification_control"]["lanes"]["P0b"] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        yaml_path = root / "validation" / "product" / "control.yaml"
        md_path = root / "docs" / "product" / "control.md"
        yaml_path.parent.mkdir(parents=True)
        md_path.parent.mkdir(parents=True)
        yaml_path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
        md_path.write_text(_MD_TEXT, encoding="utf-8")
        problems = c.run(yaml_path=yaml_path, md_path=md_path)
    assert any("qualification[P0b]" in problem for problem in problems)
    assert any(
        "qualification.P0b.status" in problem
        for problem in problems
    )


def test_capability_lifecycle_mapping_is_fixed_not_self_authored() -> None:
    doc = c.load_yaml()
    doc["qualification_control"]["lanes"]["P0b"]["lifecycle_targets"] = [
        {
            "kind": "adr",
            "id": "ADR-018",
            "field": "prod_validation_status",
            "promote_to": "PROD_VALIDATED",
        }
    ]
    problems = c.validate_qualification_control(doc)
    assert any("canonical capability mapping" in problem for problem in problems)


def test_lifecycle_promotion_without_pass_bundle_fails_closed() -> None:
    doc = c.load_yaml()
    _demote_p0b_fixture(doc)
    c._adr_row(doc, "ADR-024")["prod_validation_status"] = "PROD_VALIDATED"
    c._p0b_slice(doc, "P0b-L4-5")["slice_status"] = "DONE"
    problems = c.validate_qualification_control(doc)
    assert any("qualification_status=PASS" in problem for problem in problems)
    assert any("validated PASS Phase-A bundle" in problem for problem in problems)


def test_valid_pass_bundle_does_not_auto_promote_lifecycle() -> None:
    doc = c.load_yaml()
    _demote_p0b_fixture(doc)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _attach_stub_bundle(doc, "P0b", root)
        problems = c.validate_qualification_control(
            doc,
            root=root,
            bundle_validator=_stub_validator,
            bundle_loader=_stub_loader_for("P0b"),
        )
    assert problems == []
    assert c._adr_row(doc, "ADR-024")["prod_validation_status"] == "NONE"
    assert c._p0b_slice(doc, "P0b-L4-5")["slice_status"] == "PARTIAL"


def test_valid_pass_bundle_can_guard_explicit_atomic_p0b_promotion() -> None:
    doc = c.load_yaml()
    _demote_p0b_fixture(doc)
    c._adr_row(doc, "ADR-024")["prod_validation_status"] = "PROD_VALIDATED"
    c._p0b_slice(doc, "P0b-L4-5")["slice_status"] = "DONE"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _attach_stub_bundle(doc, "P0b", root)
        problems = c.validate_qualification_control(
            doc,
            root=root,
            bundle_validator=_stub_validator,
            bundle_loader=_stub_loader_for("P0b"),
        )
    assert problems == []


def test_partial_p0b_promotion_is_rejected() -> None:
    doc = c.load_yaml()
    _demote_p0b_fixture(doc)
    c._adr_row(doc, "ADR-024")["prod_validation_status"] = "PROD_VALIDATED"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _attach_stub_bundle(doc, "P0b", root)
        problems = c.validate_qualification_control(
            doc,
            root=root,
            bundle_validator=_stub_validator,
            bundle_loader=_stub_loader_for("P0b"),
        )
    assert any("must promote atomically" in problem for problem in problems)


def test_bundle_digest_mismatch_is_rejected() -> None:
    doc = c.load_yaml()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _attach_stub_bundle(doc, "P0c", root)
        doc["qualification_control"]["lanes"]["P0c"]["bundle_sha256"] = "0" * 64
        problems = c.validate_qualification_control(
            doc,
            root=root,
            bundle_validator=_stub_validator,
            bundle_loader=_stub_loader_for("P0c"),
        )
    assert any("bundle_sha256 does not match" in problem for problem in problems)


def test_bundle_capability_mismatch_is_rejected() -> None:
    doc = c.load_yaml()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _attach_stub_bundle(doc, "P0c", root)
        problems = c.validate_qualification_control(
            doc,
            root=root,
            bundle_validator=_stub_validator,
            bundle_loader=_stub_loader_for("P0d"),
        )
    assert any("does not match P0c" in problem for problem in problems)


def test_invalid_phase_a_bundle_cannot_promote_even_with_control_pass() -> None:
    doc = c.load_yaml()
    c._adr_row(doc, "ADR-015")["prod_validation_status"] = "PROD_VALIDATED"
    c._adr_row(doc, "ADR-016")["prod_validation_status"] = "PROD_VALIDATED"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _attach_stub_bundle(doc, "P0c", root)
        problems = c.validate_qualification_control(
            doc,
            root=root,
            bundle_validator=lambda _path: ["required assertion missing"],
            bundle_loader=_stub_loader_for("P0c"),
        )
    assert any("Phase-A bundle invalid" in problem for problem in problems)
    assert any("validated PASS Phase-A bundle" in problem for problem in problems)


def test_p0d_promotes_current_state_without_promoting_executive_portfolio() -> None:
    doc = c.load_yaml()
    reporting = c._wbs_row(doc, "PWBS-EXEC-REPORTING")["subtracks"]
    reporting["current_state"]["prod_validation_status"] = "PROD_VALIDATED"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _attach_stub_bundle(doc, "P0d", root)
        problems = c.validate_qualification_control(
            doc,
            root=root,
            bundle_validator=_stub_validator,
            bundle_loader=_stub_loader_for("P0d"),
        )
    assert problems == []
    assert reporting["executive_portfolio"]["prod_validation_status"] == "NONE"


def test_qualification_compact_values_are_parity_checked() -> None:
    canon = c.extract_canonical(c.load_yaml())
    md = c.parse_md_block(_MD_TEXT)

    assert canon["qualification.P0b.status"] == "PASS"
    assert canon["qualification.P0b.bundle_ref"] == "evidence/product-qualification/p0b-prod-gh-37196092728-1.yaml"
    assert canon["qualification.P0b.evidence_digest"] == "d6031d454ac40f30"
    for key in (
        "qualification.P0b.status",
        "qualification.P0b.bundle_ref",
        "qualification.P0b.evidence_digest",
        "qualification.P0b.targets_digest",
    ):
        assert md[key] == canon[key]

    for lane in ("P0c", "P0d"):
        assert canon[f"qualification.{lane}.status"] == "REQUIRED"
        assert canon[f"qualification.{lane}.bundle_ref"] == "NONE"
        assert canon[f"qualification.{lane}.evidence_digest"] == "NONE"
        assert md[f"qualification.{lane}.status"] == "REQUIRED"
        assert md[f"qualification.{lane}.targets_digest"] == canon[f"qualification.{lane}.targets_digest"]


def test_qualification_md_status_drift_is_detected() -> None:
    mutated = _MD_TEXT.replace(
        "qualification.P0b.status=PASS",
        "qualification.P0b.status=REQUIRED",
    )
    problems = _compare_with_mutated_md(mutated)
    assert any("qualification.P0b.status" in problem and "VALUE DRIFT" in problem for problem in problems)


def test_p0d_current_state_lifecycle_is_parity_checked() -> None:
    canon = c.extract_canonical(c.load_yaml())
    md = c.parse_md_block(_MD_TEXT)
    expected = {
        "wbs.PWBS-EXEC-REPORTING.current_state.realization": "WIRED",
        "wbs.PWBS-EXEC-REPORTING.current_state.deployment": "NONE",
        "wbs.PWBS-EXEC-REPORTING.current_state.prod_validation": "NONE",
    }
    for key, value in expected.items():
        assert canon[key] == value
        assert md[key] == value



# ── Schema v6 Project Controls critical parity ────────────────────────────────


def test_project_controls_priority_is_parity_checked() -> None:
    """#619: P1 priority is canonical machine truth, not unguarded prose."""
    canon = c.extract_canonical(c.load_yaml())
    md = c.parse_md_block(_MD_TEXT)
    key = "wbs.PWBS-PROJECT-CONTROLS.priority"
    assert canon.get(key) == "P1", canon
    assert md.get(key) == canon.get(key), (md.get(key), canon.get(key))


def test_adr025_lifecycle_is_parity_checked() -> None:
    """#619: ADR-025 lifecycle cannot drift between YAML and human MASTER."""
    canon = c.extract_canonical(c.load_yaml())
    md = c.parse_md_block(_MD_TEXT)
    expected = {
        "adr.ADR-025.realization": "PARTIAL",
        "adr.ADR-025.deployment": "NONE",
        "adr.ADR-025.prod_validation": "NONE",
    }
    for key, value in expected.items():
        assert canon.get(key) == value, (key, canon.get(key))
        assert md.get(key) == value, (key, md.get(key))


def test_project_controls_invariant_is_parity_checked() -> None:
    """#619: one-project/one-WBS invariant is guarded as an exact canonical value."""
    canon = c.extract_canonical(c.load_yaml())
    md = c.parse_md_block(_MD_TEXT)
    key = "project_controls.invariant"
    expected = "one_project_one_canonical_hierarchical_wbs"
    assert canon.get(key) == expected, canon
    assert md.get(key) == expected, (md.get(key), expected)


def test_canonical_dimensions_are_parity_checked() -> None:
    """#619: the shared six-dimensional taxonomy cannot silently diverge."""
    canon = c.extract_canonical(c.load_yaml())
    md = c.parse_md_block(_MD_TEXT)
    key = "product_semantics.canonical_dimensions"
    expected = "SCOPE,BUDGET,TIME,TECHNICAL,LEGAL,QUALITY"
    assert canon.get(key) == expected, canon
    assert md.get(key) == expected, (md.get(key), expected)


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
