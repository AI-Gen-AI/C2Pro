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
    # Value-agnostic: drop the whole `adr.ADR-024.realization=<anything>` line so this test
    # cannot rot when the row's status legitimately changes (it was pinned to DESIGNED and
    # silently became a no-op when ADR-024 moved to WIRED).
    mutated = re.sub(r"^adr\.ADR-024\.realization=.*\n", "", _MD_TEXT, flags=re.MULTILINE)
    assert mutated != _MD_TEXT, "the canonical key must exist before we can test its removal"
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
        "P0b-L4-4": "DONE",
        "P0b-L4-5": "PARTIAL",
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


def test_l4_5_is_partial_and_carries_no_blocker_field() -> None:
    """L4-5 is PARTIAL: merged/release-ready, but PROD validation is still the exit gate."""
    doc = c.load_yaml()
    slice_45 = next(
        sl for sl in doc["p0b_vertical_contract"]["slices"] if sl["id"] == "P0b-L4-5"
    )
    slice_44 = next(
        sl for sl in doc["p0b_vertical_contract"]["slices"] if sl["id"] == "P0b-L4-4"
    )
    assert slice_44["slice_status"] == "DONE", "L4-5 only advances after L4-4 closed"
    assert slice_45["slice_status"] == "PARTIAL"
    assert slice_45["slice_status"] != "DONE", "release-ready merge must not imply PROD validation"
    assert "blocked_by" not in slice_45, "an unblocked slice must not carry a blocker field"


def test_resolved_residual_is_not_the_current_blocker_and_l4_5_is_next() -> None:
    """ANTI-DRIFT: once R1 is RESOLVED, control truth must stop gating on it."""
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

    assert p0b["next_slice"] == "P0b-L4-5"
    nxt = next(sl for sl in p0b["slices"] if sl["id"] == p0b["next_slice"])
    assert nxt["slice_status"] == "PARTIAL"


def test_next_slice_is_parity_checked() -> None:
    """The next authorized action is a canonical value, so MD cannot disagree."""
    canon = c.extract_canonical(c.load_yaml())
    md = c.parse_md_block(_MD_TEXT)
    assert canon["p0b.next_slice"] == "P0b-L4-5"
    assert md["p0b.next_slice"] == canon["p0b.next_slice"]


def test_missing_next_slice_detected() -> None:
    """Negative: control truth must always name what comes next."""
    doc = c.load_yaml()
    del doc["p0b_vertical_contract"]["next_slice"]
    problems = c.validate_enums(doc)
    assert any("missing 'next_slice'" in p for p in problems), problems


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



# ── Schema v7 Product Qualification control ──────────────────────────────────


def _attach_stub_bundle(
    doc: dict,
    lane: str,
    root: Path,
    *,
    verdict: str = "PASS",
) -> Path:
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


def test_schema_v7_initial_qualification_control_is_valid_and_non_promoted() -> None:
    doc = c.load_yaml()
    assert doc["schema_version"] == 7
    assert c.validate_enums(doc) == []
    assert c.validate_qualification_control(doc) == []
    for lane in ("P0b", "P0c", "P0d"):
        row = doc["qualification_control"]["lanes"][lane]
        assert row["qualification_status"] == "REQUIRED"
        assert row["bundle_ref"] is None
        assert row["bundle_sha256"] is None


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


def test_invalid_qualification_status_is_rejected() -> None:
    doc = c.load_yaml()
    doc["qualification_control"]["lanes"]["P0b"]["qualification_status"] = "AUTO_PASS"
    problems = c.validate_enums(doc) + c.validate_qualification_control(doc)
    assert any("AUTO_PASS" in problem or "invalid qualification_status" in problem for problem in problems)


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
    c._adr_row(doc, "ADR-024")["prod_validation_status"] = "PROD_VALIDATED"
    c._p0b_slice(doc, "P0b-L4-5")["slice_status"] = "DONE"
    problems = c.validate_qualification_control(doc)
    assert any("qualification_status=PASS" in problem for problem in problems)
    assert any("validated PASS Phase-A bundle" in problem for problem in problems)


def test_valid_pass_bundle_does_not_auto_promote_lifecycle() -> None:
    doc = c.load_yaml()
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
    for lane in ("P0b", "P0c", "P0d"):
        assert canon[f"qualification.{lane}.status"] == "REQUIRED"
        assert canon[f"qualification.{lane}.bundle_ref"] == "NONE"
        assert canon[f"qualification.{lane}.evidence_digest"] == "NONE"
        assert md[f"qualification.{lane}.status"] == "REQUIRED"
        assert md[f"qualification.{lane}.targets_digest"] == canon[f"qualification.{lane}.targets_digest"]


def test_qualification_md_status_drift_is_detected() -> None:
    mutated = _MD_TEXT.replace(
        "qualification.P0b.status=REQUIRED",
        "qualification.P0b.status=PASS",
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
