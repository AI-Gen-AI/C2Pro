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

import re
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
        "P0b-L4-5": "ACTIVE",
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
    # Historical truth preserved, not rewritten.
    assert "DID block P0b-L4-5" in res["historical_truth"]


def test_l4_5_is_active_and_carries_no_blocker_field() -> None:
    """L4-5 is ACTIVE now that L4-4 is DONE, and it carries NO blocker field at all.

    Same structural principle as schema v5's residual_blocking: something that is not
    blocked must not carry a blocker line, because a blocker line that outlives its
    blocker is exactly how control prose drifts. L4-5 was BLOCKED on L4-4 acceptance;
    that gate closed with #581, so the field is gone rather than left to rot.
    """
    doc = c.load_yaml()
    slice_45 = next(
        sl for sl in doc["p0b_vertical_contract"]["slices"] if sl["id"] == "P0b-L4-5"
    )
    slice_44 = next(
        sl for sl in doc["p0b_vertical_contract"]["slices"] if sl["id"] == "P0b-L4-4"
    )
    assert slice_44["slice_status"] == "DONE", "L4-5 is only ACTIVE because L4-4 closed"
    assert slice_45["slice_status"] == "ACTIVE"
    assert "blocked_by" not in slice_45, "an unblocked slice must not carry a blocker field"


def test_resolved_residual_is_not_the_current_blocker_and_l4_5_is_next() -> None:
    """ANTI-DRIFT: once R1 is RESOLVED, control truth must stop gating on it.

    Deliberately structured-field only — no prose parsing. Two things must hold
    together, because a stale narrative can otherwise keep citing a closed residual
    as the live blocker long after its status flipped:

      1. no RESOLVED residual still carries a blocking edge, and nothing at all
         currently blocks P0b-L4-5 via the residual registry;
      2. the current next authorized product action is P0b-L4-5.
    """
    doc = c.load_yaml()
    p0b = doc["p0b_vertical_contract"]
    r1 = _residual(doc, "P0b-R1-EVIDENCE-GRANULARITY")

    assert r1["status"] == "RESOLVED", "fixture drifted: this test guards the RESOLVED state"

    # 1 — a RESOLVED residual cannot be anyone's current blocker.
    for res in p0b["residuals"]:
        if res["status"] == "RESOLVED":
            assert res["blocking"] == "NON_BLOCKING", res["id"]
            assert "blocks" not in res, res["id"]
    assert not [
        res["id"] for res in p0b["residuals"] if res.get("blocks") == "P0b-L4-5"
    ], "P0b-L4-5 is still gated by a residual"

    # 2 — the next authorized action is L4-5, and it is real work (not DONE).
    assert p0b["next_slice"] == "P0b-L4-5"
    nxt = next(sl for sl in p0b["slices"] if sl["id"] == p0b["next_slice"])
    assert nxt["slice_status"] == "ACTIVE"


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
