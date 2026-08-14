# apps/api/src/coherence/rules_engine/deterministic.py
"""
rules_engine/deterministic.py — Production-grade deterministic evaluators v0.3.

Covers all 6 C2Pro coherence categories + cross-dimensional checks.
Aligned with calibration_dataset structure (contract, budget_items,
schedule_items, bom_items, clauses).

Zero LLM cost. All evaluators produce continuous FindingSignal (0.0-1.0).

Location: apps/api/src/coherence/rules_engine/deterministic.py
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime, timedelta
from typing import Any, TypeGuard

from ..models import Clause, FindingSignal, impact_to_severity
from .base import ApplicabilityState, Finding, RuleEvaluator
from .category_utils import infer_category
from .config import DEFAULT_CONFIG, EvaluatorConfig

# ═══════════════════════════════════════════════════════════════
#  CATEGORY: BUDGET (DET-BUD-*)
# ═══════════════════════════════════════════════════════════════

class BudgetOverrunEvaluator(RuleEvaluator):
    """
    DET-BUD-OVERRUN — Continuous budget overrun detection.

    Logarithmic curve:
      5%  → impact 0.28    10% → 0.45
      25% → 0.72           50% → 0.85    100%+ → 0.95
    """
    rule_id = "DET-BUD-OVERRUN"
    rule_name = "Budget Overrun Detection"
    category = "BUDGET"

    def __init__(self, config: EvaluatorConfig = DEFAULT_CONFIG):
        self.config = config

    def applicability(self, clause: Clause) -> ApplicabilityState:
        if _num(clause.data.get("current")) and _num(clause.data.get("planned")):
            return ApplicabilityState.EVALUATED
        return ApplicabilityState.SKIPPED_MISSING_INPUTS

    def evaluate(self, clause: Clause) -> Finding | None:
        s = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=s.raw_data) if s else None

    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        current = clause.data.get("current")
        planned = clause.data.get("planned")
        if not _num(current) or not _num(planned) or planned <= 0:
            return None
        overrun = (current / planned) - 1.0
        if overrun < self.config.budget_overrun_warning_pct:
            return None
        norm = overrun / self.config.budget_overrun_critical_pct
        impact = min(0.95, 0.25 + 0.70 * (1 - math.exp(-1.5 * norm)))
        return _signal(self, clause, impact,
            f"Budget overrun: {current:,.2f} vs planned {planned:,.2f} ({overrun*100:.1f}% over)",
            {"current": current, "planned": planned, "overrun_pct": round(overrun*100, 2),
             "currency": clause.data.get("currency", "N/A")})


class BudgetContingencyEvaluator(RuleEvaluator):
    """DET-BUD-CONTINGENCY — Too low (<5%) or suspiciously high (>20%) contingency."""
    rule_id = "DET-BUD-CONTINGENCY"
    rule_name = "Contingency Reserve Adequacy"
    category = "BUDGET"

    def __init__(self, config: EvaluatorConfig = DEFAULT_CONFIG):
        self.config = config

    def evaluate(self, clause: Clause) -> Finding | None:
        s = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=s.raw_data) if s else None

    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        contingency = clause.data.get("contingency")
        total = clause.data.get("total_budget") or clause.data.get("planned")
        if not _num(contingency) or not _num(total) or total <= 0:
            return None
        pct = contingency / total
        if pct < self.config.budget_contingency_min_pct:
            deficit = self.config.budget_contingency_min_pct - pct
            impact = min(0.85, 0.45 + deficit * 8)
            ev = f"Contingency {pct*100:.1f}% below minimum {self.config.budget_contingency_min_pct*100:.0f}%"
        elif pct > self.config.budget_contingency_max_pct:
            excess = pct - self.config.budget_contingency_max_pct
            impact = min(0.6, 0.30 + excess * 3)
            ev = f"Contingency {pct*100:.1f}% above maximum {self.config.budget_contingency_max_pct*100:.0f}%"
        else:
            return None
        return _signal(self, clause, impact, ev, {"contingency_pct": round(pct*100, 2)})


# Units that denote a time/labor dimension. A row priced per period carries a
# hidden duration (and often headcount) factor, so unit_price × quantity is not
# expected to equal the line total.
_TIME_LABOR_UNITS = frozenset({
    "mes", "meses", "month", "months", "mo",
    "h", "hr", "hora", "horas", "hour", "hours", "hh",
    "jornada", "jornadas", "dia", "día", "dias", "días", "day", "days",
    "semana", "semanas", "week", "weeks",
    "ano", "año", "anio", "anios", "años", "year", "years",
    "persona-mes", "person-month", "pers/mes", "ud/mes", "u/mes", "h/h",
})

# Personnel / labor role keywords (ES + EN). Labor is priced headcount × duration
# × rate, so it is not a 2-factor (quantity × unit_price) line item.
_LABOR_KEYWORDS = (
    "soldador", "montador", "electricista", "ayudante", "peon", "peón",
    "oficial", "operario", "operador", "encargado", "capataz", "cuadrilla",
    "ingeniero", "tecnico", "técnico", "jefe", "director", "administrativo",
    "auxiliar", "jornalero", "maquinista", "conductor", "gruista", "gruísta",
    "mano de obra", "welder", "fitter", "electrician", "laborer", "labourer",
    "foreman", "engineer", "technician", "supervisor", "operator",
)

# Explicit duration phrasing in the item name, e.g. "5 uds. x 4 meses" or "/mes".
# Requires a time word so dimension specs like "3x150 mm²" are NOT matched.
_DURATION_PATTERN = re.compile(
    r"\d+\s*(mes|meses|month|months|semana|semanas|week|weeks|"
    r"jornada|jornadas|hora|horas|hour|hours|dia|día|dias|días|day|days|"
    r"año|años|anio|anios|year|years)\b"
    r"|/\s*mes\b|€\s*/\s*mes",
    re.IGNORECASE,
)


def _is_multi_factor_line(name: str | None, unit: object) -> bool:
    """True when a budget row is priced by a hidden third factor (duration/headcount).

    Labor and period-rented rows carry an implicit time (and often headcount)
    dimension, so unit_price × quantity intentionally differs from the line
    total. Applying the 2-factor arithmetic check to them yields false positives
    (TASK-COH-BUD-LINEITEM-011). Detection is heuristic and conservative — a unit
    denoting time, a personnel role in the name, or explicit duration phrasing.
    """
    if isinstance(unit, str) and unit.strip().lower() in _TIME_LABOR_UNITS:
        return True
    if not name:
        return False
    lowered = name.lower()
    if any(keyword in lowered for keyword in _LABOR_KEYWORDS):
        return True
    return bool(_DURATION_PATTERN.search(lowered))


class BudgetLineItemEvaluator(RuleEvaluator):
    """DET-BUD-LINEITEM — Checks unit_price × quantity ≈ line_total.

    Skips multi-factor rows (labor / period-rented equipment) — see
    ``_is_multi_factor_line`` — because their total includes a hidden duration
    or headcount factor and the 2-factor check would raise false positives.
    """
    rule_id = "DET-BUD-LINEITEM"
    rule_name = "Line Item Arithmetic Check"
    category = "BUDGET"

    def __init__(self, config: EvaluatorConfig = DEFAULT_CONFIG):
        self.config = config

    def applicability(self, clause: Clause) -> ApplicabilityState:
        up, qty = clause.data.get("unit_price"), clause.data.get("quantity")
        total = clause.data.get("line_total") or clause.data.get("total")
        if not _num(up) or not _num(qty) or not _num(total):
            return ApplicabilityState.SKIPPED_MISSING_INPUTS
        if _is_multi_factor_line(clause.text, clause.data.get("unit")):
            return ApplicabilityState.SKIPPED_MISSING_INPUTS
        return ApplicabilityState.EVALUATED

    def evaluate(self, clause: Clause) -> Finding | None:
        s = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=s.raw_data) if s else None

    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        up = clause.data.get("unit_price")
        qty = clause.data.get("quantity")
        total = clause.data.get("line_total") or clause.data.get("total")
        if not _num(up) or not _num(qty) or not _num(total) or up <= 0 or qty <= 0:
            return None
        if _is_multi_factor_line(clause.text, clause.data.get("unit")):
            return None
        expected = up * qty
        dev = abs(expected - total) / expected
        if dev <= self.config.budget_unit_price_tolerance_pct:
            return None
        impact = min(0.9, 0.4 + dev * 2.5)
        return _signal(self, clause, impact,
            f"Line item: {up} × {qty} = {expected:,.2f} but stated {total:,.2f} ({dev*100:.1f}% off)",
            {"unit_price": up, "quantity": qty, "expected": round(expected,2),
             "stated": total, "deviation_pct": round(dev*100, 2)})


class BudgetSumMismatchEvaluator(RuleEvaluator):
    """
    DET-BUD-SUM — Checks that sum of budget_items ≈ contract total.

    Aligned with calibration_dataset: budget_items[].amount vs contract.total_amount.
    This is the first cross-dimensional check (budget vs contract).
    """
    rule_id = "DET-BUD-SUM"
    rule_name = "Budget Items vs Contract Total"
    category = "BUDGET"

    def __init__(self, config: EvaluatorConfig = DEFAULT_CONFIG):
        self.config = config

    def applicability(self, clause: Clause) -> ApplicabilityState:
        budget_items = clause.data.get("budget_items")
        contract_total = clause.data.get("contract_total") or clause.data.get("total_amount")
        if (
            isinstance(budget_items, list)
            and budget_items
            and _num(contract_total)
            and contract_total > 0
        ):
            return ApplicabilityState.EVALUATED
        return ApplicabilityState.SKIPPED_MISSING_INPUTS

    def evaluate(self, clause: Clause) -> Finding | None:
        s = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=s.raw_data) if s else None

    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        budget_items = clause.data.get("budget_items", [])
        contract_total = clause.data.get("contract_total") or clause.data.get("total_amount")
        if not isinstance(budget_items, list) or not _num(contract_total) or contract_total <= 0:
            return None
        items_sum = sum(
            item.get("amount", 0) for item in budget_items if isinstance(item, dict)
        )
        if items_sum <= 0:
            return None
        dev = abs(items_sum - contract_total) / contract_total
        if dev <= self.config.budget_sum_tolerance_pct:
            return None
        # Budget items sum > contract = overcommitted; < contract = incomplete coverage
        direction = "exceeds" if items_sum > contract_total else "below"
        impact = min(0.85, 0.35 + dev * 2.0)
        currency = clause.data.get("currency")
        raw: dict[str, Any] = {"items_sum": round(items_sum, 2), "contract_total": contract_total,
             "deviation_pct": round(dev * 100, 2), "direction": direction}
        if currency:
            raw["currency"] = currency
        return _signal(self, clause, impact,
            f"Budget items sum {items_sum:,.2f} {direction} contract total {contract_total:,.2f} ({dev*100:.1f}%)",
            raw)


class BudgetInternalConsistencyEvaluator(RuleEvaluator):
    """
    DET-BUD-INTERNAL — Checks that sum of budget_items ≈ the budget's declared total.

    TASK-COH-BUD-RECON-004: this is an intra-document budget check. It only
    evaluates when the source budget provided an explicit stated_total.
    """

    rule_id = "DET-BUD-INTERNAL"
    rule_name = "Budget Items vs Declared Total"
    category = "BUDGET"

    def __init__(self, config: EvaluatorConfig = DEFAULT_CONFIG):
        self.config = config

    def applicability(self, clause: Clause) -> ApplicabilityState:
        budget_items = clause.data.get("budget_items")
        stated_total = clause.data.get("stated_total")
        if (
            isinstance(budget_items, list)
            and budget_items
            and _num(stated_total)
            and stated_total > 0
        ):
            return ApplicabilityState.EVALUATED
        return ApplicabilityState.SKIPPED_MISSING_INPUTS

    def evaluate(self, clause: Clause) -> Finding | None:
        s = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=s.raw_data) if s else None

    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        budget_items = clause.data.get("budget_items", [])
        stated_total = clause.data.get("stated_total")
        if not isinstance(budget_items, list) or not _num(stated_total) or stated_total <= 0:
            return None
        items_sum = sum(
            item.get("amount", 0) for item in budget_items if isinstance(item, dict)
        )
        if items_sum <= 0:
            return None
        dev = abs(items_sum - stated_total) / stated_total
        if dev <= self.config.budget_sum_tolerance_pct:
            return None
        direction = "exceeds" if items_sum > stated_total else "below"
        impact = min(0.85, 0.35 + dev * 2.0)
        currency = clause.data.get("currency")
        raw: dict[str, Any] = {
            "items_sum": round(items_sum, 2),
            "stated_total": stated_total,
            "deviation_pct": round(dev * 100, 2),
            "direction": direction,
        }
        if currency:
            raw["currency"] = currency
        return _signal(
            self,
            clause,
            impact,
            (
                f"Budget line items sum {items_sum:,.2f} differ from declared total "
                f"{stated_total:,.2f} ({dev*100:.1f}%)"
            ),
            raw,
        )


class RetentionRateEvaluator(RuleEvaluator):
    """DET-BUD-RETENTION — Retention % within 3-10% norms."""
    rule_id = "DET-BUD-RETENTION"
    rule_name = "Retention Rate Validation"
    category = "BUDGET"

    def __init__(self, config: EvaluatorConfig = DEFAULT_CONFIG):
        self.config = config

    def evaluate(self, clause: Clause) -> Finding | None:
        s = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=s.raw_data) if s else None

    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        ret = clause.data.get("retention_pct") or clause.data.get("retention_rate")
        if not _num(ret):
            return None
        if ret > 1:
            ret = ret / 100
        if ret < self.config.retention_min_pct:
            impact = min(0.8, 0.6 + (self.config.retention_min_pct - ret) * 10)
            ev = f"Retention {ret*100:.1f}% below minimum {self.config.retention_min_pct*100:.0f}%"
        elif ret > self.config.retention_max_pct:
            impact = min(0.6, 0.4 + (ret - self.config.retention_max_pct) * 5)
            ev = f"Retention {ret*100:.1f}% above maximum {self.config.retention_max_pct*100:.0f}%"
        else:
            return None
        return _signal(self, clause, impact, ev, {"retention_pct": round(ret*100, 2)})


class AdvancePaymentEvaluator(RuleEvaluator):
    """DET-BUD-ADVANCE — Advance payment >30% without bank guarantee = high risk."""
    rule_id = "DET-BUD-ADVANCE"
    rule_name = "Advance Payment Risk"
    category = "BUDGET"

    def __init__(self, config: EvaluatorConfig = DEFAULT_CONFIG):
        self.config = config

    def evaluate(self, clause: Clause) -> Finding | None:
        s = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=s.raw_data) if s else None

    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        adv = clause.data.get("advance_pct") or clause.data.get("advance_payment_pct")
        guarantee = clause.data.get("bank_guarantee", False)
        if not _num(adv):
            return None
        if adv > 1:
            adv = adv / 100
        if adv <= self.config.advance_payment_max_pct:
            return None
        impact = min(0.9, 0.4 + (adv - self.config.advance_payment_max_pct) * 3 + (0.15 if not guarantee else 0))
        return _signal(self, clause, impact,
            f"Advance {adv*100:.1f}% > {self.config.advance_payment_max_pct*100:.0f}%"
            f"{' without bank guarantee' if not guarantee else ''}",
            {"advance_pct": round(adv*100, 2), "has_guarantee": guarantee})


# ═══════════════════════════════════════════════════════════════
#  CATEGORY: TIME (DET-TIM-*)
# ═══════════════════════════════════════════════════════════════

class ScheduleStatusEvaluator(RuleEvaluator):
    """DET-TIM-STATUS — Multi-status with differentiated impact."""
    rule_id = "DET-TIM-STATUS"
    rule_name = "Schedule Status Assessment"
    category = "TIME"

    STATUS_IMPACT = {
        "delayed": 0.70, "behind": 0.65, "at_risk": 0.50, "at-risk": 0.50,
        "critical": 0.85, "suspended": 0.80, "cancelled": 0.90,
        "force_majeure": 0.75, "stopped": 0.85,
    }

    def applicability(self, clause: Clause) -> ApplicabilityState:
        if infer_category(clause) in ("TIME", "SCHEDULE") and str(
            clause.data.get("status", "")
        ).strip():
            return ApplicabilityState.EVALUATED
        return ApplicabilityState.SKIPPED_MISSING_INPUTS

    def evaluate(self, clause: Clause) -> Finding | None:
        s = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=s.raw_data) if s else None

    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        if infer_category(clause) not in ("TIME", "SCHEDULE"):
            return None
        status = str(clause.data.get("status", "")).lower().strip()
        impact = self.STATUS_IMPACT.get(status)
        if impact is None:
            return None
        return _signal(self, clause, impact, f"Schedule status: '{status}'", {"status": status})


class DeadlineOverdueEvaluator(RuleEvaluator):
    """DET-TIM-OVERDUE — Progressive severity: 7d→low, 30d→high, 90d+→critical."""
    rule_id = "DET-TIM-OVERDUE"
    rule_name = "Deadline Overdue"
    category = "TIME"

    def evaluate(self, clause: Clause) -> Finding | None:
        s = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=s.raw_data) if s else None

    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        d = _parse_date(clause.data.get("end_date") or clause.data.get("deadline") or clause.data.get("due_date"))
        if d is None:
            return None
        days = (date.today() - d).days
        if days <= 0:
            return None
        impact = min(0.95, 0.2 + 0.75 * (1 - math.exp(-days / 60)))
        return _signal(self, clause, impact,
            f"Deadline {d} is {days} days overdue",
            {"deadline": str(d), "days_overdue": days})


class MilestoneGapEvaluator(RuleEvaluator):
    """DET-TIM-GAP — Gaps > 90 days between consecutive milestones."""
    rule_id = "DET-TIM-GAP"
    rule_name = "Milestone Gap Detection"
    category = "TIME"

    def __init__(self, config: EvaluatorConfig = DEFAULT_CONFIG):
        self.config = config

    def evaluate(self, clause: Clause) -> Finding | None:
        s = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=s.raw_data) if s else None

    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        milestones = clause.data.get("milestones") or clause.data.get("schedule_items", [])
        if not isinstance(milestones, list) or len(milestones) < 2:
            return None
        dated_milestones = sorted(
            [
                (parsed_date, milestone)
                for milestone in milestones
                if isinstance(milestone, dict)
                if (parsed_date := _parse_date(
                    milestone.get("date") or milestone.get("end_date") or milestone.get("due_date")
                )) is not None
            ],
            key=lambda item: item[0],
        )
        if len(dated_milestones) < 2:
            return None
        prior, following = max(
            (
                (dated_milestones[index], dated_milestones[index + 1])
                for index in range(len(dated_milestones) - 1)
            ),
            key=lambda pair: (pair[1][0] - pair[0][0]).days,
        )
        max_gap = (following[0] - prior[0]).days
        if max_gap <= self.config.schedule_milestone_gap_max_days:
            return None
        excess = max_gap - self.config.schedule_milestone_gap_max_days
        impact = min(0.7, 0.30 + (excess / 180) * 0.4)
        return _signal(self, clause, impact,
            f"Max gap {max_gap}d between milestones (limit: {self.config.schedule_milestone_gap_max_days}d)",
            {
                "max_gap_days": max_gap,
                "milestone_before_id": prior[1].get("wbs_node_id", prior[1].get("id")),
                "milestone_after_id": following[1].get("wbs_node_id", following[1].get("id")),
            })


class PredecessorOverlapEvaluator(RuleEvaluator):
    """
    DET-TIM-PREDECESSOR — Detects schedule items that start before their predecessor ends.

    Aligned with calibration_dataset: schedule_items[].predecessor_id.
    A task starting before its predecessor finishes creates an impossible schedule.
    """
    rule_id = "DET-TIM-PREDECESSOR"
    rule_name = "Predecessor Overlap Detection"
    category = "TIME"

    def evaluate(self, clause: Clause) -> Finding | None:
        s = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=s.raw_data) if s else None

    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        items = clause.data.get("schedule_items", [])
        if not isinstance(items, list) or len(items) < 2:
            return None
        # Build lookup: id → item
        lookup: dict[str, dict[str, Any]] = {}
        for item in items:
            if isinstance(item, dict) and item.get("id"):
                lookup[item["id"]] = item

        worst_overlap = 0
        worst_pair: tuple[dict[str, Any] | None, dict[str, Any] | None] = (None, None)
        for item in items:
            if not isinstance(item, dict):
                continue
            pred_id = item.get("predecessor_id")
            if not pred_id or pred_id not in lookup:
                continue
            pred = lookup[pred_id]
            pred_end = _parse_date(pred.get("end_date"))
            item_start = _parse_date(item.get("start_date"))
            if pred_end and item_start and item_start < pred_end:
                overlap = (pred_end - item_start).days
                if overlap > worst_overlap:
                    worst_overlap = overlap
                    worst_pair = (pred, item)

        if worst_overlap <= 0:
            return None
        impact = min(0.85, 0.45 + worst_overlap / 60 * 0.4)
        predecessor, successor = worst_pair
        if predecessor is None or successor is None:
            return None
        predecessor_name = predecessor.get("name", "")
        successor_name = successor.get("name", "")
        return _signal(self, clause, impact,
            f"Task '{successor_name}' starts {worst_overlap}d before predecessor '{predecessor_name}' ends",
            {
                "overlap_days": worst_overlap,
                "predecessor": predecessor_name,
                "successor": successor_name,
                "predecessor_id": predecessor.get("wbs_node_id", predecessor.get("id")),
                "successor_id": successor.get("wbs_node_id", successor.get("id")),
            })


class ScheduleDurationEvaluator(RuleEvaluator):
    """DET-TIM-DURATION — End before start, or insufficient buffer."""
    rule_id = "DET-TIM-DURATION"
    rule_name = "Duration Realism"
    category = "TIME"

    def __init__(self, config: EvaluatorConfig = DEFAULT_CONFIG):
        self.config = config

    def applicability(self, clause: Clause) -> ApplicabilityState:
        has_dates = clause.data.get("start_date") and clause.data.get("end_date")
        has_buf = _num(clause.data.get("buffer_days")) or _num(clause.data.get("float_days"))
        if has_dates or has_buf:
            return ApplicabilityState.EVALUATED
        return ApplicabilityState.SKIPPED_MISSING_INPUTS

    def evaluate(self, clause: Clause) -> Finding | None:
        s = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=s.raw_data) if s else None

    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        start = _parse_date(clause.data.get("start_date"))
        end = _parse_date(clause.data.get("end_date"))
        if start and end and end <= start:
            return _signal(self, clause, 0.90,
                f"End date ({end}) ≤ start date ({start})",
                {"start": str(start), "end": str(end)})
        buf = clause.data.get("buffer_days") or clause.data.get("float_days")
        if _num(buf) and buf < self.config.schedule_buffer_min_days:
            impact = min(0.65, 0.35 + (self.config.schedule_buffer_min_days - buf) / self.config.schedule_buffer_min_days * 0.3)
            return _signal(self, clause, impact,
                f"Buffer {buf}d < minimum {self.config.schedule_buffer_min_days}d",
                {"buffer_days": buf})
        return None


# ═══════════════════════════════════════════════════════════════
#  CATEGORY: LEGAL (DET-LEG-*)
# ═══════════════════════════════════════════════════════════════

class ContractReviewOverdueEvaluator(RuleEvaluator):
    """DET-LEG-REVIEW — Configurable, no more hardcoded date."""
    rule_id = "DET-LEG-REVIEW"
    rule_name = "Contract Review Overdue"
    category = "LEGAL"

    def __init__(self, config: EvaluatorConfig = DEFAULT_CONFIG):
        self.config = config

    def applicability(self, clause: Clause) -> ApplicabilityState:
        if clause.data.get("last_review_date") is not None:
            return ApplicabilityState.EVALUATED
        return ApplicabilityState.SKIPPED_MISSING_INPUTS

    def evaluate(self, clause: Clause) -> Finding | None:
        s = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=s.raw_data) if s else None

    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        d = _parse_date(clause.data.get("last_review_date"))
        if d is None:
            return None
        days = (date.today() - d).days
        if days < self.config.contract_review_warning_days:
            return None
        norm = (days - self.config.contract_review_warning_days) / 365
        impact = min(0.85, 0.25 + 0.60 * (1 - math.exp(-1.2 * norm)))
        return _signal(self, clause, impact,
            f"Last review {days} days ago ({d})",
            {"last_review_date": str(d), "days_since": days})


class PenaltyCapEvaluator(RuleEvaluator):
    """DET-LEG-PENALTY — Missing cap = unlimited liability; excessive cap or daily rate."""
    rule_id = "DET-LEG-PENALTY"
    rule_name = "Penalty Clause Validation"
    category = "LEGAL"

    def __init__(self, config: EvaluatorConfig = DEFAULT_CONFIG):
        self.config = config

    def applicability(self, clause: Clause) -> ApplicabilityState:
        d = clause.data
        if (
            d.get("has_penalty_cap") is not None
            or _num(d.get("penalty_cap_pct"))
            or _num(d.get("daily_penalty_pct"))
        ):
            return ApplicabilityState.EVALUATED
        return ApplicabilityState.SKIPPED_MISSING_INPUTS

    def evaluate(self, clause: Clause) -> Finding | None:
        s = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=s.raw_data) if s else None

    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        cap = clause.data.get("penalty_cap_pct")
        daily = clause.data.get("daily_penalty_pct")
        has_cap = clause.data.get("has_penalty_cap")
        if has_cap is False:
            return _signal(self, clause, 0.80,
                "Penalty clause without cumulative cap — unlimited liability",
                {"has_cap": False})
        if _num(cap):
            cap = cap / 100 if cap > 1 else cap
            if cap > self.config.penalty_cap_max_pct:
                impact = min(0.8, 0.45 + (cap - self.config.penalty_cap_max_pct) * 4)
                return _signal(self, clause, impact,
                    f"Penalty cap {cap*100:.1f}% > max {self.config.penalty_cap_max_pct*100:.0f}%",
                    {"penalty_cap_pct": round(cap*100, 2)})
        if _num(daily):
            daily = daily / 100 if daily > 1 else daily
            if daily > self.config.daily_penalty_max_pct:
                impact = min(0.7, 0.40 + (daily - self.config.daily_penalty_max_pct) * 60)
                return _signal(self, clause, impact,
                    f"Daily penalty {daily*100:.3f}% > max {self.config.daily_penalty_max_pct*100:.2f}%",
                    {"daily_penalty_pct": round(daily*100, 4)})
        return None


class NoticePeriodEvaluator(RuleEvaluator):
    """DET-LEG-NOTICE — Too short (<14d) or too long (>90d) notice periods."""
    rule_id = "DET-LEG-NOTICE"
    rule_name = "Notice Period Validation"
    category = "LEGAL"

    def __init__(self, config: EvaluatorConfig = DEFAULT_CONFIG):
        self.config = config

    def applicability(self, clause: Clause) -> ApplicabilityState:
        if _num(clause.data.get("notice_period_days")):
            return ApplicabilityState.EVALUATED
        return ApplicabilityState.SKIPPED_MISSING_INPUTS

    def evaluate(self, clause: Clause) -> Finding | None:
        s = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=s.raw_data) if s else None

    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        days = clause.data.get("notice_period_days")
        if not _num(days):
            return None
        if days < self.config.notice_period_min_days:
            impact = min(0.75, 0.50 + (self.config.notice_period_min_days - days) / self.config.notice_period_min_days * 0.25)
            ev = f"Notice {days}d < min {self.config.notice_period_min_days}d"
        elif days > self.config.notice_period_max_days:
            impact = min(0.6, 0.35 + (days - self.config.notice_period_max_days) / 180 * 0.25)
            ev = f"Notice {days}d > expected max {self.config.notice_period_max_days}d"
        else:
            return None
        return _signal(self, clause, impact, ev, {"notice_days": days})


class WarrantyPeriodEvaluator(RuleEvaluator):
    """DET-LEG-WARRANTY — Too short (<6m) or too long (>60m) warranty."""
    rule_id = "DET-LEG-WARRANTY"
    rule_name = "Warranty Period Validation"
    category = "LEGAL"

    def __init__(self, config: EvaluatorConfig = DEFAULT_CONFIG):
        self.config = config

    def evaluate(self, clause: Clause) -> Finding | None:
        s = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=s.raw_data) if s else None

    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        m = clause.data.get("warranty_months") or clause.data.get("defects_liability_months")
        if not _num(m):
            return None
        if m < self.config.warranty_min_months:
            impact = min(0.75, 0.5 + (self.config.warranty_min_months - m) / self.config.warranty_min_months * 0.25)
            ev = f"Warranty {m}m < min {self.config.warranty_min_months}m"
        elif m > self.config.warranty_max_months:
            ev = f"Warranty {m}m > expected max {self.config.warranty_max_months}m"
            impact = 0.35
        else:
            return None
        return _signal(self, clause, impact, ev, {"warranty_months": m})


class PaymentTermEvaluator(RuleEvaluator):
    """DET-LEG-PAYMENT — Payment terms > 60 days."""
    rule_id = "DET-LEG-PAYMENT"
    rule_name = "Payment Term Validation"
    category = "LEGAL"

    def __init__(self, config: EvaluatorConfig = DEFAULT_CONFIG):
        self.config = config

    def evaluate(self, clause: Clause) -> Finding | None:
        s = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=s.raw_data) if s else None

    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        days = clause.data.get("payment_term_days") or clause.data.get("payment_days")
        if not _num(days) or days <= self.config.payment_term_max_days:
            return None
        excess = days - self.config.payment_term_max_days
        impact = min(0.7, 0.35 + excess / 90 * 0.35)
        return _signal(self, clause, impact,
            f"Payment term {days}d > {self.config.payment_term_max_days}d limit",
            {"payment_days": days})


class InsuranceExpiryEvaluator(RuleEvaluator):
    """DET-LEG-INSURANCE — Insurance/bond expiry vs project end."""
    rule_id = "DET-LEG-INSURANCE"
    rule_name = "Insurance/Bond Expiry"
    category = "LEGAL"

    def __init__(self, config: EvaluatorConfig = DEFAULT_CONFIG):
        self.config = config

    def evaluate(self, clause: Clause) -> Finding | None:
        s = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=s.raw_data) if s else None

    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        expiry = _parse_date(clause.data.get("insurance_expiry") or clause.data.get("bond_expiry"))
        if not expiry:
            return None
        proj_end = _parse_date(clause.data.get("project_end_date"))
        if proj_end and expiry < proj_end:
            gap = (proj_end - expiry).days
            impact = min(0.85, 0.55 + gap / 365 * 0.3)
            return _signal(self, clause, impact,
                f"Insurance expires {expiry} — {gap}d before project end {proj_end}",
                {"expiry": str(expiry), "project_end": str(proj_end), "gap_days": gap})
        to_expiry = (expiry - date.today()).days
        if to_expiry <= 0:
            return _signal(self, clause, 0.85,
                f"Insurance expired {abs(to_expiry)} days ago ({expiry})",
                {"expiry": str(expiry), "days_expired": abs(to_expiry)})
        if to_expiry <= self.config.insurance_expiry_warning_days:
            impact = 0.45 + (self.config.insurance_expiry_warning_days - to_expiry) / self.config.insurance_expiry_warning_days * 0.3
            return _signal(self, clause, round(impact, 3),
                f"Insurance expires in {to_expiry}d ({expiry})",
                {"expiry": str(expiry), "days_to_expiry": to_expiry})
        return None


# ═══════════════════════════════════════════════════════════════
#  CATEGORY: TECHNICAL (DET-TEC-*)
# ═══════════════════════════════════════════════════════════════

class BomLeadTimeEvaluator(RuleEvaluator):
    """
    DET-TEC-LEADTIME — Checks if BOM item lead time fits before required_on_site_date.

    Aligned with calibration_dataset: bom_items[].lead_time_days, required_on_site_date.
    If ordering today wouldn't arrive on time, that's a procurement risk.
    """
    rule_id = "DET-TEC-LEADTIME"
    rule_name = "BOM Lead Time Feasibility"
    category = "TECHNICAL"

    def evaluate(self, clause: Clause) -> Finding | None:
        s = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=s.raw_data) if s else None

    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        lead_days = clause.data.get("lead_time_days")
        needed_str = clause.data.get("required_on_site_date")
        if not _num(lead_days) or not needed_str:
            return None
        needed = _parse_date(needed_str)
        if not needed:
            return None
        latest_order = needed - timedelta(days=int(lead_days))
        days_remaining = (latest_order - date.today()).days
        if days_remaining >= 14:  # 2-week safety margin
            return None
        if days_remaining < 0:
            impact = min(0.9, 0.65 + abs(days_remaining) / 60 * 0.25)
            ev = f"BOM item '{clause.data.get('item_name', 'unknown')}': ordering window closed {abs(days_remaining)}d ago"
        else:
            impact = min(0.6, 0.35 + (14 - days_remaining) / 14 * 0.25)
            ev = f"BOM item '{clause.data.get('item_name', 'unknown')}': only {days_remaining}d left to order (lead time: {lead_days}d)"
        return _signal(self, clause, impact, ev,
            {"item": clause.data.get("item_name"), "lead_time_days": lead_days,
             "needed_by": str(needed), "days_remaining_to_order": days_remaining})


class SpecReferenceEvaluator(RuleEvaluator):
    """
    DET-TEC-SPEC — Checks that technical clauses reference specific standards or specs.

    If a technical clause has no spec_reference, standard, or norm field,
    it's missing traceable technical requirements.
    """
    rule_id = "DET-TEC-SPEC"
    rule_name = "Technical Specification Reference"
    category = "TECHNICAL"

    def applicability(self, clause: Clause) -> ApplicabilityState:
        if any(
            clause.data.get(k) not in (None, [], "")
            for k in ("material", "bom_items", "item_name", "lead_time_days")
        ):
            return ApplicabilityState.EVALUATED
        return ApplicabilityState.SKIPPED_MISSING_INPUTS

    def evaluate(self, clause: Clause) -> Finding | None:
        s = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=s.raw_data) if s else None

    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        # Only fire when extraction confirmed material/BOM content exists.
        # If extraction ran and left these fields null the clause isn't a
        # spec/BOM clause, regardless of what keywords appear in its text.
        has_material_content = any(
            clause.data.get(k) not in (None, [], "")
            for k in ("material", "bom_items", "item_name", "lead_time_days")
        )
        if not has_material_content:
            return None
        has_spec = any(clause.data.get(k) for k in (
            "spec_reference", "standard", "norm", "iso", "astm", "en_standard",
            "specification", "technical_standard",
        ))
        if not has_spec:
            return _signal(self, clause, 0.45,
                "Technical clause without specific standard/specification reference",
                {"missing": "spec_reference or standard or norm"})
        return None


class BomBudgetLinkEvaluator(RuleEvaluator):
    """
    DET-TEC-BOMBUDGET — Checks that BOM items have a linked budget item.

    Aligned with calibration_dataset: bom_items[].budget_item_id.
    Materials without budget allocation = procurement risk.
    """
    rule_id = "DET-TEC-BOMBUDGET"
    rule_name = "BOM-Budget Linkage"
    category = "TECHNICAL"

    def applicability(self, clause: Clause) -> ApplicabilityState:
        bom = clause.data.get("bom_items")
        if isinstance(bom, list) and len(bom) > 0:
            return ApplicabilityState.EVALUATED
        return ApplicabilityState.SKIPPED_MISSING_INPUTS

    def evaluate(self, clause: Clause) -> Finding | None:
        s = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=s.raw_data) if s else None

    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        bom_items = clause.data.get("bom_items", [])
        if not isinstance(bom_items, list) or len(bom_items) == 0:
            return None
        unlinked = [
            item.get("item_name", f"item-{i}")
            for i, item in enumerate(bom_items)
            if isinstance(item, dict) and not item.get("budget_item_id")
        ]
        if not unlinked:
            return None
        ratio = len(unlinked) / len(bom_items)
        impact = min(0.75, 0.30 + ratio * 0.45)
        return _signal(self, clause, impact,
            f"{len(unlinked)}/{len(bom_items)} BOM items without budget allocation: {', '.join(unlinked[:5])}",
            {"unlinked_count": len(unlinked), "total": len(bom_items),
             "unlinked_items": unlinked[:10]})


# ═══════════════════════════════════════════════════════════════
#  CATEGORY: QUALITY (DET-QUA-*)
# ═══════════════════════════════════════════════════════════════

class QualityStandardEvaluator(RuleEvaluator):
    """
    DET-QUA-STANDARD — Validates that quality clauses cite specific standards.

    Flags generic "industry standards" or "best practices" without
    ISO/EN/ASTM/AASHTO references.
    """
    rule_id = "DET-QUA-STANDARD"
    rule_name = "Quality Standard Specificity"
    category = "QUALITY"

    VAGUE_TERMS = {
        "industry standards", "best practices", "good practices",
        "accepted standards", "current standards", "applicable standards",
        "generally accepted", "customary", "usual standards",
    }

    def applicability(self, clause: Clause) -> ApplicabilityState:
        if infer_category(clause) in ("QUALITY", "TECHNICAL"):
            return ApplicabilityState.EVALUATED
        return ApplicabilityState.SKIPPED_MISSING_INPUTS

    def evaluate(self, clause: Clause) -> Finding | None:
        s = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=s.raw_data) if s else None

    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        if infer_category(clause) not in ("QUALITY", "TECHNICAL"):
            return None
        text_lower = (clause.text or "").lower()
        standards = clause.data.get("quality_standards") or clause.data.get("standards", [])
        has_specific = bool(standards) or any(
            kw in text_lower for kw in ("iso ", "en ", "astm ", "aashto ", "din ", "une ", "bs ")
        )
        has_vague = any(term in text_lower for term in self.VAGUE_TERMS)

        if has_vague and not has_specific:
            return _signal(self, clause, 0.55,
                "Quality clause references vague standards without specific ISO/EN/ASTM citations",
                {"vague_terms_found": True, "specific_standards_found": False})
        return None


class InspectionFrequencyEvaluator(RuleEvaluator):
    """
    DET-QUA-INSPECT — Validates inspection/testing frequency is defined.

    Quality clauses that mention inspections but don't specify frequency,
    method, or responsible party are incomplete.
    """
    rule_id = "DET-QUA-INSPECT"
    rule_name = "Inspection Frequency Validation"
    category = "QUALITY"

    def applicability(self, clause: Clause) -> ApplicabilityState:
        if infer_category(clause) in ("QUALITY", "TECHNICAL"):
            return ApplicabilityState.EVALUATED
        return ApplicabilityState.SKIPPED_MISSING_INPUTS

    def evaluate(self, clause: Clause) -> Finding | None:
        s = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=s.raw_data) if s else None

    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        if infer_category(clause) not in ("QUALITY", "TECHNICAL"):
            return None
        has_inspection = clause.data.get("inspection") or clause.data.get("testing")
        if not has_inspection:
            # Check text for inspection-related keywords
            text_lower = (clause.text or "").lower()
            if not any(kw in text_lower for kw in ("inspection", "testing", "quality control", "qc")):
                return None

        has_frequency = clause.data.get("inspection_frequency") or clause.data.get("testing_frequency")
        has_method = clause.data.get("inspection_method") or clause.data.get("testing_method")

        missing = []
        if not has_frequency:
            missing.append("frequency")
        if not has_method:
            missing.append("method")

        if not missing:
            return None
        impact = 0.30 + len(missing) * 0.12
        return _signal(self, clause, impact,
            f"Inspection clause missing: {', '.join(missing)}",
            {"missing_fields": missing})


# ═══════════════════════════════════════════════════════════════
#  CATEGORY: SCOPE (DET-SCP-*)
# ═══════════════════════════════════════════════════════════════

class MissingRequiredFieldsEvaluator(RuleEvaluator):
    """DET-SCP-MISSING — Category-specific required field checks."""
    rule_id = "DET-SCP-MISSING"
    rule_name = "Missing Required Fields"
    category = "SCOPE"

    REQUIRED: dict[str, list[str]] = {
        "BUDGET": ["planned", "currency"],
        "TIME": ["end_date"],
        "LEGAL": [],
        "SCOPE": [],
        "QUALITY": [],
        "TECHNICAL": [],
    }

    def evaluate(self, clause: Clause) -> Finding | None:
        s = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=s.raw_data) if s else None

    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        cat = self._infer(clause)
        missing = [f for f in self.REQUIRED.get(cat, []) if clause.data.get(f) is None]
        if not missing:
            return None
        impact = min(0.7, 0.3 + len(missing) * 0.15)
        return _signal(self, clause, impact,
            f"Missing required fields for {cat}: {', '.join(missing)}",
            {"missing": missing, "category": cat})

    @staticmethod
    def _infer(clause: Clause) -> str:
        d = clause.data or {}
        if any(k in d for k in ("current", "planned", "budget")):
            return "BUDGET"
        if any(k in d for k in ("status", "end_date", "deadline")):
            return "TIME"
        if any(k in d for k in ("last_review_date", "penalty", "termination")):
            return "LEGAL"
        if any(k in d for k in ("item_name", "specification", "material")):
            return "TECHNICAL"
        if any(k in d for k in ("standard", "quality", "inspection")):
            return "QUALITY"
        return "SCOPE"


class ScopeDeliverablesEvaluator(RuleEvaluator):
    """
    DET-SCP-DELIVERABLES — Checks that scope clauses define measurable deliverables.

    A scope clause with text but no structured deliverables data is incomplete.
    """
    rule_id = "DET-SCP-DELIVERABLES"
    rule_name = "Deliverable Completeness"
    category = "SCOPE"

    def applicability(self, clause: Clause) -> ApplicabilityState:
        if infer_category(clause) == "SCOPE":
            return ApplicabilityState.EVALUATED
        return ApplicabilityState.SKIPPED_MISSING_INPUTS

    def evaluate(self, clause: Clause) -> Finding | None:
        s = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=s.raw_data) if s else None

    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        if clause.data.get("category") not in ("SCOPE", "scope", None):
            return None
        deliverables = clause.data.get("deliverables", [])
        if isinstance(deliverables, list) and len(deliverables) > 0:
            return None
        # Only flag if the text mentions work/deliverables
        text_lower = (clause.text or "").lower()
        if any(kw in text_lower for kw in ("entregable", "deliverable", "alcance", "scope", "trabajos", "works")):
            return _signal(self, clause, 0.40,
                "Scope clause mentions deliverables without structured definition",
                {"has_text": True, "has_structured_deliverables": False})
        return None


# ═══════════════════════════════════════════════════════════════
#  CROSS-DIMENSIONAL (DET-CRS-*)
#  These catch mismatches BETWEEN the tridimensional pillars
# ═══════════════════════════════════════════════════════════════

class BudgetVsContractTotalEvaluator(RuleEvaluator):
    """
    DET-CRS-BUDCON — Checks budget_items sum vs contract.total_amount.

    Alias: also exposed as DET-BUD-SUM (see BudgetSumMismatchEvaluator).
    This is the same logic but categorized as CROSS for the subgraph.
    """
    rule_id = "DET-CRS-BUDCON"
    rule_name = "Budget vs Contract Total Alignment"
    category = "BUDGET"  # Primary category

    def __init__(self, config: EvaluatorConfig = DEFAULT_CONFIG):
        self._inner = BudgetSumMismatchEvaluator(config)

    def evaluate(self, clause: Clause) -> Finding | None:
        return self._inner.evaluate(clause)

    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        sig = self._inner.evaluate_v3(clause)
        if sig:
            sig.rule_id = self.rule_id
        return sig


class ScheduleVsBomDeliveryEvaluator(RuleEvaluator):
    """
    DET-CRS-SCHBOM — Checks if BOM required_on_site_date falls within schedule window.

    If a material needs to be on site before the project even starts,
    or after the relevant schedule task ends, that's a cross-dimensional conflict.
    """
    rule_id = "DET-CRS-SCHBOM"
    rule_name = "Schedule vs BOM Delivery Alignment"
    category = "TECHNICAL"

    def evaluate(self, clause: Clause) -> Finding | None:
        s = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=s.raw_data) if s else None

    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        bom_items = clause.data.get("bom_items", [])
        schedule_items = clause.data.get("schedule_items", [])
        if not isinstance(bom_items, list) or not isinstance(schedule_items, list):
            return None
        if not bom_items or not schedule_items:
            return None

        # Get overall schedule window
        all_dates = []
        for si in schedule_items:
            if isinstance(si, dict):
                for dk in ("start_date", "end_date"):
                    d = _parse_date(si.get(dk))
                    if d:
                        all_dates.append(d)
        if not all_dates:
            return None
        schedule_start = min(all_dates)
        schedule_end = max(all_dates)

        out_of_window = []
        for bi in bom_items:
            if not isinstance(bi, dict):
                continue
            needed = _parse_date(bi.get("required_on_site_date"))
            if not needed:
                continue
            if needed < schedule_start or needed > schedule_end:
                out_of_window.append(bi.get("item_name", "unknown"))

        if not out_of_window:
            return None
        ratio = len(out_of_window) / len(bom_items)
        impact = min(0.75, 0.40 + ratio * 0.35)
        return _signal(self, clause, impact,
            f"{len(out_of_window)} BOM items needed outside schedule window ({schedule_start}–{schedule_end})",
            {"out_of_window_items": out_of_window[:10], "schedule_start": str(schedule_start),
             "schedule_end": str(schedule_end)})


class ScopeVsBudgetCoverageEvaluator(RuleEvaluator):
    """
    DET-CRS-SCPBUD — Checks if all scope deliverables have budget coverage.

    A deliverable without a matching budget line = unfunded commitment.
    """
    rule_id = "DET-CRS-SCPBUD"
    rule_name = "Scope vs Budget Coverage"
    category = "SCOPE"

    def applicability(self, clause: Clause) -> ApplicabilityState:
        d = clause.data
        deliverables, budget_items = d.get("deliverables"), d.get("budget_items")
        if (
            isinstance(deliverables, list) and deliverables
            and isinstance(budget_items, list) and budget_items
        ):
            return ApplicabilityState.EVALUATED
        return ApplicabilityState.SKIPPED_MISSING_INPUTS

    def evaluate(self, clause: Clause) -> Finding | None:
        s = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=s.raw_data) if s else None

    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        deliverables = clause.data.get("deliverables", [])
        budget_items = clause.data.get("budget_items", [])
        if not isinstance(deliverables, list) or not isinstance(budget_items, list):
            return None
        if not deliverables or not budget_items:
            return None

        budget_ids = {
            bi.get("id") or bi.get("name", "").lower()
            for bi in budget_items if isinstance(bi, dict)
        }
        unfunded = [
            d.get("name", f"deliverable-{i}")
            for i, d in enumerate(deliverables)
            if isinstance(d, dict) and (d.get("budget_item_id") or d.get("name", "").lower()) not in budget_ids
        ]
        if not unfunded:
            return None
        ratio = len(unfunded) / len(deliverables)
        impact = min(0.75, 0.35 + ratio * 0.4)
        return _signal(self, clause, impact,
            f"{len(unfunded)}/{len(deliverables)} deliverables without budget: {', '.join(unfunded[:5])}",
            {"unfunded": unfunded[:10], "total_deliverables": len(deliverables)})


# ═══════════════════════════════════════════════════════════════
#  REGISTRY
# ═══════════════════════════════════════════════════════════════

def get_all_deterministic_evaluators(
    config: EvaluatorConfig = DEFAULT_CONFIG,
) -> list[RuleEvaluator]:
    """Returns all 27 deterministic evaluators, ready for registry."""
    return [
        # BUDGET (6)
        BudgetOverrunEvaluator(config),
        BudgetContingencyEvaluator(config),
        BudgetLineItemEvaluator(config),
        BudgetSumMismatchEvaluator(config),
        RetentionRateEvaluator(config),
        AdvancePaymentEvaluator(config),
        # TIME (5)
        ScheduleStatusEvaluator(),
        DeadlineOverdueEvaluator(),
        MilestoneGapEvaluator(config),
        PredecessorOverlapEvaluator(),
        ScheduleDurationEvaluator(config),
        # LEGAL (6)
        ContractReviewOverdueEvaluator(config),
        PenaltyCapEvaluator(config),
        NoticePeriodEvaluator(config),
        WarrantyPeriodEvaluator(config),
        PaymentTermEvaluator(config),
        InsuranceExpiryEvaluator(config),
        # TECHNICAL (3)
        BomLeadTimeEvaluator(),
        SpecReferenceEvaluator(),
        BomBudgetLinkEvaluator(),
        # QUALITY (2)
        QualityStandardEvaluator(),
        InspectionFrequencyEvaluator(),
        # SCOPE (2)
        MissingRequiredFieldsEvaluator(),
        ScopeDeliverablesEvaluator(),
        # CROSS-DIMENSIONAL (3)
        BudgetVsContractTotalEvaluator(config),
        ScheduleVsBomDeliveryEvaluator(),
        ScopeVsBudgetCoverageEvaluator(),
    ]

# ═══════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════

def _num(val: Any) -> TypeGuard[int | float]:
    """Check if value is a numeric type (int or float, but not bool)."""
    return isinstance(val, int | float) and not isinstance(val, bool)


def _parse_date(val: Any) -> date | None:
    """Parse various date formats to a date object."""
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        val = val.strip()
        if not val:
            return None
        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00")).date()
        except (ValueError, TypeError):
            pass
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(val, fmt).date()
            except ValueError:
                continue
    return None


def _signal(
    evaluator: RuleEvaluator,
    clause: Clause,
    impact: float,
    evidence: str,
    raw_data: dict[str, Any],
) -> FindingSignal:
    """Factory to create FindingSignal with common defaults."""
    impact = round(min(0.95, max(0.0, impact)), 3)
    return FindingSignal(
        rule_id=evaluator.rule_id,
        clause_id=clause.id,
        impact_score=impact,
        confidence=1.0,
        severity=impact_to_severity(impact),
        category=evaluator.category,
        evidence_summary=evidence,
        quote=clause.text[:200] if clause.text else "",
        raw_data=raw_data,
    )


# Legacy aliases for backward compatibility
ScheduleDelayEvaluator = ScheduleStatusEvaluator
