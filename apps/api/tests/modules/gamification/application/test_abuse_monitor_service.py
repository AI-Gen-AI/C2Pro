"""TS-UC-SEC-GAM-001: Gamification Abuse Monitor — tenant-scoped security tests."""

import time
from typing import NamedTuple
from unittest.mock import AsyncMock, MagicMock, call
from uuid import uuid4

import pytest

from src.gamification.application.abuse_monitor_service import (
    AbuseMonitorService,
    AbuseType,
    AlertingService,
    AuditService,
    GamificationAbuseRepository,
    PenaltyService,
)


class ChangeEvent(NamedTuple):
    user_id: str
    tenant_id: uuid4
    timestamp: float


class ResolutionEvent(NamedTuple):
    user_id: str
    tenant_id: uuid4
    issue_hash: str


class ScoreUpdateEvent(NamedTuple):
    user_id: str
    tenant_id: uuid4
    new_score: float


class WeightChangeEvent(NamedTuple):
    user_id: str
    tenant_id: uuid4
    component_id: str
    new_weight: float


TENANT_A = uuid4()
TENANT_B = uuid4()


@pytest.fixture
def mock_abuse_repo() -> MagicMock:
    repo = MagicMock(spec=GamificationAbuseRepository)
    repo.get_change_events_in_last_hour = AsyncMock(return_value=[])
    repo.get_resolution_count_for_hash = AsyncMock(return_value=0)
    repo.get_user_document_count = AsyncMock(return_value=100)
    repo.get_previous_weight_in_last_24h = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_alerting_service() -> MagicMock:
    return AsyncMock(spec=AlertingService)


@pytest.fixture
def mock_audit_service() -> MagicMock:
    return AsyncMock(spec=AuditService)


@pytest.fixture
def mock_penalty_service() -> MagicMock:
    return AsyncMock(spec=PenaltyService)


@pytest.fixture
def abuse_monitor_service(
    mock_abuse_repo,
    mock_alerting_service,
    mock_audit_service,
    mock_penalty_service,
) -> AbuseMonitorService:
    return AbuseMonitorService(
        repo=mock_abuse_repo,
        alerting_service=mock_alerting_service,
        audit_service=mock_audit_service,
        penalty_service=mock_penalty_service,
    )


@pytest.mark.asyncio
class TestGamificationAbuseMonitor:
    """Refers to Suite ID: TS-UC-SEC-GAM-001"""

    USER_ID = "test_user_123"

    # -- Tenant isolation verification (RED → GREEN) ---------------
    async def test_tenant_001_repo_methods_require_tenant_id(
        self,
        abuse_monitor_service,
        mock_abuse_repo,
    ):
        """All repo query methods MUST accept tenant_id as keyword argument."""
        mock_abuse_repo.get_change_events_in_last_hour.return_value = []
        event = ChangeEvent(
            user_id=self.USER_ID,
            tenant_id=TENANT_A,
            timestamp=time.time(),
        )
        await abuse_monitor_service.process_change_event(event)
        mock_abuse_repo.get_change_events_in_last_hour.assert_called_once_with(
            self.USER_ID,
            tenant_id=TENANT_A,
        )

    async def test_tenant_002_cross_tenant_data_is_scoped(
        self,
        abuse_monitor_service,
        mock_abuse_repo,
    ):
        """Repo calls from tenant-A events must carry tenant-A, not tenant-B."""
        mock_abuse_repo.get_resolution_count_for_hash.return_value = 0
        event = ResolutionEvent(
            user_id=self.USER_ID,
            tenant_id=TENANT_A,
            issue_hash="hash1",
        )
        await abuse_monitor_service.process_issue_resolution_event(event)
        mock_abuse_repo.get_resolution_count_for_hash.assert_called_once_with(
            self.USER_ID,
            "hash1",
            tenant_id=TENANT_A,
        )

    async def test_tenant_003_violation_services_receive_tenant_id(
        self,
        abuse_monitor_service,
        mock_abuse_repo,
        mock_alerting_service,
        mock_audit_service,
        mock_penalty_service,
    ):
        """When a violation triggers, penalty/audit/alert receive tenant_id."""
        mock_abuse_repo.get_change_events_in_last_hour.return_value = [
            time.time() - i for i in range(10)
        ]
        event = ChangeEvent(
            user_id=self.USER_ID,
            tenant_id=TENANT_B,
            timestamp=time.time(),
        )
        await abuse_monitor_service.process_change_event(event)

        mock_alerting_service.trigger_alert.assert_called_once_with(
            self.USER_ID,
            AbuseType.MASS_CHANGES,
            "User made 11 changes in the last hour",
            tenant_id=TENANT_B,
        )
        mock_audit_service.log_abuse_violation.assert_called_once_with(
            self.USER_ID,
            AbuseType.MASS_CHANGES,
            tenant_id=TENANT_B,
        )
        mock_penalty_service.apply_penalty.assert_called_once_with(
            self.USER_ID,
            AbuseType.MASS_CHANGES,
            tenant_id=TENANT_B,
        )

    # -- Mass Changes Tests (test_001-003) -------------------------
    async def test_001_mass_changes_11_in_hour_detected(
        self,
        abuse_monitor_service,
        mock_abuse_repo,
        mock_alerting_service,
        mock_audit_service,
        mock_penalty_service,
    ):
        mock_abuse_repo.get_change_events_in_last_hour.return_value = [
            time.time() - i for i in range(10)
        ]
        event = ChangeEvent(
            user_id=self.USER_ID,
            tenant_id=TENANT_A,
            timestamp=time.time(),
        )
        await abuse_monitor_service.process_change_event(event)

        mock_alerting_service.trigger_alert.assert_called_once_with(
            self.USER_ID,
            AbuseType.MASS_CHANGES,
            "User made 11 changes in the last hour",
            tenant_id=TENANT_A,
        )
        mock_audit_service.log_abuse_violation.assert_called_once_with(
            self.USER_ID,
            AbuseType.MASS_CHANGES,
            tenant_id=TENANT_A,
        )
        mock_penalty_service.apply_penalty.assert_called_once_with(
            self.USER_ID,
            AbuseType.MASS_CHANGES,
            tenant_id=TENANT_A,
        )

    async def test_002_mass_changes_10_in_hour_allowed(
        self,
        abuse_monitor_service,
        mock_abuse_repo,
        mock_alerting_service,
    ):
        mock_abuse_repo.get_change_events_in_last_hour.return_value = [
            time.time() - i for i in range(9)
        ]
        event = ChangeEvent(
            user_id=self.USER_ID,
            tenant_id=TENANT_A,
            timestamp=time.time(),
        )
        await abuse_monitor_service.process_change_event(event)
        mock_alerting_service.trigger_alert.assert_not_called()

    # -- Resolve/Re-introduce Tests --------------------------------
    async def test_004_resolve_reintroduce_3_times_detected(
        self,
        abuse_monitor_service,
        mock_abuse_repo,
        mock_alerting_service,
    ):
        issue_hash = "hash_of_issue_content"
        mock_abuse_repo.get_resolution_count_for_hash.return_value = 2
        event = ResolutionEvent(
            user_id=self.USER_ID,
            tenant_id=TENANT_A,
            issue_hash=issue_hash,
        )
        await abuse_monitor_service.process_issue_resolution_event(event)
        mock_alerting_service.trigger_alert.assert_called_once_with(
            self.USER_ID,
            AbuseType.RESOLVE_REINTRODUCE,
            f"Issue with hash {issue_hash} has been re-introduced 3 times.",
            tenant_id=TENANT_A,
        )

    async def test_005_resolve_reintroduce_2_times_allowed(
        self,
        abuse_monitor_service,
        mock_abuse_repo,
        mock_alerting_service,
    ):
        mock_abuse_repo.get_resolution_count_for_hash.return_value = 1
        event = ResolutionEvent(
            user_id=self.USER_ID,
            tenant_id=TENANT_A,
            issue_hash="some_hash",
        )
        await abuse_monitor_service.process_issue_resolution_event(event)
        mock_alerting_service.trigger_alert.assert_not_called()

    async def test_006_resolve_reintroduce_different_hash_allowed(
        self,
        abuse_monitor_service,
        mock_abuse_repo,
        mock_alerting_service,
    ):
        mock_abuse_repo.get_resolution_count_for_hash.side_effect = [2, 0]
        event1 = ResolutionEvent(
            user_id=self.USER_ID,
            tenant_id=TENANT_A,
            issue_hash="hash1",
        )
        await abuse_monitor_service.process_issue_resolution_event(event1)
        mock_alerting_service.trigger_alert.assert_called_once()
        mock_alerting_service.reset_mock()

        event2 = ResolutionEvent(
            user_id=self.USER_ID,
            tenant_id=TENANT_A,
            issue_hash="hash2",
        )
        await abuse_monitor_service.process_issue_resolution_event(event2)
        mock_alerting_service.trigger_alert.assert_not_called()

    # -- High Score / Few Docs Tests -------------------------------
    async def test_007_high_score_few_docs_detected(
        self,
        abuse_monitor_service,
        mock_abuse_repo,
        mock_alerting_service,
    ):
        mock_abuse_repo.get_user_document_count.return_value = 4
        event = ScoreUpdateEvent(
            user_id=self.USER_ID,
            tenant_id=TENANT_A,
            new_score=95.0,
        )
        await abuse_monitor_service.process_score_update_event(event)
        mock_alerting_service.trigger_alert.assert_called_once_with(
            self.USER_ID,
            AbuseType.HIGH_SCORE_LOW_DOCS,
            "User has a high score (95.0) with only 4 documents.",
            tenant_id=TENANT_A,
        )

    async def test_008_high_score_many_docs_allowed(
        self,
        abuse_monitor_service,
        mock_abuse_repo,
        mock_alerting_service,
    ):
        mock_abuse_repo.get_user_document_count.return_value = 20
        event = ScoreUpdateEvent(
            user_id=self.USER_ID,
            tenant_id=TENANT_A,
            new_score=95.0,
        )
        await abuse_monitor_service.process_score_update_event(event)
        mock_alerting_service.trigger_alert.assert_not_called()

    async def test_009_high_score_threshold_boundary(
        self,
        abuse_monitor_service,
        mock_abuse_repo,
        mock_alerting_service,
    ):
        mock_abuse_repo.get_user_document_count.return_value = 4
        event1 = ScoreUpdateEvent(
            user_id=self.USER_ID,
            tenant_id=TENANT_A,
            new_score=89.9,
        )
        await abuse_monitor_service.process_score_update_event(event1)
        mock_alerting_service.trigger_alert.assert_not_called()

        mock_abuse_repo.get_user_document_count.return_value = 5
        event2 = ScoreUpdateEvent(
            user_id=self.USER_ID,
            tenant_id=TENANT_A,
            new_score=90.0,
        )
        await abuse_monitor_service.process_score_update_event(event2)
        mock_alerting_service.trigger_alert.assert_not_called()

    # -- Weight Change Tests --------------------------------------
    async def test_010_weight_change_25_percent_detected(
        self,
        abuse_monitor_service,
        mock_abuse_repo,
        mock_alerting_service,
    ):
        mock_abuse_repo.get_previous_weight_in_last_24h.return_value = 1.0
        event = WeightChangeEvent(
            user_id=self.USER_ID,
            tenant_id=TENANT_A,
            component_id="comp1",
            new_weight=1.25,
        )
        await abuse_monitor_service.process_weight_change_event(event)
        mock_alerting_service.trigger_alert.assert_called_once_with(
            self.USER_ID,
            AbuseType.LARGE_WEIGHT_CHANGE,
            "Weight for comp1 changed by 25.0% in 24 hours.",
            tenant_id=TENANT_A,
        )

    async def test_011_weight_change_15_percent_allowed(
        self,
        abuse_monitor_service,
        mock_abuse_repo,
        mock_alerting_service,
    ):
        mock_abuse_repo.get_previous_weight_in_last_24h.return_value = 1.0
        event = WeightChangeEvent(
            user_id=self.USER_ID,
            tenant_id=TENANT_A,
            component_id="comp1",
            new_weight=1.15,
        )
        await abuse_monitor_service.process_weight_change_event(event)
        mock_alerting_service.trigger_alert.assert_not_called()

    # -- Edge Case Tests ------------------------------------------
    async def test_edge_001_multiple_violations_combined(
        self,
        abuse_monitor_service,
        mock_abuse_repo,
        mock_alerting_service,
    ):
        mock_abuse_repo.get_change_events_in_last_hour.return_value = [
            time.time() - i for i in range(10)
        ]
        mock_abuse_repo.get_previous_weight_in_last_24h.return_value = 1.0

        event = WeightChangeEvent(
            user_id=self.USER_ID,
            tenant_id=TENANT_A,
            component_id="comp1",
            new_weight=1.30,
        )
        await abuse_monitor_service.process_event(event)

        expected_calls = [
            call(
                self.USER_ID,
                AbuseType.MASS_CHANGES,
                "User made 11 changes in the last hour",
                tenant_id=TENANT_A,
            ),
            call(
                self.USER_ID,
                AbuseType.LARGE_WEIGHT_CHANGE,
                "Weight for comp1 changed by 30.0% in 24 hours.",
                tenant_id=TENANT_A,
            ),
        ]
        mock_alerting_service.trigger_alert.assert_has_calls(
            expected_calls,
            any_order=True,
        )

    async def test_edge_002_003_penalty_and_audit_logging(
        self,
        abuse_monitor_service,
        mock_abuse_repo,
        mock_audit_service,
        mock_penalty_service,
    ):
        mock_abuse_repo.get_resolution_count_for_hash.return_value = 2
        issue_hash = "audited_and_penalized_hash"
        event = ResolutionEvent(
            user_id=self.USER_ID,
            tenant_id=TENANT_A,
            issue_hash=issue_hash,
        )
        await abuse_monitor_service.process_issue_resolution_event(event)

        mock_audit_service.log_abuse_violation.assert_called_once_with(
            self.USER_ID,
            AbuseType.RESOLVE_REINTRODUCE,
            tenant_id=TENANT_A,
        )
        mock_penalty_service.apply_penalty.assert_called_once_with(
            self.USER_ID,
            AbuseType.RESOLVE_REINTRODUCE,
            tenant_id=TENANT_A,
        )
