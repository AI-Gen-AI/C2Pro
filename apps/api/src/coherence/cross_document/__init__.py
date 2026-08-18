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

from src.coherence.cross_document.assembly import (
    assemble_cross_doc_inputs,
    cross_document_signals,
)
from src.coherence.cross_document.comparators import (
    RULE_BOM_VS_BUDGET,
    RULE_BUDGET_EXCEEDS_CONTRACT,
    RULE_CONTRACT_VS_BUDGET,
    RULE_RISK_EXCEEDS_CONTINGENCY,
    RULE_SCHEDULE_OVERRUNS_DEADLINE,
    RULE_WBS_VS_BUDGET,
    bom_vs_budget_total,
    budget_exceeds_contract,
    compare_values,
    contract_vs_budget_total,
    risk_exceeds_contingency,
    run_numeric_comparators,
    schedule_overruns_deadline,
    wbs_vs_budget_total,
)
from src.coherence.cross_document.findings import CrossDocFinding
from src.coherence.cross_document.inputs import ProjectCrossDocInputs
from src.coherence.cross_document.signal_adapter import to_finding_signal

__all__ = [
    "RULE_BOM_VS_BUDGET",
    "RULE_BUDGET_EXCEEDS_CONTRACT",
    "RULE_CONTRACT_VS_BUDGET",
    "RULE_RISK_EXCEEDS_CONTINGENCY",
    "RULE_SCHEDULE_OVERRUNS_DEADLINE",
    "RULE_WBS_VS_BUDGET",
    "CrossDocFinding",
    "ProjectCrossDocInputs",
    "assemble_cross_doc_inputs",
    "bom_vs_budget_total",
    "budget_exceeds_contract",
    "compare_values",
    "contract_vs_budget_total",
    "cross_document_signals",
    "risk_exceeds_contingency",
    "run_numeric_comparators",
    "schedule_overruns_deadline",
    "to_finding_signal",
    "wbs_vs_budget_total",
]
