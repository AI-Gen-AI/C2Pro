"""
Coherence alert entity and mapping tests (TDD - RED phase).

Refers to Suite ID: TS-UD-COH-ALR-001.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.coherence.domain.alert_mapping import (
    AlertCategory,
    AlertSeverity,
    CoherenceAlert,
    CoherenceAlertMapper,
)


class TestAlertEntityAndMapping:
    """Refers to Suite ID: TS-UD-COH-ALR-001"""

    def test_001_alert_entity_creation_with_all_fields(self) -> None:
        alert = CoherenceAlert.model_validate(
            {
                "rule_id": "R11",
                "title": "WBS without activities",
                "message": "Level 4 WBS lacks linked activities",
                "severity": AlertSeverity.HIGH,
                "category": AlertCategory.SCOPE,
                "affected_entities": ["wbs-1", "wbs-2"],
            }
        )
        assert alert.rule_id == "R11"
        assert alert.category == AlertCategory.SCOPE

    def test_002_alert_entity_creation_minimum_fields(self) -> None:
        alert = CoherenceAlert.model_validate(
            {
                "rule_id": "R6",
                "title": "Budget deviation",
                "message": "Deviation greater than threshold",
                "severity": AlertSeverity.HIGH,
                "category": AlertCategory.BUDGET,
            }
        )
        assert alert.affected_entities == []

    def test_003_alert_entity_fails_without_rule_id(self) -> None:
        with pytest.raises(ValidationError):
            CoherenceAlert.model_validate(
                {
                    "title": "Missing rule id",
                    "message": "Invalid",
                    "severity": AlertSeverity.LOW,
                    "category": AlertCategory.LEGAL,
                }
            )

    def test_004_mapping_scope_rule_r11(self) -> None:
        assert CoherenceAlertMapper.category_for_rule("R11") == AlertCategory.SCOPE

    def test_005_mapping_budget_rule_r6(self) -> None:
        assert CoherenceAlertMapper.category_for_rule("R6") == AlertCategory.BUDGET

    def test_006_mapping_time_rule_r2(self) -> None:
        assert CoherenceAlertMapper.category_for_rule("R2") == AlertCategory.TIME

    def test_007_mapping_technical_rule_r3(self) -> None:
        assert CoherenceAlertMapper.category_for_rule("R3") == AlertCategory.TECHNICAL

    def test_008_mapping_legal_rule_r8(self) -> None:
        assert CoherenceAlertMapper.category_for_rule("R8") == AlertCategory.LEGAL

    def test_009_mapping_quality_rule_r17(self) -> None:
        assert CoherenceAlertMapper.category_for_rule("R17") == AlertCategory.QUALITY

    def test_010_mapping_unknown_rule_to_unknown_category(self) -> None:
        assert CoherenceAlertMapper.category_for_rule("R999") == AlertCategory.UNKNOWN

    def test_011_mapping_rule_to_default_severity(self) -> None:
        assert CoherenceAlertMapper.severity_for_rule("R14") == AlertSeverity.CRITICAL
        assert CoherenceAlertMapper.severity_for_rule("R11") == AlertSeverity.MEDIUM

    def test_012_build_alert_from_rule_uses_mapping_defaults(self) -> None:
        alert = CoherenceAlertMapper.build_alert(
            rule_id="R8",
            message="Penalty clause without milestone",
            affected_entities=["clause-1"],
        )
        assert alert.title == "Alert R8"
        assert alert.category == AlertCategory.LEGAL
        assert alert.severity == AlertSeverity.HIGH
