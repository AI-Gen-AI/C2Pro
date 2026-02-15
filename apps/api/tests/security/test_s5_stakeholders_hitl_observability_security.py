"""
Security tests for S5 controls across stakeholders, HITL, and observability.
Test Suite ID: TS-SEC-S5-001
"""

from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.modules.extraction.domain.entities import ExtractedClause
from src.modules.hitl.application.ports import HumanInTheLoopService, NotificationService, ReviewQueueRepository
from src.modules.hitl.domain.entities import ImpactLevel, ReviewItem, ReviewStatus
from src.modules.hitl.domain.services import ConfidenceRouter
from src.modules.observability.application.ports import EvaluationHarness, LangSmithAdapter
from src.modules.observability.domain.entities import DriftAlarmConfig
from src.modules.stakeholders.application.ports import RACIInferenceService, StakeholderRepository
from src.modules.stakeholders.domain.entities import PartyResolutionResult
from src.modules.stakeholders.domain.services import RACIValidator, StakeholderResolver


@pytest.mark.asyncio
async def test_s5_i10_ambiguous_stakeholder_mapping_is_flagged_for_human_validation() -> None:
    """TS-SEC-S5-001 - Ambiguous stakeholder identity must be escalated, not silently merged."""
    llm = AsyncMock()
    llm.generate_structured_output.return_value = {
        "raci_activities": [
            {
                "activity_id": str(uuid4()),
                "description": "Approve contractual variation order.",
                "responsibilities": [{"stakeholder_name": "Ambiguous Party", "role": "Responsible"}],
                "confidence": 0.9,
            }
        ]
    }
    repo = AsyncMock(spec=StakeholderRepository)
    repo.get_all_stakeholders.return_value = []
    resolver = MagicMock(spec=StakeholderResolver)
    resolver.resolve_entity.return_value = PartyResolutionResult(
        original_name="Ambiguous Party",
        resolved_stakeholder_id=None,
        canonical_id=uuid4(),
        ambiguity_flag=True,
        action="new_with_canonical",
        warning_message="name collision",
    )
    validator = MagicMock(spec=RACIValidator)
    validator.validate_activity_raci.return_value = []

    service = RACIInferenceService(
        llm_generator=llm,
        stakeholder_repo=repo,
        stakeholder_resolver=resolver,
        raci_validator=validator,
    )
    clauses = [
        ExtractedClause(
            clause_id=uuid4(),
            document_id=uuid4(),
            version_id=uuid4(),
            chunk_id=uuid4(),
            text="Ambiguous stakeholder must approve scope changes.",
            type="Governance",
            modality="Shall",
            due_date=date(2026, 10, 1),
            penalty_linkage=None,
            confidence=0.95,
            ambiguity_flag=False,
            actors=["Ambiguous Party"],
            metadata={},
        )
    ]

    matrix, ambiguities = await service.generate_raci_matrix(clauses, tenant_id=uuid4(), project_id=uuid4())

    assert len(ambiguities) == 1
    assert matrix[0].metadata.get("requires_pmo_legal_validation") is True


@pytest.mark.asyncio
async def test_s5_i11_release_enforces_explicit_reviewer_metadata() -> None:
    """TS-SEC-S5-001 - Approved outputs without reviewer metadata must never be releasable."""
    repo = AsyncMock(spec=ReviewQueueRepository)
    notifications = AsyncMock(spec=NotificationService)
    item = ReviewItem(
        item_id=uuid4(),
        item_type="CoherenceAlert",
        current_status=ReviewStatus.APPROVED,
        confidence=0.9,
        impact_level=ImpactLevel.HIGH,
        created_at=datetime.now() - timedelta(hours=2),
        sla_due_date=datetime.now() + timedelta(days=1),
        approved_by=None,
        approved_at=None,
        item_data={},
    )
    repo.get_review_item.return_value = item
    service = HumanInTheLoopService(
        review_queue_repo=repo,
        notification_service=notifications,
        confidence_router=ConfidenceRouter(),
    )

    with pytest.raises(ValueError, match="Approved item missing explicit reviewer information."):
        await service.release_item(item.item_id)


@pytest.mark.asyncio
async def test_s5_i12_trace_payload_is_sanitized_before_run_creation() -> None:
    """TS-SEC-S5-001 - Sensitive fields must be redacted in observability payloads."""
    class _MockRun:
        def __init__(self) -> None:
            self.id = uuid4()
            self.parent_run_id = None
            self.name = ""
            self.run_type = ""
            self.inputs = None
            self.outputs = None
            self.error = None
            self.end_time = None
            self.extra_attrs = {}

        def end(self, outputs=None, error=None, **kwargs):
            self.outputs = outputs
            self.error = error
            self.extra_attrs.update(kwargs)

    class _MockClient:
        def __init__(self) -> None:
            self.last_run = None

        def create_run(self, name, run_type, inputs, parent_run_id=None, **kwargs):
            run = _MockRun()
            run.name = name
            run.run_type = run_type
            run.parent_run_id = parent_run_id
            run.inputs = inputs
            run.extra_attrs = kwargs
            self.last_run = run
            return run

        def update_run(self, run, **kwargs):
            return None

    client = _MockClient()
    adapter = LangSmithAdapter(langsmith_client=client)

    await adapter.start_run(
        name="secure_trace",
        run_type="chain",
        inputs={"token": "top-secret", "nested": {"password": "abc", "value": 1}},
        metadata={"api_key": "secret-key", "tenant_id": "tenant-a"},
    )

    assert client.last_run is not None
    assert client.last_run.inputs["token"] == "[REDACTED]"
    assert client.last_run.inputs["nested"]["password"] == "[REDACTED]"
    assert client.last_run.extra_attrs["metadata"]["api_key"] == "[REDACTED]"
    assert client.last_run.extra_attrs["metadata"]["tenant_id"] == "tenant-a"


@pytest.mark.asyncio
async def test_s5_i12_drift_escalation_only_triggers_on_true_drift() -> None:
    """TS-SEC-S5-001 - Escalation path must trigger only when configured drift criteria are met."""
    adapter = AsyncMock(spec=LangSmithAdapter)
    adapter.get_dataset_eval_metrics.return_value = {
        "recent_metrics": {"recall": 0.91},
        "baseline_metrics": {"recall": 0.90},
    }
    notifications = AsyncMock()
    harness = EvaluationHarness(langsmith_adapter=adapter, notification_service=notifications)

    alerts = await harness.check_drift(
        dataset_name="eval_dataset",
        alarm_configs=[
            DriftAlarmConfig(
                metric_name="recall",
                threshold_percentage_drop=0.05,
                min_absolute_value=0.80,
                escalation_target_email="ops@c2pro.ai",
            )
        ],
    )

    assert alerts == []
    notifications.send_escalation_alert.assert_not_called()

