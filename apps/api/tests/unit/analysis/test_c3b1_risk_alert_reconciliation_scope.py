"""TS-UT-C3B1-ALERTS-001 - why C3b-1 does not route RISK alerts through #828.

The canonical AlertGeneratorService (#828/#829/#834) is the ONLY alert identity /
reconciliation system, and C3b-1 must not add a second one. These checks pin the
two facts that make it not applicable to the RISK alerts an approved artifact
materializes, so the limitation stays explicit instead of being papered over:

* its reconciliation set is COHERENCE alerts only, project-wide -- auto-resolving
  through it with RISK findings would resolve human-visible COHERENCE alerts;
* a RISK finding carries no rule id, clause anchor or detector evidence, so its
  fingerprint degenerates to the category: distinct risks would collapse into one.
"""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock
from uuid import uuid4

from src.coherence.alert_generator import AlertGenerator
from src.coherence.services.alerts.generator import AlertGeneratorService
from src.shared_kernel.enums import AlertType


def test_canonical_service_reconciles_coherence_alerts_only() -> None:
    source = inspect.getsource(AlertGeneratorService._load_existing)
    assert "alert_type=AlertType.COHERENCE" in source


def test_risk_findings_have_no_identity_the_canonical_service_can_use() -> None:
    risks = AlertGenerator(project_id=uuid4(), analysis_id=uuid4()).generate_risk_alerts(
        [
            {"title": "Delay penalty exposure", "category": "LEGAL", "description": "a"},
            {"title": "Unlimited liability", "category": "LEGAL", "description": "b"},
        ]
    )
    assert {risk.alert_type for risk in risks} == {AlertType.RISK}
    assert all(r.rule_id is None and r.source_clause_id is None for r in risks)

    service = AlertGeneratorService(repository=AsyncMock())
    fingerprints = {service._fingerprint(risk) for risk in risks}
    # Two different risks -> one identity: reusing it would merge them.
    assert len(fingerprints) == 1
