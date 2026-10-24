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

from dataclasses import dataclass, field
from datetime import date

from src.coherence.cross_document.findings import CrossDocFinding, CrossDocNotAssessed
from src.coherence.cross_document.inputs import (
    DATE_KIND_CONTRACT_COMPLETION,
    DATE_KIND_SCHEDULE_FINISH,
    DatedSource,
    ProjectCrossDocInputs,
)
from src.coherence.models import CoherenceCategory

# Firing threshold. Contract vs budget totals normally differ by a MARGIN (target margin,
# JV partner share, contingency); only a gap BEYOND this fraction reads as a discrepancy.
# Calibrated from the golden corpus (N=101): synthetic projects carry a uniform ~15% margin
# the expert does NOT flag, while the 25% pilot case is a real incoherence. Interim — refine
# against real precision/recall once the normalized golden lands (aligns with the
# conflict-service CRITICAL_MISMATCH_RATIO = 0.20).
DEFAULT_TOLERANCE = 0.18

RULE_CONTRACT_VS_BUDGET = "DET-CRS-CONBUD"  # contract price ↔ budget total (symmetric gap)
RULE_WBS_VS_BUDGET = "DET-CRS-WBSBUD"  # WBS package sum ↔ budget total
RULE_BOM_VS_BUDGET = "DET-CRS-BOMBUD"  # BOM line sum ↔ budget total
RULE_BUDGET_EXCEEDS_CONTRACT = "DET-CRS-NEGMARGIN"  # budget total ABOVE contract = negative margin
RULE_RISK_EXCEEDS_CONTINGENCY = "DET-CRS-RISKCONT"  # identified risk exposure > contingency fund
RULE_SCHEDULE_OVERRUNS_DEADLINE = "DET-CRS-SCHDEAD"  # schedule end AFTER the contractual deadline (TIME)

# A budget more than this fraction above the contract is a real overrun, not rounding.
# Directional and margin-threshold-independent: a budget BELOW contract is a normal
# margin, but a budget ABOVE it cannot be funded by the contract → always an incoherence.
_NEGATIVE_MARGIN_TOLERANCE = 0.01


def _currency_not_assessed(
    rule_id: str,
    left_key: str,
    left: frozenset[str],
    right_key: str,
    right: frozenset[str],
) -> CrossDocNotAssessed | None:
    """NOT_ASSESSED when two money values do not share one known denomination.

    An unstated denomination on a side is not evidence of a mismatch, so the
    comparison proceeds; stated different or mixed denominations stop it.
    """
    if len(left) > 1 or len(right) > 1:
        reason = "MIXED_CURRENCY"
    elif left and right and left != right:
        reason = "CURRENCY_MISMATCH"
    else:
        return None
    return CrossDocNotAssessed(
        rule_id=rule_id,
        reason=reason,
        left_key=left_key,
        right_key=right_key,
        detail=(
            f"{left_key} in {', '.join(sorted(left)) or 'unstated'} vs {right_key} in "
            f"{', '.join(sorted(right)) or 'unstated'}: no FX basis to compare totals"
        ),
    )


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
    if denom <= 0.0:  # magnitude is non-negative; avoids float == comparison (S1244)
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
) -> CrossDocFinding | CrossDocNotAssessed | None:
    """Contract price ↔ stated budget total (the €1.6M-vs-€1.2M case)."""
    if inputs.contract_total is not None and inputs.budget_total is not None:
        skipped = _currency_not_assessed(
            RULE_CONTRACT_VS_BUDGET,
            "contract_total",
            inputs.contract_currencies,
            "budget_total",
            inputs.budget_currencies,
        )
        if skipped is not None:
            return skipped
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


def budget_exceeds_contract(
    inputs: ProjectCrossDocInputs,
) -> CrossDocFinding | CrossDocNotAssessed | None:
    """Budget total ABOVE contract total = negative margin — always an incoherence.

    A budget below the contract is a normal margin; a budget that EXCEEDS the contract
    price cannot be funded by it, so any overrun beyond rounding is flagged regardless of
    the symmetric margin threshold used by `contract_vs_budget_total`.
    """
    contract = inputs.contract_total
    budget = inputs.budget_total
    if contract is None or budget is None or contract <= 0.0:
        return None
    skipped = _currency_not_assessed(
        RULE_BUDGET_EXCEEDS_CONTRACT,
        "budget_total",
        inputs.budget_currencies,
        "contract_total",
        inputs.contract_currencies,
    )
    if skipped is not None:
        return skipped
    overrun = (budget - contract) / contract
    if overrun <= _NEGATIVE_MARGIN_TOLERANCE:
        return None
    return CrossDocFinding(
        rule_id=RULE_BUDGET_EXCEEDS_CONTRACT,
        category="BUDGET",
        left_key="budget_total",
        left_value=float(budget),
        right_key="contract_total",
        right_value=float(contract),
        delta=float(budget) - float(contract),
        direction="exceeds",
        materiality_ratio=min(1.0, overrun),
        summary=(
            f"budget_total ({budget:,.0f}) exceeds contract_total ({contract:,.0f}) "
            f"by {overrun:.1%} — negative margin"
        ),
    )


def risk_exceeds_contingency(inputs: ProjectCrossDocInputs) -> CrossDocFinding | None:
    """An identified risk exposure exceeding the contingency fund = under-provisioned budget.

    If the largest identified risk is bigger than the contingency/reserve set aside for it,
    the budget cannot absorb that risk — a cross-document incoherence between the risk
    analysis and the contract/budget provision.
    """
    contingency = inputs.contingency
    risk = inputs.max_risk_exposure
    if contingency is None or risk is None or contingency < 0.0:
        return None
    if risk <= contingency:
        return None
    over = (risk - contingency) / contingency if contingency > 0.0 else 1.0
    return CrossDocFinding(
        rule_id=RULE_RISK_EXCEEDS_CONTINGENCY,
        category="BUDGET",
        left_key="max_risk_exposure",
        left_value=float(risk),
        right_key="contingency",
        right_value=float(contingency),
        delta=float(risk) - float(contingency),
        direction="exceeds",
        materiality_ratio=min(1.0, over),
        summary=(
            f"identified risk exposure ({risk:,.0f}) exceeds contingency ({contingency:,.0f})"
        ),
    )


def _date_not_assessed(reason: str, detail: str) -> CrossDocNotAssessed:
    return CrossDocNotAssessed(
        rule_id=RULE_SCHEDULE_OVERRUNS_DEADLINE,
        reason=reason,
        left_key="schedule_end",
        right_key="contract_deadline",
        detail=detail,
    )


def _sourced_dates_not_assessed(
    contract: DatedSource, schedule: DatedSource
) -> CrossDocNotAssessed | None:
    """NOT_ASSESSED unless both dates are comparable, calendar-exact and sourced.

    Comparable = the right KIND (a contractual completion deadline vs a schedule's planned
    finish -- never a milestone, a duration or a start date); sourced = document, revision
    and locator all known on both sides; calendar-exact = an unambiguous ISO date. Anything
    else is "not assessed", never a discrepancy.
    """
    if contract.kind != DATE_KIND_CONTRACT_COMPLETION or schedule.kind != DATE_KIND_SCHEDULE_FINISH:
        return _date_not_assessed(
            "DATE_KIND_NOT_COMPARABLE",
            f"{contract.kind} vs {schedule.kind}: only a contractual completion deadline is "
            "comparable with the schedule planned finish",
        )
    for side, source in (("contract", contract), ("schedule", schedule)):
        if source.value is None:
            return _date_not_assessed(
                "DATE_NOT_ASSESSED",
                f"{side} date not assessed: {source.reason or 'no reason recorded'}",
            )
        if not (source.document_id and source.revision_id and source.locator):
            return _date_not_assessed(
                "UNSOURCED_DATE",
                f"{side} date lacks a verifiable source (document, revision and locator)",
            )
    return None


def schedule_overruns_deadline(
    inputs: ProjectCrossDocInputs,
) -> CrossDocFinding | CrossDocNotAssessed | None:
    """Schedule planned finish AFTER the contractual completion deadline (TIME).

    Sourced path (production): ``contract_completion`` vs ``schedule_finish``. Absent side =
    nothing to compare (None). Both present but not comparable / not sourced / not calendar
    exact = NOT_ASSESSED with the reason; a finding is only emitted for two sourced, comparable,
    unambiguous dates whose order is violated. The finding carries both sources as expected
    (contract) / observed (schedule) evidence and points its alert at the contract clause.

    Calibration path: bare ``contract_deadline`` / ``schedule_end`` strings (no identity) keep
    their original semantics for the golden corpus; production assembly never fills them.
    """
    contract = inputs.contract_completion
    schedule = inputs.schedule_finish
    if contract is not None or schedule is not None:
        if contract is None or schedule is None:
            return None
        skipped = _sourced_dates_not_assessed(contract, schedule)
        if skipped is not None:
            return skipped
        try:
            deadline = date.fromisoformat(str(contract.value))
            end = date.fromisoformat(str(schedule.value))
        except ValueError:
            return _date_not_assessed(
                "AMBIGUOUS_DATE", "a date is not an unambiguous ISO calendar date"
            )
        return _overrun_finding(
            deadline,
            end,
            source_clause_id=contract.locator,
            evidence={
                "expected": {
                    "kind": contract.kind,
                    "date": deadline.isoformat(),
                    "document_id": contract.document_id,
                    "revision_id": contract.revision_id,
                    "clause_id": contract.locator,
                },
                "observed": {
                    "kind": schedule.kind,
                    "date": end.isoformat(),
                    "document_id": schedule.document_id,
                    "revision_id": schedule.revision_id,
                    "source_locator": schedule.locator,
                },
            },
        )

    deadline_iso = inputs.contract_deadline
    end_iso = inputs.schedule_end
    if not deadline_iso or not end_iso:
        return None
    try:
        deadline = date.fromisoformat(deadline_iso)
        end = date.fromisoformat(end_iso)
    except ValueError:
        return None
    return _overrun_finding(deadline, end)


def _overrun_finding(
    deadline: date,
    end: date,
    *,
    source_clause_id: str | None = None,
    evidence: dict[str, object] | None = None,
) -> CrossDocFinding | None:
    if end <= deadline:
        return None
    overrun_days = (end - deadline).days
    return CrossDocFinding(
        rule_id=RULE_SCHEDULE_OVERRUNS_DEADLINE,
        category="TIME",
        left_key="schedule_end",
        left_value=float(end.toordinal()),
        right_key="contract_deadline",
        right_value=float(deadline.toordinal()),
        delta=float(overrun_days),
        direction="exceeds",
        materiality_ratio=min(1.0, overrun_days / 365.0),
        summary=(
            f"schedule ends {end.isoformat()} — {overrun_days} days after the contract "
            f"deadline {deadline.isoformat()}"
        ),
        source_clause_id=source_clause_id,
        evidence=evidence or {},
    )


@dataclass(frozen=True)
class CrossDocAssessment:
    """Material findings plus the comparisons that were NOT_ASSESSED, and why."""

    findings: list[CrossDocFinding] = field(default_factory=list)
    not_assessed: list[CrossDocNotAssessed] = field(default_factory=list)


def assess_numeric_comparators(
    inputs: ProjectCrossDocInputs, *, tolerance: float = DEFAULT_TOLERANCE
) -> CrossDocAssessment:
    """Run every numeric cross-document comparator and keep each outcome."""
    outcomes = [
        comparator(inputs, tolerance=tolerance)
        for comparator in (contract_vs_budget_total, wbs_vs_budget_total, bom_vs_budget_total)
    ]
    outcomes += [
        directional(inputs)
        for directional in (
            budget_exceeds_contract,
            risk_exceeds_contingency,
            schedule_overruns_deadline,
        )
    ]
    return CrossDocAssessment(
        findings=[o for o in outcomes if isinstance(o, CrossDocFinding)],
        not_assessed=[o for o in outcomes if isinstance(o, CrossDocNotAssessed)],
    )


def run_numeric_comparators(
    inputs: ProjectCrossDocInputs, *, tolerance: float = DEFAULT_TOLERANCE
) -> list[CrossDocFinding]:
    """Run every numeric cross-document comparator; return only material findings."""
    return assess_numeric_comparators(inputs, tolerance=tolerance).findings


__all__ = [
    "DEFAULT_TOLERANCE",
    "RULE_BOM_VS_BUDGET",
    "RULE_BUDGET_EXCEEDS_CONTRACT",
    "RULE_CONTRACT_VS_BUDGET",
    "RULE_RISK_EXCEEDS_CONTINGENCY",
    "RULE_SCHEDULE_OVERRUNS_DEADLINE",
    "RULE_WBS_VS_BUDGET",
    "CrossDocAssessment",
    "assess_numeric_comparators",
    "bom_vs_budget_total",
    "budget_exceeds_contract",
    "compare_values",
    "contract_vs_budget_total",
    "risk_exceeds_contingency",
    "run_numeric_comparators",
    "schedule_overruns_deadline",
    "wbs_vs_budget_total",
]
