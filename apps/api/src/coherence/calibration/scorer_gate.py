"""
Scorer-direct acceptance-gate measurement (ADR-009 §G.1, criteria 3-4).

Isolates the SCORING model — the thing the ADR-017 canary actually flips — from
detection. Feeds each golden project's VERIFIED findings into the canonical scorer
(base = clean, conflict = the worst verified alert per category, certainty = 1.0
because the golden is ground truth) and returns the canonical headline, so MAE and
score↔expert correlation can be measured against the expert score with NO LLM call.

Detection recall/FPR (criteria 1-2) is a separate axis measured by the deterministic
comparators + the full-engine harness; this module deliberately does not touch it.

Refers to Suite ID: TS-UA-COH-CALIB-SCORER-GATE-001.
"""
from __future__ import annotations

from typing import Any

from src.coherence.calibration.gemini_adapter import alert_category
from src.coherence.canonical import (
    CategoryScore,
    CategoryScoreInput,
    ConflictInput,
    GlobalScoreInput,
    aggregate_global,
    score_category,
)
from src.coherence.canonical.category import Severity
from src.coherence.domain.v2_constants import DEFAULT_CATEGORY_WEIGHTS
from src.coherence.models import Alert, AlertCategory, Evidence
from src.coherence.scoring import ScoringService

# Clean baseline: golden projects are otherwise-coherent, so a category's score starts
# at 100 and is depressed only by its verified conflict.
CLEAN_BASE = 100.0

_SEVERITY_MAP: dict[str, Severity] = {
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "warning": "low",
    "low": "low",
    "minor": "low",
}
_SEVERITY_RANK: dict[Severity, int] = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _alerts(project: dict[str, Any]) -> list[dict[str, Any]]:
    out = project.get("expected_output")
    alerts = out.get("coherence_alerts", []) if isinstance(out, dict) else []
    return [a for a in alerts if isinstance(a, dict)]


def _category_of(alert: dict[str, Any]) -> str | None:
    category = alert.get("category")
    if isinstance(category, str) and category.strip():
        return category.strip().upper()
    return alert_category(str(alert.get("rule_id", "")))


def _severity_of(alert: dict[str, Any]) -> Severity:
    raw = str(alert.get("severity", "high")).strip().lower()
    return _SEVERITY_MAP.get(raw, "high")


def golden_category_conflicts(project: dict[str, Any]) -> dict[str, ConflictInput]:
    """Worst verified alert per category → a ConflictInput (certainty 1.0 = ground truth)."""
    worst: dict[str, Severity] = {}
    for alert in _alerts(project):
        if alert.get("evidence_verified") is False:
            continue  # explicitly-unverified alerts are excluded from ground truth
        category = _category_of(alert)
        if category is None:
            continue
        severity = _severity_of(alert)
        if category not in worst or _SEVERITY_RANK[severity] > _SEVERITY_RANK[worst[category]]:
            worst[category] = severity
    return {cat: ConflictInput(severity=sev, certainty=1.0) for cat, sev in worst.items()}


def _worst_open(conflicts: dict[str, ConflictInput]) -> Severity | None:
    worst: Severity | None = None
    for conflict in conflicts.values():
        if worst is None or _SEVERITY_RANK[conflict.severity] > _SEVERITY_RANK[worst]:
            worst = conflict.severity
    return worst


def score_golden_project(project: dict[str, Any]) -> float | None:
    """Canonical headline for a golden project, derived from its verified findings."""
    conflicts = golden_category_conflicts(project)
    category_scores: dict[str, CategoryScore] = {
        category: score_category(
            CategoryScoreInput(base=CLEAN_BASE, conflict=conflicts.get(category))
        )
        for category in DEFAULT_CATEGORY_WEIGHTS
    }
    result = aggregate_global(
        GlobalScoreInput(
            category_scores=category_scores,
            category_weights=dict(DEFAULT_CATEGORY_WEIGHTS),
            worst_open_severity=_worst_open(conflicts),
        )
    )
    return result.score


def expert_score(project: dict[str, Any]) -> float | None:
    """Read the expert ground-truth headline, if present."""
    out = project.get("expected_output")
    value = out.get("expert_score") if isinstance(out, dict) else None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


# Golden category → a valid AlertCategory. v1's compute_score is category-independent
# (it deducts on severity + rule only), so this mapping only satisfies the Alert schema.
_GOLDEN_TO_ALERT_CATEGORY: dict[str, AlertCategory] = {
    "SCOPE": "SCOPE",
    "BUDGET": "BUDGET",
    "TIME": "SCHEDULE",
    "TECHNICAL": "TECHNICAL",
    "LEGAL": "LEGAL",
    "QUALITY": "QUALITY",
}
_GOLDEN_EVIDENCE = Evidence(source_clause_id="golden", claim="golden finding", quote="golden finding")


def _golden_alerts(project: dict[str, Any]) -> list[Alert]:
    """Project the verified golden findings into v1 `Alert`s (same set the canonical path sees)."""
    alerts: list[Alert] = []
    for alert in _alerts(project):
        if alert.get("evidence_verified") is False:
            continue
        category = _category_of(alert)
        if category is None:
            continue
        alerts.append(
            Alert(
                rule_id=str(alert.get("rule_id", "GOLDEN")),
                severity=_severity_of(alert),
                category=_GOLDEN_TO_ALERT_CATEGORY.get(category, "general"),
                message="golden finding",
                evidence=_GOLDEN_EVIDENCE,
            )
        )
    return alerts


def v1_score_golden(project: dict[str, Any]) -> float:
    """Legacy v1 (penalty-based) headline for the SAME verified findings.

    The no-regression baseline (§G.1 criterion 5): the canonical scorer must track the
    expert score at least as well as the v1 scorer it replaces.
    """
    return ScoringService().compute_score(_golden_alerts(project))


__all__ = [
    "CLEAN_BASE",
    "expert_score",
    "golden_category_conflicts",
    "score_golden_project",
    "v1_score_golden",
]
