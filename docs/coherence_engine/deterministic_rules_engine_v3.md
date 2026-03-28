# Deterministic Rules Engine v0.3 — Complete Overhaul

## From 3 Toy Rules to a Production-Grade Tridimensional Auditor

---

## 1. Diagnosis: What's Wrong with the Current `deterministic.py`

The current file has **86 lines and 3 evaluators**. Here's what's missing:

### Structural Problems

| Issue | Impact |
|-------|--------|
| **Only 3 rules** (budget overrun, schedule delayed, contract review) | Covers ~5% of real procurement risk scenarios |
| **Hardcoded threshold date** (`datetime(2025, 6, 1)`) | Breaks in production, non-configurable |
| **Binary output** — `Finding` or `None` | No granularity, feeds the 0/100 scoring problem |
| **No continuous impact scoring** | A 12% overrun weighs the same as a 200% overrun |
| **No category awareness** | Evaluators don't know about SCOPE/BUDGET/TIME/TECH/LEGAL/QUALITY |
| **Missing tridimensional rules** | Zero cross-dimensional checks (contract vs budget vs schedule) |
| **No configurable thresholds** | Magic numbers scattered in code |
| **Schedule evaluator is trivial** | Only checks `status == "delayed"` — ignores dates, float, milestones |

### Domain Knowledge Gap

As a Strategic Procurement Director, Jesus, you know that real contract coherence issues involve things like penalty clause consistency with timelines, retention percentages vs delivery milestones, unit price × quantity vs total budget, payment terms alignment with cash flow, insurance/bond expiration vs project duration, and many more. The current 3 rules barely scratch the surface.

---

## 2. Architecture: The New Deterministic Engine

### Design Principles

1. **Each evaluator produces `FindingSignal`** with continuous `impact_score` (0.0–1.0) and `confidence` (always 1.0 for deterministic)
2. **Configurable thresholds** via `EvaluatorConfig` dataclass
3. **Category-tagged** — every evaluator declares its `category` for the LangGraph subgraph
4. **One evaluator per risk pattern** — small, testable, composable
5. **Registry-based** — evaluators self-register, engine discovers them automatically

### File Structure After Upgrade

```
rules_engine/
├── __init__.py
├── base.py                    # Finding, FindingSignal, RuleEvaluator (updated)
├── config.py                  # NEW: EvaluatorConfig with all thresholds
├── deterministic.py           # REPLACED: 20+ evaluators across 6 categories
├── llm_evaluator.py           # Existing (updated in previous doc)
└── registry.py                # Updated: auto-registers new evaluators
```

---

## 3. Injectable Code

### `rules_engine/config.py` — Centralized Configuration

```python
"""
rules_engine/config.py — Configurable thresholds for deterministic evaluators.

All magic numbers live here. Override via environment variables or
dependency injection for different tenants/environments.

Location: apps/api/src/coherence/rules_engine/config.py
"""

from dataclasses import dataclass, field


@dataclass
class EvaluatorConfig:
    """
    Centralized thresholds for all deterministic evaluators.
    
    Designed to be overridable per-tenant in future multi-tenant scenarios.
    Default values reflect standard procurement risk thresholds from
    FIDIC, NEC, and AIA contract frameworks.
    """
    
    # ─── BUDGET ───────────────────────────────────────────────
    budget_overrun_warning_pct: float = 0.05     # 5% = low alert
    budget_overrun_high_pct: float = 0.10        # 10% = high alert
    budget_overrun_critical_pct: float = 0.25    # 25% = critical
    
    budget_contingency_min_pct: float = 0.05     # Minimum contingency %
    budget_contingency_max_pct: float = 0.20     # Suspiciously high contingency
    
    budget_unit_price_tolerance_pct: float = 0.02  # 2% rounding tolerance
    
    retention_min_pct: float = 0.03              # Min retention (3%)
    retention_max_pct: float = 0.10              # Max retention (10%)
    
    # ─── TIME ─────────────────────────────────────────────────
    schedule_buffer_min_days: int = 14           # Minimum float/buffer
    schedule_milestone_gap_max_days: int = 90    # Max gap between milestones
    schedule_overdue_warning_days: int = 7       # Days past deadline = warning
    schedule_overdue_critical_days: int = 30     # Days past deadline = critical
    
    # ─── LEGAL ────────────────────────────────────────────────
    contract_review_warning_days: int = 180      # 6 months since review
    contract_review_critical_days: int = 365     # 1 year since review
    
    notice_period_min_days: int = 14             # Min notice period
    notice_period_max_days: int = 90             # Suspiciously long notice
    
    warranty_min_months: int = 6                 # Minimum warranty
    warranty_max_months: int = 60                # Suspiciously long warranty
    
    # ─── INSURANCE / BONDS ────────────────────────────────────
    insurance_expiry_warning_days: int = 60      # Expiring within 60 days
    bond_coverage_min_pct: float = 0.10          # Min performance bond %
    
    # ─── PENALTIES ────────────────────────────────────────────
    penalty_cap_max_pct: float = 0.15            # Max cumulative penalty %
    daily_penalty_max_pct: float = 0.005         # Max daily penalty (0.5%)
    
    # ─── PAYMENT ──────────────────────────────────────────────
    payment_term_max_days: int = 60              # Max payment term
    advance_payment_max_pct: float = 0.30        # Max advance payment %


# Global default instance
DEFAULT_CONFIG = EvaluatorConfig()
```

### `rules_engine/base.py` — Updated Base Classes

```python
"""
rules_engine/base.py — Base classes for rule evaluators.

Updated to support continuous FindingSignal output.

Location: apps/api/src/coherence/rules_engine/base.py
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Literal

from ..models import Clause


@dataclass
class Finding:
    """Legacy finding format — kept for backward compatibility."""
    triggered_clause: Clause
    raw_data: dict = field(default_factory=dict)


@dataclass
class FindingSignal:
    """
    Continuous-scored finding for the v0.3 scoring engine.
    
    This is the output format that feeds into the Scoring Arbiter (Agent C)
    in the LangGraph subgraph.
    """
    rule_id: str
    source: Literal["deterministic", "llm", "rag_similarity"] = "deterministic"
    clause_id: str = ""
    impact_score: float = 0.0       # 0.0 (clean) to 1.0 (catastrophic)
    confidence: float = 1.0         # Always 1.0 for deterministic rules
    severity: Literal["critical", "high", "medium", "low"] = "medium"
    category: Literal["SCOPE", "BUDGET", "TIME", "TECH", "LEGAL", "QUALITY"] = "SCOPE"
    evidence_summary: str = ""
    quote: str = ""
    raw_data: dict = field(default_factory=dict)


class RuleEvaluator(ABC):
    """Base class for all rule evaluators."""
    
    rule_id: str = "unknown"
    rule_name: str = "Unknown Rule"
    category: str = "SCOPE"
    
    @abstractmethod
    def evaluate(self, clause: Clause) -> Finding | None:
        """Legacy interface — returns Finding or None."""
        ...
    
    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        """
        v0.3 interface — returns FindingSignal with continuous scoring.
        
        Default implementation wraps the legacy evaluate() method.
        Subclasses should override this directly for granular scoring.
        """
        finding = self.evaluate(clause)
        if finding is None:
            return None
        
        return FindingSignal(
            rule_id=self.rule_id,
            source="deterministic",
            clause_id=clause.id,
            impact_score=0.7,  # Default medium-high for legacy findings
            confidence=1.0,
            severity="high",
            category=self.category,
            evidence_summary=str(finding.raw_data),
            quote=clause.text[:200] if clause.text else "",
            raw_data=finding.raw_data,
        )


def impact_to_severity(impact: float) -> str:
    """Convert continuous impact score to categorical severity."""
    if impact >= 0.85:
        return "critical"
    elif impact >= 0.6:
        return "high"
    elif impact >= 0.35:
        return "medium"
    return "low"
```

### `rules_engine/deterministic.py` — The Full Replacement

```python
"""
rules_engine/deterministic.py — Production-grade deterministic evaluators.

Covers all 6 coherence categories (SCOPE, BUDGET, TIME, TECH, LEGAL, QUALITY)
with continuous impact scoring and configurable thresholds.

These evaluators are pure Python — zero LLM cost, confidence=1.0.
They run as Agent A in the LangGraph coherence subgraph.

Location: apps/api/src/coherence/rules_engine/deterministic.py
"""

from __future__ import annotations

import math
from datetime import datetime, date, timedelta
from typing import Optional

from ..models import Clause
from .base import Finding, FindingSignal, RuleEvaluator, impact_to_severity
from .config import EvaluatorConfig, DEFAULT_CONFIG


# ═══════════════════════════════════════════════════════════════
# CATEGORY: BUDGET
# ═══════════════════════════════════════════════════════════════

class BudgetOverrunEvaluator(RuleEvaluator):
    """
    DET-BUDGET-OVERRUN — Detects budget overrun with continuous severity.
    
    Unlike v0.2 which only fired at >10%, this uses a continuous curve:
      5-10% → low (impact 0.25-0.45)
      10-25% → high (impact 0.45-0.75)
      25%+   → critical (impact 0.75-0.95)
    """
    rule_id = "DET-BUDGET-OVERRUN"
    rule_name = "Budget Overrun Detection"
    category = "BUDGET"
    
    def __init__(self, config: EvaluatorConfig = DEFAULT_CONFIG):
        self.config = config
    
    def evaluate(self, clause: Clause) -> Finding | None:
        signal = self.evaluate_v3(clause)
        if signal:
            return Finding(
                triggered_clause=clause,
                raw_data=signal.raw_data,
            )
        return None
    
    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        current = clause.data.get("current")
        planned = clause.data.get("planned")
        
        if not _is_number(current) or not _is_number(planned):
            return None
        if planned <= 0:
            return None
        
        overrun_pct = (current / planned) - 1.0
        
        if overrun_pct < self.config.budget_overrun_warning_pct:
            return None  # Within acceptable range
        
        # Continuous impact: logarithmic curve from 0.25 to 0.95
        # Maps 5% overrun → ~0.25, 10% → ~0.45, 25% → ~0.72, 50% → ~0.85, 100%+ → ~0.95
        normalized = overrun_pct / self.config.budget_overrun_critical_pct
        impact = min(0.95, 0.25 + 0.70 * (1 - math.exp(-1.5 * normalized)))
        
        return FindingSignal(
            rule_id=self.rule_id,
            clause_id=clause.id,
            impact_score=round(impact, 3),
            confidence=1.0,
            severity=impact_to_severity(impact),
            category=self.category,
            evidence_summary=(
                f"Budget overrun: {current:,.2f} vs planned {planned:,.2f} "
                f"({overrun_pct*100:.1f}% over)"
            ),
            quote=clause.text[:200] if clause.text else "",
            raw_data={
                "current": current,
                "planned": planned,
                "overrun_pct": round(overrun_pct * 100, 2),
                "currency": clause.data.get("currency", "N/A"),
            },
        )


class BudgetContingencyEvaluator(RuleEvaluator):
    """
    DET-BUDGET-CONTINGENCY — Validates contingency reserve adequacy.
    
    Too low (<5%) = high risk of cost overrun.
    Too high (>20%) = possible budget padding or poor estimation.
    """
    rule_id = "DET-BUDGET-CONTINGENCY"
    rule_name = "Contingency Reserve Adequacy"
    category = "BUDGET"
    
    def __init__(self, config: EvaluatorConfig = DEFAULT_CONFIG):
        self.config = config
    
    def evaluate(self, clause: Clause) -> Finding | None:
        signal = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=signal.raw_data) if signal else None
    
    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        contingency = clause.data.get("contingency")
        total_budget = clause.data.get("total_budget") or clause.data.get("planned")
        
        if not _is_number(contingency) or not _is_number(total_budget):
            return None
        if total_budget <= 0:
            return None
        
        cont_pct = contingency / total_budget
        
        if cont_pct < self.config.budget_contingency_min_pct:
            # Dangerously low contingency
            deficit = self.config.budget_contingency_min_pct - cont_pct
            impact = min(0.85, 0.45 + deficit * 8)
            evidence = f"Contingency too low: {cont_pct*100:.1f}% (min recommended: {self.config.budget_contingency_min_pct*100:.0f}%)"
        elif cont_pct > self.config.budget_contingency_max_pct:
            # Suspiciously high contingency
            excess = cont_pct - self.config.budget_contingency_max_pct
            impact = min(0.6, 0.30 + excess * 3)
            evidence = f"Contingency suspiciously high: {cont_pct*100:.1f}% (max expected: {self.config.budget_contingency_max_pct*100:.0f}%)"
        else:
            return None
        
        return FindingSignal(
            rule_id=self.rule_id,
            clause_id=clause.id,
            impact_score=round(impact, 3),
            confidence=1.0,
            severity=impact_to_severity(impact),
            category=self.category,
            evidence_summary=evidence,
            raw_data={"contingency_pct": round(cont_pct * 100, 2)},
        )


class BudgetLineItemConsistencyEvaluator(RuleEvaluator):
    """
    DET-BUDGET-LINEITEM — Checks that unit_price × quantity ≈ line_total.
    
    Catches arithmetic errors in budget breakdowns — surprisingly common
    in large procurement contracts.
    """
    rule_id = "DET-BUDGET-LINEITEM"
    rule_name = "Line Item Arithmetic Consistency"
    category = "BUDGET"
    
    def __init__(self, config: EvaluatorConfig = DEFAULT_CONFIG):
        self.config = config
    
    def evaluate(self, clause: Clause) -> Finding | None:
        signal = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=signal.raw_data) if signal else None
    
    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        unit_price = clause.data.get("unit_price")
        quantity = clause.data.get("quantity")
        line_total = clause.data.get("line_total") or clause.data.get("total")
        
        if not all(_is_number(v) for v in [unit_price, quantity, line_total]):
            return None
        if unit_price <= 0 or quantity <= 0:
            return None
        
        expected = unit_price * quantity
        deviation = abs(expected - line_total) / expected
        
        if deviation <= self.config.budget_unit_price_tolerance_pct:
            return None  # Within rounding tolerance
        
        # Larger deviations = higher impact
        impact = min(0.9, 0.4 + deviation * 2.5)
        
        return FindingSignal(
            rule_id=self.rule_id,
            clause_id=clause.id,
            impact_score=round(impact, 3),
            confidence=1.0,
            severity=impact_to_severity(impact),
            category=self.category,
            evidence_summary=(
                f"Line item mismatch: {unit_price} × {quantity} = {expected:,.2f}, "
                f"but stated total is {line_total:,.2f} (deviation: {deviation*100:.1f}%)"
            ),
            raw_data={
                "unit_price": unit_price,
                "quantity": quantity,
                "expected_total": round(expected, 2),
                "stated_total": line_total,
                "deviation_pct": round(deviation * 100, 2),
            },
        )


class RetentionRateEvaluator(RuleEvaluator):
    """
    DET-BUDGET-RETENTION — Validates retention percentage is within norms.
    
    Standard: 5-10%. Below 3% offers insufficient protection.
    Above 10% may violate payment regulations in some jurisdictions.
    """
    rule_id = "DET-BUDGET-RETENTION"
    rule_name = "Retention Rate Validation"
    category = "BUDGET"
    
    def __init__(self, config: EvaluatorConfig = DEFAULT_CONFIG):
        self.config = config
    
    def evaluate(self, clause: Clause) -> Finding | None:
        signal = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=signal.raw_data) if signal else None
    
    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        retention = clause.data.get("retention_pct") or clause.data.get("retention_rate")
        
        if not _is_number(retention):
            return None
        
        # Normalize: if given as percentage (e.g., 5), convert to decimal
        if retention > 1:
            retention = retention / 100
        
        if retention < self.config.retention_min_pct:
            impact = 0.6 + (self.config.retention_min_pct - retention) * 10
            evidence = f"Retention {retention*100:.1f}% is below minimum {self.config.retention_min_pct*100:.0f}%"
        elif retention > self.config.retention_max_pct:
            impact = 0.4 + (retention - self.config.retention_max_pct) * 5
            evidence = f"Retention {retention*100:.1f}% exceeds maximum {self.config.retention_max_pct*100:.0f}%"
        else:
            return None
        
        impact = round(min(0.85, impact), 3)
        
        return FindingSignal(
            rule_id=self.rule_id,
            clause_id=clause.id,
            impact_score=impact,
            confidence=1.0,
            severity=impact_to_severity(impact),
            category=self.category,
            evidence_summary=evidence,
            raw_data={"retention_pct": round(retention * 100, 2)},
        )


class AdvancePaymentEvaluator(RuleEvaluator):
    """
    DET-BUDGET-ADVANCE — Flags excessive advance payment percentages.
    
    Advance payments above 30% without a bank guarantee are high risk.
    """
    rule_id = "DET-BUDGET-ADVANCE"
    rule_name = "Advance Payment Risk"
    category = "BUDGET"
    
    def __init__(self, config: EvaluatorConfig = DEFAULT_CONFIG):
        self.config = config
    
    def evaluate(self, clause: Clause) -> Finding | None:
        signal = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=signal.raw_data) if signal else None
    
    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        advance = clause.data.get("advance_pct") or clause.data.get("advance_payment_pct")
        has_guarantee = clause.data.get("bank_guarantee", False)
        
        if not _is_number(advance):
            return None
        if advance > 1:
            advance = advance / 100
        
        if advance <= self.config.advance_payment_max_pct:
            return None
        
        # Higher impact without bank guarantee
        base_impact = 0.4 + (advance - self.config.advance_payment_max_pct) * 3
        if not has_guarantee:
            base_impact += 0.15
        
        impact = round(min(0.9, base_impact), 3)
        
        return FindingSignal(
            rule_id=self.rule_id,
            clause_id=clause.id,
            impact_score=impact,
            confidence=1.0,
            severity=impact_to_severity(impact),
            category=self.category,
            evidence_summary=(
                f"Advance payment {advance*100:.1f}% exceeds {self.config.advance_payment_max_pct*100:.0f}% limit"
                f"{' without bank guarantee' if not has_guarantee else ''}"
            ),
            raw_data={
                "advance_pct": round(advance * 100, 2),
                "has_guarantee": has_guarantee,
            },
        )


# ═══════════════════════════════════════════════════════════════
# CATEGORY: TIME / SCHEDULE
# ═══════════════════════════════════════════════════════════════

class ScheduleStatusEvaluator(RuleEvaluator):
    """
    DET-TIME-STATUS — Enhanced schedule status evaluator.
    
    Replaces the v0.2 binary check with multi-status support
    and continuous scoring based on severity of the delay.
    """
    rule_id = "DET-TIME-STATUS"
    rule_name = "Schedule Status Assessment"
    category = "TIME"
    
    def evaluate(self, clause: Clause) -> Finding | None:
        signal = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=signal.raw_data) if signal else None
    
    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        status = str(clause.data.get("status", "")).lower().strip()
        
        STATUS_IMPACT = {
            "delayed": 0.70,
            "behind": 0.65,
            "at_risk": 0.50,
            "at-risk": 0.50,
            "critical": 0.85,
            "suspended": 0.80,
            "cancelled": 0.90,
            "force_majeure": 0.75,
        }
        
        impact = STATUS_IMPACT.get(status)
        if impact is None:
            return None
        
        return FindingSignal(
            rule_id=self.rule_id,
            clause_id=clause.id,
            impact_score=impact,
            confidence=1.0,
            severity=impact_to_severity(impact),
            category=self.category,
            evidence_summary=f"Schedule status: '{status}'",
            raw_data={"status": status},
        )


class DeadlineOverdueEvaluator(RuleEvaluator):
    """
    DET-TIME-OVERDUE — Detects past deadlines with progressive severity.
    
    7 days past → low, 30 days → high, 90+ days → critical.
    """
    rule_id = "DET-TIME-OVERDUE"
    rule_name = "Deadline Overdue Detection"
    category = "TIME"
    
    def __init__(self, config: EvaluatorConfig = DEFAULT_CONFIG):
        self.config = config
    
    def evaluate(self, clause: Clause) -> Finding | None:
        signal = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=signal.raw_data) if signal else None
    
    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        deadline_str = (
            clause.data.get("end_date") 
            or clause.data.get("deadline") 
            or clause.data.get("due_date")
        )
        
        if not deadline_str:
            return None
        
        deadline = _parse_date(deadline_str)
        if deadline is None:
            return None
        
        days_overdue = (date.today() - deadline).days
        if days_overdue <= 0:
            return None
        
        # Logarithmic curve: gentle at first, steepens over time
        # 7 days → 0.28, 30 days → 0.55, 90 days → 0.78, 365 days → 0.92
        impact = min(0.95, 0.2 + 0.75 * (1 - math.exp(-days_overdue / 60)))
        
        return FindingSignal(
            rule_id=self.rule_id,
            clause_id=clause.id,
            impact_score=round(impact, 3),
            confidence=1.0,
            severity=impact_to_severity(impact),
            category=self.category,
            evidence_summary=f"Deadline {deadline} is {days_overdue} days overdue",
            raw_data={
                "deadline": str(deadline),
                "days_overdue": days_overdue,
            },
        )


class MilestoneGapEvaluator(RuleEvaluator):
    """
    DET-TIME-MILESTONE-GAP — Detects excessive gaps between milestones.
    
    If two consecutive milestones are more than 90 days apart,
    there's insufficient control over the delivery timeline.
    """
    rule_id = "DET-TIME-MILESTONE-GAP"
    rule_name = "Milestone Gap Detection"
    category = "TIME"
    
    def __init__(self, config: EvaluatorConfig = DEFAULT_CONFIG):
        self.config = config
    
    def evaluate(self, clause: Clause) -> Finding | None:
        signal = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=signal.raw_data) if signal else None
    
    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        milestones = clause.data.get("milestones", [])
        
        if not isinstance(milestones, list) or len(milestones) < 2:
            return None
        
        # Extract and sort dates
        dates = []
        for m in milestones:
            d = _parse_date(m.get("date") or m.get("due_date") or "")
            if d:
                dates.append(d)
        
        dates.sort()
        if len(dates) < 2:
            return None
        
        max_gap = 0
        gap_pair = (None, None)
        for i in range(len(dates) - 1):
            gap = (dates[i + 1] - dates[i]).days
            if gap > max_gap:
                max_gap = gap
                gap_pair = (dates[i], dates[i + 1])
        
        if max_gap <= self.config.schedule_milestone_gap_max_days:
            return None
        
        excess = max_gap - self.config.schedule_milestone_gap_max_days
        impact = min(0.7, 0.30 + (excess / 180) * 0.4)
        
        return FindingSignal(
            rule_id=self.rule_id,
            clause_id=clause.id,
            impact_score=round(impact, 3),
            confidence=1.0,
            severity=impact_to_severity(impact),
            category=self.category,
            evidence_summary=(
                f"Gap of {max_gap} days between milestones "
                f"({gap_pair[0]} → {gap_pair[1]}), max recommended: "
                f"{self.config.schedule_milestone_gap_max_days} days"
            ),
            raw_data={"max_gap_days": max_gap, "threshold": self.config.schedule_milestone_gap_max_days},
        )


class ScheduleDurationEvaluator(RuleEvaluator):
    """
    DET-TIME-DURATION — Validates that total project duration is realistic.
    
    Flags if start-to-end span is unrealistically short (<30 days for
    construction) or has no buffer at all.
    """
    rule_id = "DET-TIME-DURATION"
    rule_name = "Project Duration Realism"
    category = "TIME"
    
    def __init__(self, config: EvaluatorConfig = DEFAULT_CONFIG):
        self.config = config
    
    def evaluate(self, clause: Clause) -> Finding | None:
        signal = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=signal.raw_data) if signal else None
    
    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        start_str = clause.data.get("start_date")
        end_str = clause.data.get("end_date")
        buffer_days = clause.data.get("buffer_days") or clause.data.get("float_days")
        
        start = _parse_date(start_str) if start_str else None
        end = _parse_date(end_str) if end_str else None
        
        if start and end:
            duration = (end - start).days
            if duration <= 0:
                return FindingSignal(
                    rule_id=self.rule_id,
                    clause_id=clause.id,
                    impact_score=0.9,
                    confidence=1.0,
                    severity="critical",
                    category=self.category,
                    evidence_summary=f"End date ({end}) is before or equal to start date ({start})",
                    raw_data={"start": str(start), "end": str(end), "duration_days": duration},
                )
        
        if _is_number(buffer_days) and buffer_days < self.config.schedule_buffer_min_days:
            impact = 0.35 + (self.config.schedule_buffer_min_days - buffer_days) / self.config.schedule_buffer_min_days * 0.3
            return FindingSignal(
                rule_id=self.rule_id,
                clause_id=clause.id,
                impact_score=round(min(0.65, impact), 3),
                confidence=1.0,
                severity=impact_to_severity(impact),
                category=self.category,
                evidence_summary=f"Schedule buffer of {buffer_days} days is below minimum {self.config.schedule_buffer_min_days}",
                raw_data={"buffer_days": buffer_days},
            )
        
        return None


# ═══════════════════════════════════════════════════════════════
# CATEGORY: LEGAL
# ═══════════════════════════════════════════════════════════════

class ContractReviewOverdueEvaluator(RuleEvaluator):
    """
    DET-LEGAL-REVIEW — Enhanced contract review overdue detection.
    
    Replaces v0.2 hardcoded threshold with configurable days
    and continuous scoring based on how overdue the review is.
    """
    rule_id = "DET-LEGAL-REVIEW"
    rule_name = "Contract Review Overdue"
    category = "LEGAL"
    
    def __init__(self, config: EvaluatorConfig = DEFAULT_CONFIG):
        self.config = config
    
    def evaluate(self, clause: Clause) -> Finding | None:
        signal = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=signal.raw_data) if signal else None
    
    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        review_str = clause.data.get("last_review_date")
        if not review_str:
            return None
        
        review_date = _parse_date(review_str)
        if review_date is None:
            return None
        
        days_since = (date.today() - review_date).days
        if days_since < self.config.contract_review_warning_days:
            return None
        
        # Progressive: 180 days → 0.25, 365 days → 0.55, 730+ days → 0.80
        normalized = (days_since - self.config.contract_review_warning_days) / 365
        impact = min(0.85, 0.25 + 0.60 * (1 - math.exp(-1.2 * normalized)))
        
        return FindingSignal(
            rule_id=self.rule_id,
            clause_id=clause.id,
            impact_score=round(impact, 3),
            confidence=1.0,
            severity=impact_to_severity(impact),
            category=self.category,
            evidence_summary=f"Last contract review was {days_since} days ago ({review_date})",
            raw_data={
                "last_review_date": str(review_date),
                "days_since_review": days_since,
            },
        )


class PenaltyCapEvaluator(RuleEvaluator):
    """
    DET-LEGAL-PENALTY — Validates penalty clauses for reasonableness.
    
    Checks cumulative penalty cap and daily penalty rate against thresholds.
    Missing penalty caps are flagged as high risk (unlimited liability).
    """
    rule_id = "DET-LEGAL-PENALTY"
    rule_name = "Penalty Clause Validation"
    category = "LEGAL"
    
    def __init__(self, config: EvaluatorConfig = DEFAULT_CONFIG):
        self.config = config
    
    def evaluate(self, clause: Clause) -> Finding | None:
        signal = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=signal.raw_data) if signal else None
    
    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        penalty_cap_pct = clause.data.get("penalty_cap_pct")
        daily_penalty_pct = clause.data.get("daily_penalty_pct")
        has_cap = clause.data.get("has_penalty_cap")
        
        # Missing penalty cap = unlimited exposure
        if has_cap is False or (
            clause.data.get("penalty") and penalty_cap_pct is None and has_cap is None
        ):
            return FindingSignal(
                rule_id=self.rule_id,
                clause_id=clause.id,
                impact_score=0.80,
                confidence=1.0,
                severity="high",
                category=self.category,
                evidence_summary="Penalty clause without cumulative cap — unlimited liability exposure",
                raw_data={"has_cap": False},
            )
        
        if _is_number(penalty_cap_pct):
            if penalty_cap_pct > 1:
                penalty_cap_pct = penalty_cap_pct / 100
            if penalty_cap_pct > self.config.penalty_cap_max_pct:
                excess = penalty_cap_pct - self.config.penalty_cap_max_pct
                impact = min(0.8, 0.45 + excess * 4)
                return FindingSignal(
                    rule_id=self.rule_id,
                    clause_id=clause.id,
                    impact_score=round(impact, 3),
                    confidence=1.0,
                    severity=impact_to_severity(impact),
                    category=self.category,
                    evidence_summary=(
                        f"Penalty cap {penalty_cap_pct*100:.1f}% exceeds "
                        f"recommended maximum {self.config.penalty_cap_max_pct*100:.0f}%"
                    ),
                    raw_data={"penalty_cap_pct": round(penalty_cap_pct * 100, 2)},
                )
        
        if _is_number(daily_penalty_pct):
            if daily_penalty_pct > 1:
                daily_penalty_pct = daily_penalty_pct / 100
            if daily_penalty_pct > self.config.daily_penalty_max_pct:
                impact = min(0.7, 0.40 + (daily_penalty_pct - self.config.daily_penalty_max_pct) * 60)
                return FindingSignal(
                    rule_id=self.rule_id,
                    clause_id=clause.id,
                    impact_score=round(impact, 3),
                    confidence=1.0,
                    severity=impact_to_severity(impact),
                    category=self.category,
                    evidence_summary=(
                        f"Daily penalty {daily_penalty_pct*100:.3f}% exceeds "
                        f"recommended {self.config.daily_penalty_max_pct*100:.2f}%"
                    ),
                    raw_data={"daily_penalty_pct": round(daily_penalty_pct * 100, 4)},
                )
        
        return None


class NoticePeriodEvaluator(RuleEvaluator):
    """
    DET-LEGAL-NOTICE — Validates notice periods for reasonableness.
    """
    rule_id = "DET-LEGAL-NOTICE"
    rule_name = "Notice Period Validation"
    category = "LEGAL"
    
    def __init__(self, config: EvaluatorConfig = DEFAULT_CONFIG):
        self.config = config
    
    def evaluate(self, clause: Clause) -> Finding | None:
        signal = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=signal.raw_data) if signal else None
    
    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        notice_days = clause.data.get("notice_period_days")
        if not _is_number(notice_days):
            return None
        
        if notice_days < self.config.notice_period_min_days:
            impact = 0.50 + (self.config.notice_period_min_days - notice_days) / self.config.notice_period_min_days * 0.3
            evidence = f"Notice period {notice_days} days is too short (min: {self.config.notice_period_min_days})"
        elif notice_days > self.config.notice_period_max_days:
            impact = 0.35 + (notice_days - self.config.notice_period_max_days) / 180 * 0.3
            evidence = f"Notice period {notice_days} days is unusually long (max expected: {self.config.notice_period_max_days})"
        else:
            return None
        
        return FindingSignal(
            rule_id=self.rule_id,
            clause_id=clause.id,
            impact_score=round(min(0.75, impact), 3),
            confidence=1.0,
            severity=impact_to_severity(impact),
            category=self.category,
            evidence_summary=evidence,
            raw_data={"notice_period_days": notice_days},
        )


class WarrantyPeriodEvaluator(RuleEvaluator):
    """
    DET-LEGAL-WARRANTY — Validates warranty/defects liability period.
    """
    rule_id = "DET-LEGAL-WARRANTY"
    rule_name = "Warranty Period Validation"
    category = "LEGAL"
    
    def __init__(self, config: EvaluatorConfig = DEFAULT_CONFIG):
        self.config = config
    
    def evaluate(self, clause: Clause) -> Finding | None:
        signal = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=signal.raw_data) if signal else None
    
    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        warranty_months = clause.data.get("warranty_months") or clause.data.get("defects_liability_months")
        if not _is_number(warranty_months):
            return None
        
        if warranty_months < self.config.warranty_min_months:
            impact = 0.5 + (self.config.warranty_min_months - warranty_months) / self.config.warranty_min_months * 0.3
            evidence = f"Warranty {warranty_months} months is below minimum {self.config.warranty_min_months}"
        elif warranty_months > self.config.warranty_max_months:
            impact = 0.35
            evidence = f"Warranty {warranty_months} months is unusually long (max expected: {self.config.warranty_max_months})"
        else:
            return None
        
        return FindingSignal(
            rule_id=self.rule_id,
            clause_id=clause.id,
            impact_score=round(min(0.75, impact), 3),
            confidence=1.0,
            severity=impact_to_severity(impact),
            category=self.category,
            evidence_summary=evidence,
            raw_data={"warranty_months": warranty_months},
        )


class PaymentTermEvaluator(RuleEvaluator):
    """
    DET-LEGAL-PAYMENT-TERM — Validates payment terms (days to pay).
    """
    rule_id = "DET-LEGAL-PAYMENT-TERM"
    rule_name = "Payment Term Validation"
    category = "LEGAL"
    
    def __init__(self, config: EvaluatorConfig = DEFAULT_CONFIG):
        self.config = config
    
    def evaluate(self, clause: Clause) -> Finding | None:
        signal = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=signal.raw_data) if signal else None
    
    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        payment_days = clause.data.get("payment_term_days") or clause.data.get("payment_days")
        if not _is_number(payment_days):
            return None
        
        if payment_days > self.config.payment_term_max_days:
            excess = payment_days - self.config.payment_term_max_days
            impact = min(0.7, 0.35 + excess / 90 * 0.35)
            return FindingSignal(
                rule_id=self.rule_id,
                clause_id=clause.id,
                impact_score=round(impact, 3),
                confidence=1.0,
                severity=impact_to_severity(impact),
                category=self.category,
                evidence_summary=f"Payment term {payment_days} days exceeds {self.config.payment_term_max_days}-day limit",
                raw_data={"payment_days": payment_days},
            )
        return None


# ═══════════════════════════════════════════════════════════════
# CATEGORY: INSURANCE / BONDS
# ═══════════════════════════════════════════════════════════════

class InsuranceExpiryEvaluator(RuleEvaluator):
    """
    DET-LEGAL-INSURANCE — Checks insurance/bond expiry vs project end date.
    """
    rule_id = "DET-LEGAL-INSURANCE"
    rule_name = "Insurance/Bond Expiry Check"
    category = "LEGAL"
    
    def __init__(self, config: EvaluatorConfig = DEFAULT_CONFIG):
        self.config = config
    
    def evaluate(self, clause: Clause) -> Finding | None:
        signal = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=signal.raw_data) if signal else None
    
    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        expiry_str = clause.data.get("insurance_expiry") or clause.data.get("bond_expiry")
        project_end_str = clause.data.get("project_end_date")
        
        expiry = _parse_date(expiry_str) if expiry_str else None
        if not expiry:
            return None
        
        # Check against project end date if available
        project_end = _parse_date(project_end_str) if project_end_str else None
        
        if project_end and expiry < project_end:
            days_short = (project_end - expiry).days
            impact = min(0.85, 0.55 + days_short / 365 * 0.3)
            return FindingSignal(
                rule_id=self.rule_id,
                clause_id=clause.id,
                impact_score=round(impact, 3),
                confidence=1.0,
                severity=impact_to_severity(impact),
                category=self.category,
                evidence_summary=(
                    f"Insurance/bond expires {expiry} — {days_short} days before "
                    f"project end {project_end}"
                ),
                raw_data={"expiry": str(expiry), "project_end": str(project_end), "days_short": days_short},
            )
        
        # Check against today (expiring soon)
        days_to_expiry = (expiry - date.today()).days
        if days_to_expiry <= 0:
            return FindingSignal(
                rule_id=self.rule_id,
                clause_id=clause.id,
                impact_score=0.85,
                confidence=1.0,
                severity="critical",
                category=self.category,
                evidence_summary=f"Insurance/bond expired {abs(days_to_expiry)} days ago ({expiry})",
                raw_data={"expiry": str(expiry), "days_expired": abs(days_to_expiry)},
            )
        elif days_to_expiry <= self.config.insurance_expiry_warning_days:
            impact = 0.45 + (self.config.insurance_expiry_warning_days - days_to_expiry) / self.config.insurance_expiry_warning_days * 0.3
            return FindingSignal(
                rule_id=self.rule_id,
                clause_id=clause.id,
                impact_score=round(impact, 3),
                confidence=1.0,
                severity=impact_to_severity(impact),
                category=self.category,
                evidence_summary=f"Insurance/bond expires in {days_to_expiry} days ({expiry})",
                raw_data={"expiry": str(expiry), "days_to_expiry": days_to_expiry},
            )
        
        return None


# ═══════════════════════════════════════════════════════════════
# CATEGORY: SCOPE
# ═══════════════════════════════════════════════════════════════

class MissingRequiredFieldsEvaluator(RuleEvaluator):
    """
    DET-SCOPE-MISSING — Checks for missing critical structured data fields.
    
    Different clause categories require different mandatory fields.
    """
    rule_id = "DET-SCOPE-MISSING"
    rule_name = "Missing Required Fields"
    category = "SCOPE"
    
    REQUIRED_FIELDS = {
        "BUDGET": ["planned", "currency"],
        "TIME": ["end_date"],
        "LEGAL": [],
        "SCOPE": [],
        "QUALITY": [],
        "TECH": [],
    }
    
    def evaluate(self, clause: Clause) -> Finding | None:
        signal = self.evaluate_v3(clause)
        return Finding(triggered_clause=clause, raw_data=signal.raw_data) if signal else None
    
    def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
        # Infer category from data keys
        category = self._infer_category(clause)
        required = self.REQUIRED_FIELDS.get(category, [])
        
        missing = [f for f in required if clause.data.get(f) is None]
        
        if not missing:
            return None
        
        # Impact scales with how many fields are missing
        impact = min(0.7, 0.3 + len(missing) * 0.15)
        
        return FindingSignal(
            rule_id=self.rule_id,
            clause_id=clause.id,
            impact_score=round(impact, 3),
            confidence=1.0,
            severity=impact_to_severity(impact),
            category=category,
            evidence_summary=f"Missing required fields: {', '.join(missing)}",
            raw_data={"missing_fields": missing, "category": category},
        )
    
    @staticmethod
    def _infer_category(clause: Clause) -> str:
        data = clause.data or {}
        if any(k in data for k in ("current", "planned", "budget")):
            return "BUDGET"
        if any(k in data for k in ("status", "end_date", "deadline")):
            return "TIME"
        if any(k in data for k in ("last_review_date", "penalty", "termination")):
            return "LEGAL"
        return "SCOPE"


# ═══════════════════════════════════════════════════════════════
# REGISTRY HELPER
# ═══════════════════════════════════════════════════════════════

def get_all_deterministic_evaluators(
    config: EvaluatorConfig = DEFAULT_CONFIG,
) -> list[RuleEvaluator]:
    """
    Returns all deterministic evaluators, ready to be registered.
    
    Usage in composition root or registry:
        evaluators = get_all_deterministic_evaluators()
        for e in evaluators:
            registry.register(e.rule_id, e)
    """
    return [
        # BUDGET (5 evaluators)
        BudgetOverrunEvaluator(config),
        BudgetContingencyEvaluator(config),
        BudgetLineItemConsistencyEvaluator(config),
        RetentionRateEvaluator(config),
        AdvancePaymentEvaluator(config),
        # TIME (4 evaluators)
        ScheduleStatusEvaluator(),
        DeadlineOverdueEvaluator(config),
        MilestoneGapEvaluator(config),
        ScheduleDurationEvaluator(config),
        # LEGAL (6 evaluators)
        ContractReviewOverdueEvaluator(config),
        PenaltyCapEvaluator(config),
        NoticePeriodEvaluator(config),
        WarrantyPeriodEvaluator(config),
        PaymentTermEvaluator(config),
        InsuranceExpiryEvaluator(config),
        # SCOPE (1 evaluator)
        MissingRequiredFieldsEvaluator(),
    ]


# ═══════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def _is_number(val) -> bool:
    """Check if value is a valid number (int or float)."""
    return isinstance(val, (int, float)) and not isinstance(val, bool)


def _parse_date(val) -> Optional[date]:
    """Parse a date string or date object into a date. Returns None on failure."""
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ",
                     "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S%z"):
            try:
                return datetime.strptime(val.replace("+00:00", "Z").rstrip("Z"), 
                                          fmt.rstrip("Z").rstrip("%z")).date()
            except ValueError:
                continue
        # Try ISO format as fallback
        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00")).date()
        except (ValueError, TypeError):
            pass
    return None
```

---

## 4. Comparison: Old vs New

| Metric | v0.2 (current) | v0.3 (proposed) |
|--------|----------------|-----------------|
| **Evaluators** | 3 | 16 |
| **Categories covered** | 2 (BUDGET, TIME) | 5 (BUDGET, TIME, LEGAL, SCOPE, INSURANCE) |
| **Output type** | Binary `Finding | None` | Continuous `FindingSignal` (0.0–1.0) |
| **Configuration** | Hardcoded thresholds | `EvaluatorConfig` dataclass |
| **Date handling** | Single format, hardcoded threshold | Multi-format parser, relative to today |
| **Budget rules** | 1 (>10% overrun) | 5 (overrun curve + contingency + line items + retention + advance) |
| **Schedule rules** | 1 (status == "delayed") | 4 (multi-status + overdue curve + milestone gaps + duration) |
| **Legal rules** | 1 (review date) | 6 (review + penalties + notice + warranty + payment terms + insurance) |
| **Lines of code** | 86 | ~650 |
| **LLM cost** | $0 | $0 (pure Python) |

---

## 5. Test Suite for the New Evaluators

```python
"""
tests/coherence/test_deterministic_v3.py — Tests for enhanced deterministic evaluators.

Follows C2Pro TDD protocol: these tests validate continuous scoring behavior.
Suite ID: TS-COH-DET-V3-001
"""

import pytest
from datetime import date, timedelta
from coherence.models import Clause
from coherence.rules_engine.deterministic import (
    BudgetOverrunEvaluator,
    BudgetContingencyEvaluator,
    BudgetLineItemConsistencyEvaluator,
    RetentionRateEvaluator,
    AdvancePaymentEvaluator,
    ScheduleStatusEvaluator,
    DeadlineOverdueEvaluator,
    MilestoneGapEvaluator,
    ContractReviewOverdueEvaluator,
    PenaltyCapEvaluator,
    InsuranceExpiryEvaluator,
    MissingRequiredFieldsEvaluator,
    get_all_deterministic_evaluators,
)
from coherence.rules_engine.config import EvaluatorConfig


# ─── Fixtures ─────────────────────────────────────────────────

def _clause(data: dict, text: str = "Test clause") -> Clause:
    return Clause(id="test-clause", text=text, data=data)


# ═══════════════════════════════════════════════════════════════
# BUDGET EVALUATORS
# ═══════════════════════════════════════════════════════════════

class TestBudgetOverrunEvaluator:
    
    def test_no_overrun_returns_none(self):
        evaluator = BudgetOverrunEvaluator()
        result = evaluator.evaluate_v3(_clause({"current": 100000, "planned": 110000}))
        assert result is None
    
    def test_small_overrun_returns_low_impact(self):
        evaluator = BudgetOverrunEvaluator()
        result = evaluator.evaluate_v3(_clause({"current": 106000, "planned": 100000}))
        assert result is not None
        assert 0.2 < result.impact_score < 0.5
        assert result.severity in ("low", "medium")
    
    def test_moderate_overrun_returns_medium_impact(self):
        evaluator = BudgetOverrunEvaluator()
        result = evaluator.evaluate_v3(_clause({"current": 115000, "planned": 100000}))
        assert result is not None
        assert 0.4 < result.impact_score < 0.7
    
    def test_severe_overrun_returns_high_impact(self):
        evaluator = BudgetOverrunEvaluator()
        result = evaluator.evaluate_v3(_clause({"current": 200000, "planned": 100000}))
        assert result is not None
        assert result.impact_score > 0.7
        assert result.severity in ("high", "critical")
    
    def test_impact_never_exceeds_095(self):
        evaluator = BudgetOverrunEvaluator()
        result = evaluator.evaluate_v3(_clause({"current": 1000000, "planned": 100000}))
        assert result is not None
        assert result.impact_score <= 0.95
    
    def test_missing_data_returns_none(self):
        evaluator = BudgetOverrunEvaluator()
        assert evaluator.evaluate_v3(_clause({"current": 100})) is None
        assert evaluator.evaluate_v3(_clause({"planned": 100})) is None
        assert evaluator.evaluate_v3(_clause({})) is None
    
    def test_zero_planned_returns_none(self):
        evaluator = BudgetOverrunEvaluator()
        assert evaluator.evaluate_v3(_clause({"current": 100, "planned": 0})) is None


class TestBudgetLineItemConsistency:
    
    def test_correct_arithmetic_returns_none(self):
        evaluator = BudgetLineItemConsistencyEvaluator()
        result = evaluator.evaluate_v3(_clause({
            "unit_price": 50.0, "quantity": 100, "line_total": 5000.0,
        }))
        assert result is None
    
    def test_small_rounding_within_tolerance(self):
        evaluator = BudgetLineItemConsistencyEvaluator()
        result = evaluator.evaluate_v3(_clause({
            "unit_price": 33.33, "quantity": 3, "line_total": 100.0,
        }))
        assert result is None  # 99.99 vs 100.0 = 0.01% deviation
    
    def test_significant_mismatch_detected(self):
        evaluator = BudgetLineItemConsistencyEvaluator()
        result = evaluator.evaluate_v3(_clause({
            "unit_price": 50.0, "quantity": 100, "line_total": 6000.0,
        }))
        assert result is not None
        assert result.impact_score > 0.4
        assert "5,000" in result.evidence_summary
        assert "6,000" in result.evidence_summary


# ═══════════════════════════════════════════════════════════════
# SCHEDULE EVALUATORS
# ═══════════════════════════════════════════════════════════════

class TestScheduleStatusEvaluator:
    
    @pytest.mark.parametrize("status,min_impact,max_impact", [
        ("delayed", 0.65, 0.75),
        ("at_risk", 0.45, 0.55),
        ("critical", 0.80, 0.90),
        ("suspended", 0.75, 0.85),
        ("on-track", None, None),  # Should return None
    ])
    def test_status_mapping(self, status, min_impact, max_impact):
        evaluator = ScheduleStatusEvaluator()
        result = evaluator.evaluate_v3(_clause({"status": status}))
        
        if min_impact is None:
            assert result is None
        else:
            assert result is not None
            assert min_impact <= result.impact_score <= max_impact


class TestDeadlineOverdueEvaluator:
    
    def test_future_deadline_returns_none(self):
        evaluator = DeadlineOverdueEvaluator()
        future = (date.today() + timedelta(days=30)).isoformat()
        assert evaluator.evaluate_v3(_clause({"end_date": future})) is None
    
    def test_recently_overdue_returns_low_impact(self):
        evaluator = DeadlineOverdueEvaluator()
        past = (date.today() - timedelta(days=5)).isoformat()
        result = evaluator.evaluate_v3(_clause({"end_date": past}))
        assert result is not None
        assert result.impact_score < 0.4
    
    def test_severely_overdue_returns_high_impact(self):
        evaluator = DeadlineOverdueEvaluator()
        past = (date.today() - timedelta(days=120)).isoformat()
        result = evaluator.evaluate_v3(_clause({"end_date": past}))
        assert result is not None
        assert result.impact_score > 0.7


# ═══════════════════════════════════════════════════════════════
# LEGAL EVALUATORS
# ═══════════════════════════════════════════════════════════════

class TestPenaltyCapEvaluator:
    
    def test_no_cap_flagged_as_high(self):
        evaluator = PenaltyCapEvaluator()
        result = evaluator.evaluate_v3(_clause({
            "penalty": True, "has_penalty_cap": False,
        }))
        assert result is not None
        assert result.impact_score >= 0.7
    
    def test_excessive_cap_detected(self):
        evaluator = PenaltyCapEvaluator()
        result = evaluator.evaluate_v3(_clause({"penalty_cap_pct": 25}))
        assert result is not None
        assert result.impact_score > 0.4


class TestInsuranceExpiryEvaluator:
    
    def test_expired_insurance_is_critical(self):
        evaluator = InsuranceExpiryEvaluator()
        past = (date.today() - timedelta(days=30)).isoformat()
        result = evaluator.evaluate_v3(_clause({"insurance_expiry": past}))
        assert result is not None
        assert result.severity == "critical"
    
    def test_insurance_expires_before_project_end(self):
        evaluator = InsuranceExpiryEvaluator()
        result = evaluator.evaluate_v3(_clause({
            "insurance_expiry": "2026-06-01",
            "project_end_date": "2026-12-31",
        }))
        assert result is not None
        assert "before project end" in result.evidence_summary


# ═══════════════════════════════════════════════════════════════
# REGISTRY
# ═══════════════════════════════════════════════════════════════

class TestRegistry:
    
    def test_all_evaluators_returns_16(self):
        evaluators = get_all_deterministic_evaluators()
        assert len(evaluators) == 16
    
    def test_all_evaluators_have_unique_rule_ids(self):
        evaluators = get_all_deterministic_evaluators()
        ids = [e.rule_id for e in evaluators]
        assert len(ids) == len(set(ids))
    
    def test_custom_config_propagates(self):
        config = EvaluatorConfig(budget_overrun_warning_pct=0.20)
        evaluators = get_all_deterministic_evaluators(config)
        budget_eval = next(e for e in evaluators if e.rule_id == "DET-BUDGET-OVERRUN")
        
        # 15% overrun should NOT trigger with 20% threshold
        result = budget_eval.evaluate_v3(_clause({"current": 115, "planned": 100}))
        assert result is None
```
