from __future__ import annotations

from uuid import UUID, uuid4

from src.modules.analysis.models import AlertSeverity
from src.modules.coherence.alert_generator import AlertGenerator
from src.modules.coherence.rules_engine.context_rules import CoherenceRuleResult


def test_alert_generator_maps_rule_result_to_alerts() -> None:
    project_id = uuid4()
    analysis_id = uuid4()
    source_clause_id = uuid4()

    rule_result = CoherenceRuleResult(
        rule_id="R14",
        is_violated=True,
        evidence={
            "severity": "CRITICAL",
            "risks": [
                {
                    "material": "Valve X",
                    "lead_time": 20,
                    "delay_days": 20,
                    "needed_date": "2030-01-10",
                    "source_clause_id": str(source_clause_id),
                }
            ],
        },
    )

    generator = AlertGenerator(project_id=project_id, analysis_id=analysis_id)
    alerts = generator.generate(rule_result)

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.project_id == project_id
    assert alert.analysis_id == analysis_id
    assert alert.rule_id == "R14"
    assert alert.severity == AlertSeverity.CRITICAL
    assert alert.source_clause_id == source_clause_id
    assert "Valve X" in alert.description
