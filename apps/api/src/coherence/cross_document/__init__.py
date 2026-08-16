"""
First-class cross-document comparators (ADR-023 Phase 1b).

Genuine value-vs-value comparison **across** documents — NOT aggregation of
per-document findings. Each comparator takes assembled project-level aggregates
(`ProjectCrossDocInputs`) and emits a typed `CrossDocFinding` carrying the two
compared values, their delta/direction, and the materiality ratio — the same
`compared_values`/`delta`/`direction` shape the conflict ledger already understands,
so a finding flows into the canonical scorer via the existing signal → candidate →
ConflictService → CategoryAggregator path.

Pure and side-effect-free. Lighting up LIVE pilot findings needs only the assembly
step (extract each total per document and populate `ProjectCrossDocInputs`) — that
wiring is a separate increment.
"""
from __future__ import annotations

from src.coherence.cross_document.comparators import (
    RULE_BOM_VS_BUDGET,
    RULE_CONTRACT_VS_BUDGET,
    RULE_WBS_VS_BUDGET,
    bom_vs_budget_total,
    compare_values,
    contract_vs_budget_total,
    run_numeric_comparators,
    wbs_vs_budget_total,
)
from src.coherence.cross_document.findings import CrossDocFinding
from src.coherence.cross_document.inputs import ProjectCrossDocInputs
from src.coherence.cross_document.signal_adapter import to_finding_signal

__all__ = [
    "RULE_BOM_VS_BUDGET",
    "RULE_CONTRACT_VS_BUDGET",
    "RULE_WBS_VS_BUDGET",
    "CrossDocFinding",
    "ProjectCrossDocInputs",
    "bom_vs_budget_total",
    "compare_values",
    "contract_vs_budget_total",
    "run_numeric_comparators",
    "to_finding_signal",
    "wbs_vs_budget_total",
]
