"""
Pure cross-document comparator functions (ADR-023 Phase 1b).

Each compares two assembled aggregates and emits a `CrossDocFinding` when the
relative discrepancy exceeds a tolerance (below it is rounding/noise). Materiality
is `|delta| / max(|left|, |right|)`; downstream severity (critical vs high) is derived
from that ratio by the existing conflict service (`CRITICAL_MISMATCH_RATIO`), so these
comparators intentionally do NOT hard-code severity.

Refers to Suite ID: TS-UD-COH-XDOC-COMPARATORS-001.
"""
from __future__ import annotations

from src.coherence.cross_document.findings import CrossDocFinding
from src.coherence.cross_document.inputs import ProjectCrossDocInputs
from src.coherence.models import CoherenceCategory

# Below this relative difference a mismatch is rounding/noise, not a discrepancy.
DEFAULT_TOLERANCE = 0.01

RULE_CONTRACT_VS_BUDGET = "DET-CRS-CONBUD"  # contract price ↔ budget total
RULE_WBS_VS_BUDGET = "DET-CRS-WBSBUD"  # WBS package sum ↔ budget total
RULE_BOM_VS_BUDGET = "DET-CRS-BOMBUD"  # BOM line sum ↔ budget total


def compare_values(
    left_key: str,
    left_value: float | None,
    right_key: str,
    right_value: float | None,
    *,
    rule_id: str,
    category: CoherenceCategory,
    tolerance: float = DEFAULT_TOLERANCE,
) -> CrossDocFinding | None:
    """Compare two values; emit a finding only if the relative discrepancy is material.

    Returns None when either value is absent, both are zero, or the relative
    difference is within `tolerance`.
    """
    if left_value is None or right_value is None:
        return None
    denom = max(abs(left_value), abs(right_value))
    if denom == 0.0:
        return None
    delta = float(left_value) - float(right_value)
    ratio = abs(delta) / denom
    if ratio <= tolerance:
        return None
    direction = "exceeds" if delta > 0 else "below"
    return CrossDocFinding(
        rule_id=rule_id,
        category=category,
        left_key=left_key,
        left_value=float(left_value),
        right_key=right_key,
        right_value=float(right_value),
        delta=delta,
        direction=direction,
        materiality_ratio=ratio,
        summary=(
            f"{left_key} ({left_value:,.0f}) {direction} {right_key} "
            f"({right_value:,.0f}) by {ratio:.1%}"
        ),
    )


def contract_vs_budget_total(
    inputs: ProjectCrossDocInputs, *, tolerance: float = DEFAULT_TOLERANCE
) -> CrossDocFinding | None:
    """Contract price ↔ stated budget total (the €1.6M-vs-€1.2M case)."""
    return compare_values(
        "contract_total",
        inputs.contract_total,
        "budget_total",
        inputs.budget_total,
        rule_id=RULE_CONTRACT_VS_BUDGET,
        category="BUDGET",
        tolerance=tolerance,
    )


def wbs_vs_budget_total(
    inputs: ProjectCrossDocInputs, *, tolerance: float = DEFAULT_TOLERANCE
) -> CrossDocFinding | None:
    """WBS work-package sum ↔ stated budget total."""
    return compare_values(
        "wbs_total",
        inputs.wbs_total,
        "budget_total",
        inputs.budget_total,
        rule_id=RULE_WBS_VS_BUDGET,
        category="BUDGET",
        tolerance=tolerance,
    )


def bom_vs_budget_total(
    inputs: ProjectCrossDocInputs, *, tolerance: float = DEFAULT_TOLERANCE
) -> CrossDocFinding | None:
    """BOM line-cost sum ↔ stated budget total."""
    return compare_values(
        "bom_total",
        inputs.bom_total,
        "budget_total",
        inputs.budget_total,
        rule_id=RULE_BOM_VS_BUDGET,
        category="BUDGET",
        tolerance=tolerance,
    )


def run_numeric_comparators(
    inputs: ProjectCrossDocInputs, *, tolerance: float = DEFAULT_TOLERANCE
) -> list[CrossDocFinding]:
    """Run every numeric cross-document comparator; return only material findings."""
    findings: list[CrossDocFinding] = []
    for comparator in (contract_vs_budget_total, wbs_vs_budget_total, bom_vs_budget_total):
        finding = comparator(inputs, tolerance=tolerance)
        if finding is not None:
            findings.append(finding)
    return findings


__all__ = [
    "DEFAULT_TOLERANCE",
    "RULE_BOM_VS_BUDGET",
    "RULE_CONTRACT_VS_BUDGET",
    "RULE_WBS_VS_BUDGET",
    "bom_vs_budget_total",
    "compare_values",
    "contract_vs_budget_total",
    "run_numeric_comparators",
    "wbs_vs_budget_total",
]
