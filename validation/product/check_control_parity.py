#!/usr/bin/env python3
"""Deterministic parity guard for the C2Pro product-control plane (control integrity, J).

The YAML (``c2pro-master-product-control-v1.yaml``) is the machine source of truth;
the Markdown (``docs/product/00-c2pro-master-product-control-v1.md``) is a human
projection of it. This checker asserts that every *critical* fact appears in BOTH
files (case-insensitive substring), so the two controls cannot silently diverge.

Pure standard library (no PyYAML) — safe to run anywhere, including CI/pre-merge.

Usage:
    python validation/product/check_control_parity.py
Exit code 0 = parity holds; 1 = drift (prints the missing facts).
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_YAML = _ROOT / "validation" / "product" / "c2pro-master-product-control-v1.yaml"
_MD = _ROOT / "docs" / "product" / "00-c2pro-master-product-control-v1.md"

# (label, needle) — each needle MUST appear (case-insensitive) in BOTH files.
CRITICAL_FACTS: list[tuple[str, str]] = [
    ("repository_main_sha", "9c48f4f94d0a5719561916b956f8a78b2129a250"),
    ("deployed_runtime_sha=UNVERIFIED", "unverified"),
    ("reliability_operability_baseline=CLOSED", "reliability"),
    ("product_value_delivered=false", "product_value_delivered"),
    ("north_star.full_product", "continuous, evidence-backed project & procurement intelligence"),
    ("north_star.current_product_wedge", "single-document health activation"),
    ("ADR-018 not prod-validated", "not_validated"),
    ("ADR-024 designed (P0b)", "single-document activation"),
    ("coherence v1-only in prod", "coherence-v1"),
    ("coherence cutover=NO", "cutover"),
    ("unmapped_open_legacy_items=0", "unmapped_open_legacy_items"),
    ("INV-UX null != 0%", "insufficient evidence"),
]


def _load(p: Path) -> str:
    if not p.exists():
        print(f"PARITY FAIL: missing control file {p}", file=sys.stderr)
        sys.exit(1)
    return p.read_text(encoding="utf-8").lower()


def main() -> int:
    yaml_text = _load(_YAML)
    md_text = _load(_MD)
    missing: list[str] = []
    for label, needle in CRITICAL_FACTS:
        n = needle.lower()
        if n not in yaml_text:
            missing.append(f"YAML missing [{label}]: {needle!r}")
        if n not in md_text:
            missing.append(f"MD   missing [{label}]: {needle!r}")
    if missing:
        print("PARITY FAIL — MD/YAML control drift:", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        return 1
    print(f"PARITY OK — {len(CRITICAL_FACTS)} critical facts present in both control files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
