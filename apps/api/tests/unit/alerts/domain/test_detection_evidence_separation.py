from uuid import uuid4

from src.alerts.domain.enums import AlertSeverity, AlertStatus, ApprovalStatus
from src.alerts.domain.models import Alert


def test_manual_evidence_does_not_corrupt_legacy_detector_evidence_dict() -> None:
    alert = Alert(
        id=uuid4(),
        project_id=uuid4(),
        severity=AlertSeverity.MEDIUM,
        category="TIME",
        status=AlertStatus.OPEN,
        approval_status=ApprovalStatus.PENDING,
        rule_id="DET-TIM-GAP",
        title="Schedule gap",
        description="Gap detected",
        alert_metadata={
            "evidence": {
                "source_clause_id": str(uuid4()),
                "claim": "Schedule gap detected",
                "quote": "Milestone B starts 30 days later",
            }
        },
    )

    alert.attach_evidence(
        evidence_type="note",
        content="Planner confirmed the source excerpt",
        source="manual_review",
        added_by=uuid4(),
    )

    assert isinstance(alert.alert_metadata["detection_evidence"], dict)
    assert alert.alert_metadata["detection_evidence"]["claim"] == "Schedule gap detected"
    assert isinstance(alert.alert_metadata["evidence"], list)
    assert len(alert.alert_metadata["evidence"]) == 1
    assert alert.alert_metadata["evidence"][0]["content"] == "Planner confirmed the source excerpt"
