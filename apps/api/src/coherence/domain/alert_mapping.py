"""
Coherence alert entity and deterministic mapping.

Refers to Suite ID: TS-UD-COH-ALR-001.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class AlertCategory(str, Enum):
    SCOPE = "SCOPE"
    BUDGET = "BUDGET"
    TIME = "TIME"
    TECHNICAL = "TECHNICAL"
    LEGAL = "LEGAL"
    QUALITY = "QUALITY"
    UNKNOWN = "UNKNOWN"


class AlertSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CoherenceAlert(BaseModel):
    rule_id: str
    title: str
    message: str
    severity: AlertSeverity
    category: AlertCategory
    affected_entities: list[str] = Field(default_factory=list)


class CoherenceAlertMapper:
    """Maps coherence rule IDs to default alert category and severity."""

    _CATEGORY_BY_RULE: dict[str, AlertCategory] = {
        "R11": AlertCategory.SCOPE,
        "R12": AlertCategory.SCOPE,
        "R13": AlertCategory.SCOPE,
        "R6": AlertCategory.BUDGET,
        "R15": AlertCategory.BUDGET,
        "R16": AlertCategory.BUDGET,
        "R2": AlertCategory.TIME,
        "R5": AlertCategory.TIME,
        "R14": AlertCategory.TIME,
        "R3": AlertCategory.TECHNICAL,
        "R4": AlertCategory.TECHNICAL,
        "R7": AlertCategory.TECHNICAL,
        "R8": AlertCategory.LEGAL,
        "R20": AlertCategory.LEGAL,
        "R17": AlertCategory.QUALITY,
        "R18": AlertCategory.QUALITY,
    }

    _SEVERITY_BY_RULE: dict[str, AlertSeverity] = {
        "R14": AlertSeverity.CRITICAL,
        "R11": AlertSeverity.MEDIUM,
        "R12": AlertSeverity.HIGH,
        "R13": AlertSeverity.HIGH,
        "R6": AlertSeverity.HIGH,
        "R15": AlertSeverity.HIGH,
        "R16": AlertSeverity.HIGH,
        "R2": AlertSeverity.MEDIUM,
        "R5": AlertSeverity.HIGH,
        "R3": AlertSeverity.HIGH,
        "R4": AlertSeverity.MEDIUM,
        "R7": AlertSeverity.MEDIUM,
        "R8": AlertSeverity.HIGH,
        "R20": AlertSeverity.HIGH,
        "R17": AlertSeverity.HIGH,
        "R18": AlertSeverity.HIGH,
    }

    @classmethod
    def category_for_rule(cls, rule_id: str) -> AlertCategory:
        return cls._CATEGORY_BY_RULE.get(rule_id, AlertCategory.UNKNOWN)

    @classmethod
    def severity_for_rule(cls, rule_id: str) -> AlertSeverity:
        return cls._SEVERITY_BY_RULE.get(rule_id, AlertSeverity.LOW)

    @classmethod
    def build_alert(
        cls,
        rule_id: str,
        message: str,
        affected_entities: list[str] | None = None,
    ) -> CoherenceAlert:
        return CoherenceAlert(
            rule_id=rule_id,
            title=f"Alert {rule_id}",
            message=message,
            severity=cls.severity_for_rule(rule_id),
            category=cls.category_for_rule(rule_id),
            affected_entities=affected_entities or [],
        )
