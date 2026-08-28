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


def test_wbs_status_contradiction_detected() -> None:
    mutated = _MD_TEXT.replace("wbs.PWBS-OPS-TRUST=DEPLOYED", "wbs.PWBS-OPS-TRUST=NONE")
    problems = _compare_with_mutated_md(mutated)
    assert any("VALUE DRIFT" in p and "wbs.PWBS-OPS-TRUST" in p for p in problems), problems


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
