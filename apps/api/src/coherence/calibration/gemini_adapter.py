"""
Adapter: Gemini's golden schema → engine inputs + expert findings (ADR-009 §G).

Bridges the Gemini calibration dataset (`project_metadata` / `input_documents` /
`expected_output.coherence_alerts`) to (a) the engine's cross-document inputs and (b) a
`GoldenProject`, so the metric gate measures REAL engine accuracy over the corpus rather
than the dataset just self-validating.

Tolerant to Gemini's multi-currency and JV sub-budget key variants (e.g. a joint venture
carries the whole contract total plus each partner's share — both are legitimate, and the
gap between them is a real incoherence to flag WITH its JV explanation).

Refers to Suite ID: TS-UA-COH-CALIB-GEMINI-ADAPTER-001.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

from src.coherence.calibration.golden import GoldenFinding, GoldenProject
from src.coherence.cross_document import ProjectCrossDocInputs

# Gemini uses ad-hoc alert rule_id prefixes; map them to our 6 coherence categories.
_ALERT_PREFIX_TO_CATEGORY: dict[str, str] = {
    "BUD": "BUDGET",
    "FIN": "BUDGET",
    "SCH": "TIME",
    "TIM": "TIME",
    "LEG": "LEGAL",
    "CTR": "LEGAL",
    "TEC": "TECHNICAL",
    "QUA": "QUALITY",
    "SCP": "SCOPE",
    "LOC": "SCOPE",
}
_VALID_SEVERITIES = {"low", "medium", "high", "critical"}
_VALID_CATEGORIES = {"SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY"}

_CONTRACT_KEYS = ("total_value_eur", "total_value_kwd", "total_value_usd", "total_value", "contract_total")
_BUDGET_KEYS = (
    "budget_total_eur", "budget_total_kwd", "budget_total_usd", "budget_total",
    "inabensa_sub_budget_total_eur",  # JV partner share — a legitimate second figure
)
_CONTINGENCY_KEYS = ("contingency_usd", "contingency_eur", "contingency_kwd", "contingency")
_MONEY_RE = re.compile(r"[$€£]\s*([\d][\d,]*(?:\.\d+)?)")


def _max_money(text: str) -> float | None:
    """Largest monetary amount in free text (e.g. a risk-analysis narrative), or None."""
    values: list[float] = []
    for raw in _MONEY_RE.findall(text):
        try:
            values.append(float(raw.replace(",", "")))
        except ValueError:
            continue
    return max(values) if values else None


_ES_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}
_EN_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}
_ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_ES_DATE_RE = re.compile(r"\b(\d{1,2})\s+de\s+([a-zñáéíóú]+)\s+de\s+(\d{4})\b", re.IGNORECASE)
_EN_DATE_RE = re.compile(r"\b([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})\b")


def _parse_deadline(text: str) -> str | None:
    """Parse the first date in free text (ISO / Spanish / English) into an ISO string."""
    iso = _ISO_DATE_RE.search(text)
    if iso:
        try:
            return date(int(iso[1]), int(iso[2]), int(iso[3])).isoformat()
        except ValueError:
            pass
    spanish = _ES_DATE_RE.search(text)
    if spanish and spanish[2].lower() in _ES_MONTHS:
        try:
            return date(int(spanish[3]), _ES_MONTHS[spanish[2].lower()], int(spanish[1])).isoformat()
        except ValueError:
            pass
    english = _EN_DATE_RE.search(text)
    if english and english[1].lower() in _EN_MONTHS:
        try:
            return date(int(english[3]), _EN_MONTHS[english[1].lower()], int(english[2])).isoformat()
        except ValueError:
            pass
    return None


def _num(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _first_num(data: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = _num(data.get(key))
        if value is not None:
            return value
    return None


def alert_category(rule_id: str) -> str | None:
    """Map a Gemini alert rule_id (e.g. 'LEG-KWT-01') to a coherence category, or None."""
    prefix = str(rule_id).split("-", 1)[0].upper()
    return _ALERT_PREFIX_TO_CATEGORY.get(prefix)


def _category_of(alert: dict[str, Any]) -> str | None:
    """Prefer the explicit normalized `category`; fall back to the rule_id prefix."""
    explicit = alert.get("category")
    if isinstance(explicit, str) and explicit.strip().upper() in _VALID_CATEGORIES:
        return explicit.strip().upper()
    return alert_category(str(alert.get("rule_id", "")))


def gemini_budget_inputs(gemini: dict[str, Any]) -> ProjectCrossDocInputs:
    """Assemble cross-document inputs (budget, contingency, risk, schedule) from a Gemini project."""
    documents = gemini.get("input_documents") or {}
    budget_summary = documents.get("budget_summary") or {}
    schedule_summary = documents.get("schedule_summary") or {}
    risk_text = documents.get("risk_analysis_text")
    contract_text = documents.get("contract_text")
    schedule_end = schedule_summary.get("project_end_date") if isinstance(schedule_summary, dict) else None
    return ProjectCrossDocInputs(
        contract_total=_first_num(budget_summary, _CONTRACT_KEYS),
        budget_total=_first_num(budget_summary, _BUDGET_KEYS),
        contingency=_first_num(budget_summary, _CONTINGENCY_KEYS),
        max_risk_exposure=_max_money(risk_text) if isinstance(risk_text, str) else None,
        contract_deadline=_parse_deadline(contract_text) if isinstance(contract_text, str) else None,
        schedule_end=schedule_end if isinstance(schedule_end, str) else None,
    )


def gemini_expected_categories(gemini: dict[str, Any]) -> frozenset[str]:
    """Categories the expert `coherence_alerts` are about (mapped from rule_id prefixes)."""
    alerts = (gemini.get("expected_output") or {}).get("coherence_alerts") or []
    categories: set[str] = set()
    for alert in alerts:
        if isinstance(alert, dict):
            category = _category_of(alert)
            if category is not None:
                categories.add(category)
    return frozenset(categories)


def gemini_to_golden_project(gemini: dict[str, Any]) -> GoldenProject:
    """Build a `GoldenProject` from a Gemini project's expected coherence alerts."""
    metadata = gemini.get("project_metadata") or {}
    expected = gemini.get("expected_output") or {}
    findings: list[GoldenFinding] = []
    for alert in expected.get("coherence_alerts") or []:
        if not isinstance(alert, dict):
            continue
        category = _category_of(alert)
        if category is None:
            continue
        severity = str(alert.get("severity", "medium")).lower()
        if severity not in _VALID_SEVERITIES:
            severity = "medium"
        findings.append(GoldenFinding(category=category, severity=severity, is_true_positive=True))
    return GoldenProject(
        project_id=str(metadata.get("id") or gemini.get("id", "")),
        expert_score=_num(expected.get("expert_score")),
        findings=tuple(findings),
    )


__all__ = [
    "alert_category",
    "gemini_budget_inputs",
    "gemini_expected_categories",
    "gemini_to_golden_project",
]
