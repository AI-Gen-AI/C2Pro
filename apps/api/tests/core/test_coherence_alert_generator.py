"""
TS-I6-COH-SVC-001: Coherence alert generator grouping tests.
"""

from uuid import uuid4

from src.coherence.alert_generator import AlertGenerator
from src.coherence.rules_engine.context_rules import CoherenceRuleResult
from src.shared_kernel.enums import AlertSeverity


def test_generator_groups_repeated_r15_findings_into_summary_alert() -> None:
    project_id = uuid4()
    generator = AlertGenerator(project_id=project_id)
    rule_result = CoherenceRuleResult(
        rule_id="R15",
        is_violated=True,
        evidence={
            "unbudgeted_items": ["Concrete", "Steel", "Cables"],
            "source_clause_id": str(uuid4()),
        },
    )

    alerts = generator.generate(rule_result)

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.rule_id == "R15"
    assert alert.severity == AlertSeverity.HIGH
    assert alert.title == "Material sin presupuesto"
    assert "3 items del BOM" in alert.description
    assert alert.alert_metadata["grouped"] is True
    assert alert.alert_metadata["group_size"] == 3
    assert alert.alert_metadata["evidence"]["unbudgeted_items"] == ["Concrete", "Steel", "Cables"]


def test_generator_keeps_single_r15_finding_as_individual_alert() -> None:
    project_id = uuid4()
    generator = AlertGenerator(project_id=project_id)
    rule_result = CoherenceRuleResult(
        rule_id="R15",
        is_violated=True,
        evidence={"unbudgeted_items": ["Concrete"]},
    )

    alerts = generator.generate(rule_result)

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.description == "El item del BOM 'Concrete' no tiene partida presupuestaria asociada."
    assert alert.alert_metadata["grouped"] is False
    assert alert.alert_metadata["group_size"] == 1


def test_generator_groups_repeated_schedule_dependency_findings() -> None:
    project_id = uuid4()
    generator = AlertGenerator(project_id=project_id)
    rule_result = CoherenceRuleResult(
        rule_id="R12",
        is_violated=True,
        evidence={
            "violations": [
                {
                    "successor_name": "Task B",
                    "predecessor_name": "Task A",
                    "successor_id": str(uuid4()),
                    "predecessor_id": str(uuid4()),
                    "successor_start_date": "2026-03-20",
                    "predecessor_end_date": "2026-03-25",
                },
                {
                    "successor_name": "Task D",
                    "predecessor_name": "Task C",
                    "successor_id": str(uuid4()),
                    "predecessor_id": str(uuid4()),
                    "successor_start_date": "2026-03-22",
                    "predecessor_end_date": "2026-03-28",
                },
            ]
        },
    )

    alerts = generator.generate(rule_result)

    assert len(alerts) == 1
    alert = alerts[0]
    assert "2 dependencias de cronograma invalidas" in alert.description
    assert alert.affected_entities["schedule_item_ids"]
    assert len(alert.alert_metadata["evidence"]["violations"]) == 2
