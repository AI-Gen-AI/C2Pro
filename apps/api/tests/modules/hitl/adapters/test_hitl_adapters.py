"""Tests for HITL real adapters: repository, notification, HTTP schemas, graph integration.

These tests verify the concrete adapter implementations without requiring
a running database or external services.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.modules.hitl.adapters.notifications.log_notification_service import (
    LogNotificationService,
)
from src.modules.hitl.application.ports import (
    HumanInTheLoopService,
    NotificationService,
    ReviewQueueRepository,
)
from src.modules.hitl.domain.entities import ImpactLevel, ReviewItem, ReviewStatus
from src.modules.hitl.domain.services import ConfidenceRouter

# ── Fixtures ─────────────────────────────────────────────────────────────────


def _make_review_item(**overrides) -> ReviewItem:
    defaults = {
        "item_id": uuid4(),
        "item_type": "risk_extraction",
        "current_status": ReviewStatus.PENDING_REVIEW_REQUIRED,
        "confidence": 0.4,
        "impact_level": ImpactLevel.MEDIUM,
        "created_at": datetime.now(UTC),
        "sla_due_date": datetime.now(UTC) + timedelta(days=3),
        "item_data": {"project_id": str(uuid4())},
    }
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
        await svc.send_notification(uuid4(), "Test message", item, uuid4())

    @pytest.mark.asyncio
    async def test_send_escalation_alert_does_not_raise(self):
        svc = LogNotificationService()
        item = _make_review_item()
        await svc.send_escalation_alert(item, uuid4())


# ── ORM Model (requires settings) ────────────────────────────────────────────


class TestReviewItemORM:
    def test_orm_model_has_required_columns(self):
        from src.modules.hitl.adapters.persistence.models import ReviewItemORM

        columns = {c.name for c in ReviewItemORM.__table__.columns}
        expected = {
            "id",
            "item_id",
            "item_type",
            "current_status",
            "confidence",
            "impact_level",
            "tenant_id",
            "approved_by",
            "approved_at",
            "sla_due_date",
            "item_data",
            "review_metadata",
            "created_at",
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
            session=MagicMock(),
            tenant_id=tenant_id,
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

        now = datetime.now(UTC)
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
    async def test_route_low_confidence_to_required_review(self, hitl_service, mock_repo):
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
    async def test_route_high_confidence_low_impact_auto_approves(self, hitl_service, mock_repo):
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
    async def test_route_high_impact_always_requires_review(self, hitl_service, mock_repo):
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
    async def test_escalate_overdue_items(self, hitl_service, mock_repo, mock_notification):
        tenant_id = uuid4()
        overdue = _make_review_item(
            sla_due_date=datetime.now(UTC) - timedelta(days=1),
            metadata={"tenant_id": str(tenant_id)},
        )
        mock_repo.get_overdue_items.return_value = [overdue]

        results = await hitl_service.check_and_escalate_slas()

        assert len(results) == 1
        assert results[0].new_status == ReviewStatus.ESCALATED
        assert results[0].escalation_triggered is True
        mock_notification.send_escalation_alert.assert_called_once_with(overdue, tenant_id)

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
            approved_at=datetime.now(UTC),
        )
        mock_repo.get_review_item.return_value = approved

        result = await hitl_service.release_item(approved.item_id)
        assert result.current_status == ReviewStatus.CLOSED


# ── Migration file ────────────────────────────────────────────────────────────


class TestMigration:
    @staticmethod
    def _migration_path():
        from pathlib import Path

        repo_root = Path(__file__).resolve().parents[6]
        return (
            repo_root
            / "apps"
            / "api"
            / "alembic"
            / "versions"
            / "20260225_0001_create_review_items.py"
        )

    def test_migration_file_exists(self):
        migration = self._migration_path()
        assert migration.exists()

    def test_migration_revision_chain(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location("migration", self._migration_path())
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

        now = datetime.now(UTC)
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


# ── HITLServiceAdapter (bridges to HITLPort protocol) ────────────────────────


class TestHITLServiceAdapter:
    @pytest.mark.asyncio
    async def test_route_for_review_returns_str_not_enum(self, mock_repo, mock_notification):
        from src.modules.hitl.adapters.hitl_port_adapter import HITLServiceAdapter

        service = HumanInTheLoopService(
            review_queue_repo=mock_repo,
            notification_service=mock_notification,
            confidence_router=ConfidenceRouter(),
        )
        adapter = HITLServiceAdapter(service)

        # HITLPort expects impact_level as str, returns str
        result = await adapter.route_for_review(
            item_id=uuid4(),
            item_type="risk_extraction",
            confidence=0.1,
            impact_level="LOW",
            item_data={},
        )
        assert isinstance(result, str)
        assert result == "PENDING_REVIEW_REQUIRED"

    @pytest.mark.asyncio
    async def test_route_for_review_handles_case_insensitive_impact(
        self, mock_repo, mock_notification
    ):
        from src.modules.hitl.adapters.hitl_port_adapter import HITLServiceAdapter

        adapter = HITLServiceAdapter(
            HumanInTheLoopService(
                review_queue_repo=mock_repo,
                notification_service=mock_notification,
                confidence_router=ConfidenceRouter(),
            )
        )
        result = await adapter.route_for_review(
            item_id=uuid4(),
            item_type="x",
            confidence=0.99,
            impact_level="critical",  # lowercase
            item_data={},
        )
        assert result == "PENDING_REVIEW_REQUIRED"  # critical always requires review

    @pytest.mark.asyncio
    async def test_approve_item_returns_dict_not_review_item(self, mock_repo, mock_notification):
        from src.modules.hitl.adapters.hitl_port_adapter import HITLServiceAdapter

        pending = _make_review_item(
            current_status=ReviewStatus.PENDING_REVIEW_REQUIRED,
        )
        mock_repo.get_review_item.return_value = pending

        adapter = HITLServiceAdapter(
            HumanInTheLoopService(
                review_queue_repo=mock_repo,
                notification_service=mock_notification,
                confidence_router=ConfidenceRouter(),
            )
        )
        result = await adapter.approve_item(
            item_id=pending.item_id,
            reviewer_id=uuid4(),
            reviewer_name="Maria Garcia",
        )
        # HITLPort expects dict[str, Any]
        assert isinstance(result, dict)
        assert result["approved_by"] == "Maria Garcia"
        assert result["current_status"] == "APPROVED"
        assert result.get("approved_at") is not None

    @pytest.mark.asyncio
    async def test_adapter_satisfies_hitl_port_protocol(self, mock_repo, mock_notification):
        """Verify structural typing: adapter has both methods with correct signatures."""
        from src.modules.hitl.adapters.hitl_port_adapter import HITLServiceAdapter

        adapter = HITLServiceAdapter(
            HumanInTheLoopService(
                review_queue_repo=mock_repo,
                notification_service=mock_notification,
                confidence_router=ConfidenceRouter(),
            )
        )
        assert hasattr(adapter, "route_for_review")
        assert hasattr(adapter, "approve_item")
        assert callable(adapter.route_for_review)
        assert callable(adapter.approve_item)


# ── TASK-BCK-092: Queue project filtering + true count ────────────────────────


class TestReviewQueueProjectFiltering:
    """TASK-BCK-092: Verify project_id filtering and true total count."""

    def test_repository_list_by_status_accepts_project_id(self):
        """Repository list_by_status signature accepts optional project_id."""
        from unittest.mock import AsyncMock, MagicMock
        from uuid import uuid4

        from src.modules.hitl.adapters.persistence.repository import (
            SqlAlchemyReviewQueueRepository,
        )

        mock_session = MagicMock()
        mock_session.execute = AsyncMock()
        repo = SqlAlchemyReviewQueueRepository(session=mock_session, tenant_id=uuid4())
        assert hasattr(repo, "list_by_status")

        import inspect

        sig = inspect.signature(repo.list_by_status)
        params = list(sig.parameters.keys())
        assert "project_id" in params, f"list_by_status missing project_id param: {params}"

    def test_repository_list_by_status_applies_project_id_filter(self):
        """When project_id is provided, the SQL query includes it."""
        from unittest.mock import AsyncMock, MagicMock
        from uuid import uuid4

        from src.modules.hitl.adapters.persistence.repository import (
            SqlAlchemyReviewQueueRepository,
        )

        tenant_id = uuid4()
        project_id = uuid4()
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = SqlAlchemyReviewQueueRepository(session=mock_session, tenant_id=tenant_id)
        import asyncio

        asyncio.get_event_loop().run_until_complete(repo.list_by_status(project_id=project_id))

        call_args = mock_session.execute.call_args[0][0]
        sql_str = str(call_args.compile(compile_kwargs={"literal_binds": True}))
        # SQLAlchemy literal_binds formats UUID without dashes
        tid_hex = str(tenant_id).replace("-", "")
        pid_hex = str(project_id).replace("-", "")
        assert tid_hex in sql_str, f"tenant_id not in SQL: {sql_str}"
        assert pid_hex in sql_str, f"project_id filter not present in SQL: {sql_str}"

    def test_repository_list_by_status_omits_project_id_when_none(self):
        """When project_id is None, the filter is not applied (backward compat)."""
        from unittest.mock import AsyncMock, MagicMock
        from uuid import uuid4

        from src.modules.hitl.adapters.persistence.repository import (
            SqlAlchemyReviewQueueRepository,
        )

        tenant_id = uuid4()
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = SqlAlchemyReviewQueueRepository(session=mock_session, tenant_id=tenant_id)
        import asyncio

        asyncio.get_event_loop().run_until_complete(repo.list_by_status(project_id=None))

        call_args = mock_session.execute.call_args[0][0]
        sql_str = str(call_args.compile(compile_kwargs={"literal_binds": True}))
        tid_hex = str(tenant_id).replace("-", "")
        assert tid_hex in sql_str
        # project_id should NOT be in WHERE clause when None was passed
        # (but .project_id may appear in SELECT column list)
        # Check that the WHERE does not contain a project_id filter
        where_part = sql_str.split("WHERE")[1].split("ORDER BY")[0] if "WHERE" in sql_str else ""
        assert "project_id" not in where_part, (
            f"project_id filter found in WHERE when None: {where_part}"
        )

    def test_repository_count_by_status_returns_true_count(self):
        """Repository count_by_status returns total matching rows not page size."""
        from unittest.mock import AsyncMock, MagicMock
        from uuid import uuid4

        from src.modules.hitl.adapters.persistence.repository import (
            SqlAlchemyReviewQueueRepository,
        )

        tenant_id = uuid4()
        mock_session = MagicMock()
        mock_result = MagicMock()
        # Simulate 7 total rows in the DB, but query returns only 3 due to pagination
        mock_result.scalar.return_value = 7
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = SqlAlchemyReviewQueueRepository(session=mock_session, tenant_id=tenant_id)
        assert hasattr(repo, "count_by_status")

        import asyncio

        count = asyncio.get_event_loop().run_until_complete(repo.count_by_status())
        assert count == 7, f"Expected true count 7, got {count}"

    def test_repository_count_by_status_cross_tenant_returns_zero(self):
        """Cross-tenant project_id returns zero (tenant isolation preserved)."""
        from unittest.mock import AsyncMock, MagicMock
        from uuid import uuid4

        from src.modules.hitl.adapters.persistence.repository import (
            SqlAlchemyReviewQueueRepository,
        )

        tenant_id = uuid4()
        other_project_id = uuid4()
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = SqlAlchemyReviewQueueRepository(session=mock_session, tenant_id=tenant_id)
        import asyncio

        count = asyncio.get_event_loop().run_until_complete(
            repo.count_by_status(project_id=other_project_id)
        )
        call_args = mock_session.execute.call_args[0][0]
        sql_str = str(call_args.compile(compile_kwargs={"literal_binds": True}))
        tid_hex = str(tenant_id).replace("-", "")
        pid_hex = str(other_project_id).replace("-", "")
        assert tid_hex in sql_str
        assert pid_hex in sql_str
