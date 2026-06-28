"""
rules_engine/config.py — Configuration for deterministic evaluators v0.3.

Provides configurable thresholds for all 27 evaluators across 6 categories.
All percentages are expressed as decimals (0.05 = 5%).

Location: apps/api/src/coherence/rules_engine/config.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class EvaluatorConfig:
    """
    Centralized configuration for all deterministic evaluators.

    Thresholds are grouped by category for clarity. All percentage values
    are expressed as decimals (e.g., 0.05 = 5%, 0.15 = 15%).

    Usage:
        config = EvaluatorConfig()  # Use defaults
        config = EvaluatorConfig(budget_overrun_warning_pct=0.10)  # Override
    """

    # ═══════════════════════════════════════════════════════════════
    # BUDGET thresholds
    # ═══════════════════════════════════════════════════════════════

    # DET-BUD-OVERRUN: Budget overrun detection
    budget_overrun_warning_pct: float = 0.05  # 5% triggers warning
    budget_overrun_critical_pct: float = 0.25  # 25% for impact normalization

    # DET-BUD-CONTINGENCY: Contingency reserve adequacy
    budget_contingency_min_pct: float = 0.05  # Below 5% = too low
    budget_contingency_max_pct: float = 0.20  # Above 20% = suspiciously high

    # DET-BUD-LINEITEM: Arithmetic tolerance
    budget_unit_price_tolerance_pct: float = 0.02  # 2% tolerance for rounding

    # DET-BUD-SUM: cross-document budget total reconciliation tolerance
    budget_sum_tolerance_pct: float = 0.01  # 1% tolerance for contract-vs-BOM drift

    # DET-BUD-RETENTION: Retention rate bounds
    retention_min_pct: float = 0.03  # Below 3% = insufficient
    retention_max_pct: float = 0.10  # Above 10% = excessive

    # DET-BUD-ADVANCE: Advance payment risk
    advance_payment_max_pct: float = 0.30  # Above 30% = high risk

    # ═══════════════════════════════════════════════════════════════
    # TIME thresholds
    # ═══════════════════════════════════════════════════════════════

    # DET-TIM-GAP: Milestone gap detection
    schedule_milestone_gap_max_days: int = 90  # Days between milestones

    # DET-TIM-DURATION: Buffer/float requirements
    schedule_buffer_min_days: int = 7  # Minimum buffer days

    # ═══════════════════════════════════════════════════════════════
    # LEGAL thresholds
    # ═══════════════════════════════════════════════════════════════

    # DET-LEG-REVIEW: Contract review staleness
    contract_review_warning_days: int = 365  # 1 year since last review

    # DET-LEG-PENALTY: Penalty clause limits
    penalty_cap_max_pct: float = 0.15  # 15% cumulative cap maximum
    daily_penalty_max_pct: float = 0.001  # 0.1% per day maximum

    # DET-LEG-NOTICE: Notice period bounds
    notice_period_min_days: int = 14  # Below 14 days = too short
    notice_period_max_days: int = 90  # Above 90 days = unusually long

    # DET-LEG-WARRANTY: Warranty period bounds
    warranty_min_months: int = 6  # Below 6 months = inadequate
    warranty_max_months: int = 60  # Above 60 months = excessive

    # DET-LEG-PAYMENT: Payment term limits
    payment_term_max_days: int = 60  # Above 60 days = cash flow risk

    # DET-LEG-INSURANCE: Insurance expiry warning
    insurance_expiry_warning_days: int = 30  # Warning if expires within 30 days

    # ═══════════════════════════════════════════════════════════════
    # TECHNICAL thresholds
    # ═══════════════════════════════════════════════════════════════

    # DET-TEC-LEADTIME: BOM lead time feasibility
    bom_lead_time_safety_margin_days: int = 14  # Minimum days before deadline

    # ═══════════════════════════════════════════════════════════════
    # QUALITY thresholds
    # ═══════════════════════════════════════════════════════════════

    # (Quality evaluators are mostly text-based, no numeric thresholds needed)

    # ═══════════════════════════════════════════════════════════════
    # SCOPE thresholds
    # ═══════════════════════════════════════════════════════════════

    # Category-specific required fields (defined per-evaluator, not here)

    # ═══════════════════════════════════════════════════════════════
    # LLM semantic evaluator thresholds
    # ═══════════════════════════════════════════════════════════════

    # R-* qualitative rules: drop weak/uncertain findings so headings and
    # marginal concerns do not flood scoring. Deterministic rules are unaffected.
    llm_min_impact: float = 0.30
    llm_min_confidence: float = 0.60


# Default configuration instance
DEFAULT_CONFIG = EvaluatorConfig()


def get_config(**overrides: Any) -> EvaluatorConfig:
    """
    Get an EvaluatorConfig with optional overrides.

    Args:
        **overrides: Any EvaluatorConfig field to override

    Returns:
        EvaluatorConfig with defaults and overrides applied

    Example:
        config = get_config(budget_overrun_warning_pct=0.10)
    """
    return EvaluatorConfig(**overrides)
