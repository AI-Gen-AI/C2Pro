"""Tests for HITL real adapters: repository, notification, HTTP schemas, graph integration.

These tests verify the concrete adapter implementations without requiring
a running database or external services.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.modules.hitl.domain.entities import ImpactLevel, ReviewItem, ReviewStatus
from src.modules.hitl.domain.services import ConfidenceRouter
from src.modules.hitl.application.ports import (
    HumanInTheLoopService,
    NotificationService,
    ReviewQueueRepository,
)
from src.modules.hitl.adapters.notifications.log_notification_service import (
    LogNotificationService,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _make_review_item(**overrides) -> ReviewItem:
    defaults = dict(
        item_id=uuid4(),
        item_type="risk_extraction",
        current_status=ReviewStatus.PENDING_REVIEW_REQUIRED,
        confidence=0.4,
        impact_level=ImpactLevel.MEDIUM,
        created_at=datetime.utcnow(),
        sla_due_date=datetime.utcnow() + timedelta(days=3),
        item_data={"project_id": str(uuid4())},
    )
    defaults.update(overrides)
    return ReviewItem(**defaults)


@pytest.fixture
def mock_repo() -> AsyncMock:
    repo = AsyncMock(spec=ReviewQueueRepository)
    repo.add_review_item.return_value = uuid4()
    repo.get_review_item.return_value = None
    repo.update_review_item.return_value = None
    repo.get_overdue_items.return_value = []
    return repo


@pytest.fixture
def mock_notification() -> AsyncMock:
    return AsyncMock(spec=NotificationService)


@pytest.fixture
def hitl_service(mock_repo, mock_notification) -> HumanInTheLoopService:
    return HumanInTheLoopService(
        review_queue_repo=mock_repo,
        notification_service=mock_notification,
        confidence_router=ConfidenceRouter(),
    )


# ── LogNotificationService ───────────────────────────────────────────────────


class TestLogNotificationService:
    @pytest.mark.asyncio
    async def test_send_notification_does_not_raise(self):
        svc = LogNotificationService()
        item = _make_review_item()
        await svc.send_notification(uuid4(), "Test message", item)

    @pytest.mark.asyncio
    async def test_send_escalation_alert_does_not_raise(self):
        svc = LogNotificationService()
        item = _make_review_item()
        await svc.send_escalation_alert(item)


# ── ORM Model (requires settings) ────────────────────────────────────────────


class TestReviewItemORM:
    def test_orm_model_has_required_columns(self):
        from src.modules.hitl.adapters.persistence.models import ReviewItemORM

        columns = {c.name for c in ReviewItemORM.__table__.columns}
        expected = {
            "id", "item_id", "item_type", "current_status", "confidence",
            "impact_level", "tenant_id", "approved_by", "approved_at",
            "sla_due_date", "item_data", "review_metadata", "created_at",
            "updated_at",
        }
        assert expected.issubset(columns), f"Missing columns: {expected - columns}"

    def test_orm_table_name(self):
        from src.modules.hitl.adapters.persistence.models import ReviewItemORM

        assert ReviewItemORM.__tablename__ == "review_items"

    def test_orm_has_rls_info(self):
        from src.modules.hitl.adapters.persistence.models import ReviewItemORM

        info = ReviewItemORM.__table__.info
        assert info.get("rls_policy") == "tenant_isolation"


# ── Repository mapper (requires settings for ORM import) ─────────────────────


class TestRepositoryMappers:
    def test_to_orm_maps_all_fields(self):
        from src.modules.hitl.adapters.persistence.repository import (
            SqlAlchemyReviewQueueRepository,
        )

        tenant_id = uuid4()
        repo = SqlAlchemyReviewQueueRepository(
            session=MagicMock(), tenant_id=tenant_id,
        )
        item = _make_review_item()
        orm = repo._to_orm(item)

        assert orm.item_id == item.item_id
        assert orm.item_type == item.item_type
        assert orm.current_status == item.current_status
        assert orm.confidence == item.confidence
        assert orm.impact_level == item.impact_level
        assert orm.tenant_id == tenant_id
        assert orm.sla_due_date == item.sla_due_date
        assert orm.item_data == item.item_data

    def test_to_domain_round_trips(self):
        from src.modules.hitl.adapters.persistence.models import ReviewItemORM
        from src.modules.hitl.adapters.persistence.repository import (
            SqlAlchemyReviewQueueRepository,
        )

        now = datetime.utcnow()
        orm = ReviewItemORM(
            item_id=uuid4(),
            item_type="coherence_alert",
            current_status=ReviewStatus.APPROVED,
            confidence=0.92,
            impact_level=ImpactLevel.HIGH,
            tenant_id=uuid4(),
            approved_by="reviewer-a",
            approved_at=now,
            sla_due_date=now + timedelta(days=7),
            item_data={"foo": "bar"},
            review_metadata={"source": "test"},
            created_at=now,
            updated_at=now,
        )
        domain = SqlAlchemyReviewQueueRepository._to_domain(orm)

        assert domain.item_id == orm.item_id
        assert domain.item_type == "coherence_alert"
        assert domain.current_status == ReviewStatus.APPROVED
        assert domain.confidence == 0.92
        assert domain.impact_level == ImpactLevel.HIGH
        assert domain.approved_by == "reviewer-a"
        assert domain.item_data == {"foo": "bar"}
        assert domain.metadata == {"source": "test"}


# ── End-to-end HITL service (mocked repo) ────────────────────────────────────


class TestHITLServiceIntegration:
    @pytest.mark.asyncio
    async def test_route_low_confidence_to_required_review(
        self, hitl_service, mock_repo
    ):
        status = await hitl_service.route_for_review(
            item_id=uuid4(),
            item_type="risk_extraction",
            confidence=0.1,
            impact_level=ImpactLevel.LOW,
            item_data={},
        )
        assert status == ReviewStatus.PENDING_REVIEW_REQUIRED
        mock_repo.add_review_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_route_high_confidence_low_impact_auto_approves(
        self, hitl_service, mock_repo
    ):
        status = await hitl_service.route_for_review(
            item_id=uuid4(),
            item_type="wbs_extraction",
            confidence=0.95,
            impact_level=ImpactLevel.LOW,
            item_data={},
        )
        assert status == ReviewStatus.APPROVED
        mock_repo.add_review_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_route_high_impact_always_requires_review(
        self, hitl_service, mock_repo
    ):
        status = await hitl_service.route_for_review(
            item_id=uuid4(),
            item_type="coherence_alert",
            confidence=0.99,
            impact_level=ImpactLevel.CRITICAL,
            item_data={},
        )
        assert status == ReviewStatus.PENDING_REVIEW_REQUIRED

    @pytest.mark.asyncio
    async def test_approve_item_sets_metadata(self, hitl_service, mock_repo):
        pending_item = _make_review_item(
            current_status=ReviewStatus.PENDING_REVIEW_REQUIRED,
        )
        mock_repo.get_review_item.return_value = pending_item

        result = await hitl_service.approve_item(
            item_id=pending_item.item_id,
            reviewer_id=uuid4(),
            reviewer_name="Maria Garcia",
        )
        assert result.current_status == ReviewStatus.APPROVED
        assert result.approved_by == "Maria Garcia"
        assert result.approved_at is not None
        mock_repo.update_review_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_approve_non_pending_raises(self, hitl_service, mock_repo):
        closed_item = _make_review_item(
            current_status=ReviewStatus.CLOSED,
        )
        mock_repo.get_review_item.return_value = closed_item

        with pytest.raises(ValueError, match="cannot be approved"):
            await hitl_service.approve_item(
                item_id=closed_item.item_id,
                reviewer_id=uuid4(),
                reviewer_name="Tester",
            )

    @pytest.mark.asyncio
    async def test_escalate_overdue_items(
        self, hitl_service, mock_repo, mock_notification
    ):
        overdue = _make_review_item(
            sla_due_date=datetime.utcnow() - timedelta(days=1),
        )
        mock_repo.get_overdue_items.return_value = [overdue]

        results = await hitl_service.check_and_escalate_slas()

        assert len(results) == 1
        assert results[0].new_status == ReviewStatus.ESCALATED
        assert results[0].escalation_triggered is True
        mock_notification.send_escalation_alert.assert_called_once_with(overdue)

    @pytest.mark.asyncio
    async def test_release_requires_reviewer_info(self, hitl_service, mock_repo):
        approved_no_meta = _make_review_item(
            current_status=ReviewStatus.APPROVED,
            approved_by=None,
            approved_at=None,
        )
        mock_repo.get_review_item.return_value = approved_no_meta

        with pytest.raises(ValueError, match="missing explicit reviewer"):
            await hitl_service.release_item(approved_no_meta.item_id)

    @pytest.mark.asyncio
    async def test_release_approved_item_succeeds(self, hitl_service, mock_repo):
        approved = _make_review_item(
            current_status=ReviewStatus.APPROVED,
            approved_by="Admin",
            approved_at=datetime.utcnow(),
        )
        mock_repo.get_review_item.return_value = approved

        result = await hitl_service.release_item(approved.item_id)
        assert result.current_status == ReviewStatus.CLOSED


# ── Migration file ────────────────────────────────────────────────────────────


class TestMigration:
    def test_migration_file_exists(self):
        from pathlib import Path

        migration = Path(
            "/home/user/C2Pro/apps/api/alembic/versions/20260225_0001_create_review_items.py"
        )
        assert migration.exists()

    def test_migration_revision_chain(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "migration",
            "/home/user/C2Pro/apps/api/alembic/versions/20260225_0001_create_review_items.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod.revision == "20260225_0001"
        assert mod.down_revision == "20260205_0001"


# ── HTTP schemas (imported from standalone schemas.py — no database dep) ─────


class TestHTTPSchemas:
    def test_route_for_review_request_validates(self):
        from src.modules.hitl.adapters.http.schemas import RouteForReviewRequest

        req = RouteForReviewRequest(
            item_id=uuid4(),
            item_type="risk_extraction",
            confidence=0.5,
            impact_level=ImpactLevel.HIGH,
            item_data={"key": "val"},
        )
        assert req.confidence == 0.5
        assert req.impact_level == ImpactLevel.HIGH

    def test_route_for_review_request_rejects_invalid_confidence(self):
        from pydantic import ValidationError
        from src.modules.hitl.adapters.http.schemas import RouteForReviewRequest

        with pytest.raises(ValidationError):
            RouteForReviewRequest(
                item_id=uuid4(),
                item_type="x",
                confidence=1.5,  # out of range
                impact_level=ImpactLevel.LOW,
            )

    def test_review_item_response_serializes(self):
        from src.modules.hitl.adapters.http.schemas import ReviewItemResponse

        now = datetime.utcnow()
        resp = ReviewItemResponse(
            item_id=uuid4(),
            item_type="budget_parse",
            current_status=ReviewStatus.APPROVED,
            confidence=0.88,
            impact_level=ImpactLevel.MEDIUM,
            approved_by="Admin",
            approved_at=now,
            sla_due_date=now + timedelta(days=3),
            created_at=now,
            item_data={"a": 1},
        )
        assert resp.current_status == ReviewStatus.APPROVED
        assert resp.approved_by == "Admin"

    def test_reject_request_schema(self):
        from src.modules.hitl.adapters.http.schemas import RejectRequest

        req = RejectRequest(reviewer_name="Admin", reason="Not accurate enough")
        assert req.reason == "Not accurate enough"

    def test_review_queue_response_schema(self):
        from src.modules.hitl.adapters.http.schemas import ReviewQueueResponse

        resp = ReviewQueueResponse(items=[], total=0)
        assert resp.total == 0
        assert resp.items == []
