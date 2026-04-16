from datetime import timezone
"""
Integration tests for HITL workflow resume endpoint.
Test Suite ID: TS-I11-HITL-HTTP-002

Part of TASK-BCK-024: Implement HITL workflow resume mechanism after approval.
Part of TASK-BCK-030: Set up authenticated test fixtures for HITL resume tests.

TDD Test Suite - GREEN Phase (with authentication)
Tests define requirements for POST /api/v1/hitl/resume endpoint.

All tests now use authenticated_client fixture for proper JWT authentication.
"""
from collections.abc import AsyncGenerator
from datetime import datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient

from src.core.auth.models import Tenant
from src.documents.adapters.persistence.models import DocumentORM
from src.modules.hitl.adapters.http.dependencies import get_resume_workflow_use_case
from src.modules.hitl.adapters.persistence.models import ReviewItemORM
from src.modules.hitl.adapters.persistence.repository import SqlAlchemyReviewQueueRepository
from src.modules.hitl.application.resume_workflow_use_case import ResumeWorkflowUseCase
from src.modules.hitl.domain.entities import ImpactLevel, ReviewStatus
from src.projects.adapters.persistence.models import ProjectORM

pytestmark = pytest.mark.asyncio


class _FakeCheckpointService:
    """Deterministic checkpoint service for HITL resume HTTP integration tests."""

    def __init__(self) -> None:
        self.loaded: list[tuple[str, str]] = []

    async def load_checkpoint(self, thread_id: str, checkpoint_id: str) -> dict[str, str]:
        self.loaded.append((thread_id, checkpoint_id))
        return {"thread_id": thread_id, "checkpoint_id": checkpoint_id}

    def extract_state(self, checkpoint: dict[str, str]) -> dict[str, object]:
        return {
            "thread_id": checkpoint["thread_id"],
            "checkpoint_id": checkpoint["checkpoint_id"],
        }


class _FakeGraphApp:
    """Records state updates without requiring the real LangGraph runtime."""

    def __init__(self) -> None:
        self.updates: list[tuple[dict[str, object], dict[str, object]]] = []

    async def aupdate_state(
        self,
        config: dict[str, object],
        state: dict[str, object],
    ) -> None:
        self.updates.append((config, dict(state)))


@pytest_asyncio.fixture
async def hitl_resume_override(
    app,
    db,
    test_user,
) -> AsyncGenerator[tuple[_FakeCheckpointService, _FakeGraphApp], None]:
    """Override the resume workflow dependency with deterministic collaborators."""
    checkpoint_service = _FakeCheckpointService()
    graph_app = _FakeGraphApp()

    def _override_use_case() -> ResumeWorkflowUseCase:
        repo = SqlAlchemyReviewQueueRepository(session=db, tenant_id=test_user.tenant_id)
        return ResumeWorkflowUseCase(
            review_queue_repo=repo,
            checkpoint_service=checkpoint_service,
            graph_app=graph_app,
        )

    app.dependency_overrides[get_resume_workflow_use_case] = _override_use_case
    yield checkpoint_service, graph_app
    app.dependency_overrides.pop(get_resume_workflow_use_case, None)


@pytest_asyncio.fixture
async def test_tenant(db):
    """Create a test tenant."""
    tenant = Tenant(
        id=uuid4(),
        name="Test Tenant",
        slug=f"test-{uuid4().hex[:8]}",
        subscription_plan="professional",
        is_active=True,
    )
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return tenant


@pytest_asyncio.fixture
async def test_project(db, test_tenant):
    """Create a test project."""
    project = ProjectORM(
        id=uuid4(),
        tenant_id=test_tenant.id,
        name="Test Project",
        code="TEST-HITL",
        start_date=datetime.now(),
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@pytest_asyncio.fixture
async def test_document(db, test_project):
    """Create a test document."""
    document = DocumentORM(
        id=uuid4(),
        project_id=test_project.id,
        document_type="contract",
        filename="test_contract.pdf",
        upload_status="parsed",
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)
    return document


@pytest_asyncio.fixture
async def test_review_item(db, test_project, test_document, test_tenant):
    """Create a test HITL review item with checkpoint reference."""
    item_id = uuid4()
    review_item = ReviewItemORM(
        id=item_id,
        item_id=item_id,
        item_type="stakeholder_validation",
        tenant_id=test_tenant.id,
        current_status=ReviewStatus.PENDING_REVIEW_REQUIRED,
        impact_level=ImpactLevel.HIGH,
        confidence=0.65,
        sla_due_date=datetime.now(timezone.utc),
        item_data={},
        review_metadata={
            "stakeholders": ["Alice", "Bob"],
            "confidence_score": 0.65,
            "analysis_stage": "stakeholder_extraction"
        },
        # TASK-BCK-024: Checkpoint tracking fields
        checkpoint_id=f"checkpoint_{uuid4().hex}",  # LangGraph checkpoint reference
        thread_id=f"thread_{uuid4().hex}",  # LangGraph thread ID
        project_id=test_project.id,
        document_id=test_document.id,
        review_type="stakeholder_validation",
    )
    db.add(review_item)
    await db.commit()
    await db.refresh(review_item)
    return review_item


@pytest_asyncio.fixture
async def approved_review_item(db, test_project, test_document, test_tenant):
    """Create an already-approved review item (should not be resumable)."""
    item_id = uuid4()
    review_item = ReviewItemORM(
        id=item_id,
        item_id=item_id,
        item_type="stakeholder_validation",
        tenant_id=test_tenant.id,
        current_status=ReviewStatus.APPROVED,  # Already processed
        impact_level=ImpactLevel.MEDIUM,
        confidence=0.75,
        sla_due_date=datetime.now(timezone.utc),
        item_data={},
        review_metadata={},
        # TASK-BCK-024: Checkpoint tracking fields
        checkpoint_id=f"checkpoint_{uuid4().hex}",
        thread_id=f"thread_{uuid4().hex}",
        project_id=test_project.id,
        document_id=test_document.id,
        review_type="stakeholder_validation",
    )
    db.add(review_item)
    await db.commit()
    await db.refresh(review_item)
    return review_item


class TestResumeEndpointExistence:
    """Test that the resume endpoint exists and has correct signature."""

    async def test_resume_endpoint_exists(self, authenticated_client: AsyncClient, test_review_item):
        """POST /api/v1/hitl/resume/{review_id} endpoint should exist."""
        response = await authenticated_client.post(
            f"/api/v1/hitl/resume/{test_review_item.id}",
            json={"decision": "approve", "feedback": "Looks good"}
        )
        # Endpoint should exist (not 404)
        assert response.status_code != 404, "Resume endpoint should exist"

    async def test_resume_requires_decision_field(self, authenticated_client: AsyncClient, test_review_item):
        """Resume request must include 'decision' field."""
        response = await authenticated_client.post(
            f"/api/v1/hitl/resume/{test_review_item.id}",
            json={"feedback": "Missing decision"}
        )
        # Should return 422 (validation error) or 400 (bad request)
        assert response.status_code in [400, 422], "Should reject request without decision"

    async def test_resume_validates_decision_value(self, authenticated_client: AsyncClient, test_review_item):
        """Decision field must be 'approve' or 'reject'."""
        response = await authenticated_client.post(
            f"/api/v1/hitl/resume/{test_review_item.id}",
            json={"decision": "invalid_value", "feedback": ""}
        )
        assert response.status_code in [400, 422], "Should reject invalid decision value"


class TestApprovalFlow:
    """Test workflow resumption with approval decision."""

    async def test_approval_resumes_workflow(
        self,
        authenticated_client: AsyncClient,
        test_review_item,
        hitl_resume_override,
    ):
        """Approving a review item should resume the workflow."""
        _ = hitl_resume_override
        response = await authenticated_client.post(
            f"/api/v1/hitl/resume/{test_review_item.id}",
            json={
                "decision": "approve",
                "feedback": "Stakeholders confirmed, proceed with analysis"
            }
        )
        assert response.status_code == 200, f"Approval should succeed: {response.text}"

        # Verify response structure
        data = response.json()
        assert "review_id" in data
        assert "status" in data
        assert data["status"] == "resumed" or data["status"] == "approved"

    async def test_approval_updates_review_status(
        self,
        authenticated_client: AsyncClient,
        test_review_item,
        db,
        hitl_resume_override,
    ):
        """Approval should update review item status to 'approved'."""
        _ = hitl_resume_override
        await authenticated_client.post(
            f"/api/v1/hitl/resume/{test_review_item.id}",
            json={"decision": "approve", "feedback": "Approved"}
        )

        # Reload review item from DB
        await db.refresh(test_review_item)
        assert test_review_item.current_status == ReviewStatus.APPROVED, "Status should be updated to approved"

    async def test_approval_stores_feedback(
        self,
        authenticated_client: AsyncClient,
        test_review_item,
        db,
        hitl_resume_override,
    ):
        """Approval feedback should be stored in review item."""
        _ = hitl_resume_override
        feedback_text = "All stakeholders verified, confidence increased to 0.95"

        await authenticated_client.post(
            f"/api/v1/hitl/resume/{test_review_item.id}",
            json={"decision": "approve", "feedback": feedback_text}
        )

        await db.refresh(test_review_item)
        # Feedback should be stored in review_decision field
        assert test_review_item.review_decision == feedback_text, "Feedback should be persisted in review_decision"


class TestRejectionFlow:
    """Test workflow termination with rejection decision."""

    async def test_rejection_terminates_workflow(
        self,
        authenticated_client: AsyncClient,
        test_review_item,
        hitl_resume_override,
    ):
        """Rejecting a review item should terminate the workflow."""
        _ = hitl_resume_override
        response = await authenticated_client.post(
            f"/api/v1/hitl/resume/{test_review_item.id}",
            json={
                "decision": "reject",
                "feedback": "Stakeholders list is incomplete, cannot proceed"
            }
        )
        assert response.status_code == 200, f"Rejection should succeed: {response.text}"

        data = response.json()
        assert "review_id" in data
        assert "status" in data
        assert data["status"] == "rejected" or data["status"] == "terminated"

    async def test_rejection_updates_review_status(
        self,
        authenticated_client: AsyncClient,
        test_review_item,
        db,
        hitl_resume_override,
    ):
        """Rejection should update review item status to 'rejected'."""
        _ = hitl_resume_override
        await authenticated_client.post(
            f"/api/v1/hitl/resume/{test_review_item.id}",
            json={"decision": "reject", "feedback": "Rejected"}
        )

        await db.refresh(test_review_item)
        assert test_review_item.current_status == ReviewStatus.REJECTED, "Status should be updated to rejected"

    async def test_rejection_stores_reason(
        self,
        authenticated_client: AsyncClient,
        test_review_item,
        db,
        hitl_resume_override,
    ):
        """Rejection reason should be stored."""
        _ = hitl_resume_override
        rejection_reason = "Stakeholder list missing critical parties"

        await authenticated_client.post(
            f"/api/v1/hitl/resume/{test_review_item.id}",
            json={"decision": "reject", "feedback": rejection_reason}
        )

        await db.refresh(test_review_item)
        assert test_review_item.review_decision == rejection_reason, "Rejection reason should be persisted in review_decision"


class TestCheckpointRestoration:
    """Test LangGraph checkpoint state restoration."""

    async def test_checkpoint_id_is_used_for_restoration(
        self,
        authenticated_client: AsyncClient,
        test_review_item,
        hitl_resume_override,
    ):
        """Resume should use checkpoint_id from review item to restore state."""
        checkpoint_service, _ = hitl_resume_override
        # This test verifies the resume endpoint uses the checkpoint_id field
        response = await authenticated_client.post(
            f"/api/v1/hitl/resume/{test_review_item.id}",
            json={"decision": "approve", "feedback": "Test"}
        )

        assert response.status_code == 200, "Checkpoint restoration should succeed in test runtime"
        assert checkpoint_service.loaded == [
            (test_review_item.thread_id, test_review_item.checkpoint_id)
        ]

    async def test_missing_checkpoint_id_returns_error(
        self,
        authenticated_client: AsyncClient,
        db,
        test_project,
        test_document,
        test_tenant,
        hitl_resume_override,
    ):
        """Review item without checkpoint_id should fail resume."""
        _ = hitl_resume_override
        # Create review item WITHOUT checkpoint_id
        item_id = uuid4()
        bad_review = ReviewItemORM(
            id=item_id,
            item_id=item_id,
            item_type="test_review",
            tenant_id=test_tenant.id,
            current_status=ReviewStatus.PENDING_REVIEW_REQUIRED,
            impact_level=ImpactLevel.LOW,
            confidence=0.5,
            sla_due_date=datetime.now(timezone.utc),
            item_data={},
            review_metadata={},
            project_id=test_project.id,
            document_id=test_document.id,
            review_type="test",
            checkpoint_id=None,  # Missing!
            thread_id=None,
        )
        db.add(bad_review)
        await db.commit()

        response = await authenticated_client.post(
            f"/api/v1/hitl/resume/{bad_review.id}",
            json={"decision": "approve", "feedback": ""}
        )

        assert response.status_code in [400, 500], "Should fail without checkpoint_id"


class TestStateInjection:
    """Test approval/rejection data injection into workflow state."""

    async def test_approval_injects_human_feedback_field(
        self,
        authenticated_client: AsyncClient,
        test_review_item,
        hitl_resume_override,
    ):
        """Approval should inject decision into state.human_feedback field."""
        _, graph_app = hitl_resume_override
        feedback = "Human verified: all stakeholders confirmed"

        response = await authenticated_client.post(
            f"/api/v1/hitl/resume/{test_review_item.id}",
            json={"decision": "approve", "feedback": feedback}
        )

        assert response.status_code == 200, "Approval with feedback should succeed"
        assert graph_app.updates[-1][1]["human_feedback"] == feedback
        assert graph_app.updates[-1][1]["human_decision"] == "approve"
        assert graph_app.updates[-1][1]["human_approval_required"] is False

    async def test_rejection_injects_termination_reason(
        self,
        authenticated_client: AsyncClient,
        test_review_item,
        hitl_resume_override,
    ):
        """Rejection should inject reason into state for workflow termination."""
        _, graph_app = hitl_resume_override
        reason = "User rejected: data quality insufficient"

        response = await authenticated_client.post(
            f"/api/v1/hitl/resume/{test_review_item.id}",
            json={"decision": "reject", "feedback": reason}
        )

        assert response.status_code == 200, "Rejection with reason should succeed"
        assert graph_app.updates[-1][1]["human_decision"] == "reject"
        assert graph_app.updates[-1][1]["workflow_terminated"] is True
        assert graph_app.updates[-1][1]["termination_reason"] == reason


class TestErrorCases:
    """Test error handling for resume endpoint."""

    async def test_nonexistent_review_id_returns_404(self, authenticated_client: AsyncClient):
        """Resume with non-existent review_id should return 404."""
        fake_id = uuid4()
        response = await authenticated_client.post(
            f"/api/v1/hitl/resume/{fake_id}",
            json={"decision": "approve", "feedback": ""}
        )
        assert response.status_code == 404, "Should return 404 for non-existent review"

    async def test_already_processed_review_returns_200(
        self,
        authenticated_client: AsyncClient,
        approved_review_item,
    ):
        """Attempting to resume an already-processed review should be idempotent."""
        response = await authenticated_client.post(
            f"/api/v1/hitl/resume/{approved_review_item.id}",
            json={"decision": "approve", "feedback": ""}
        )
        assert response.status_code == 200, "Already-processed review should return current state"
        assert response.json()["status"] == "APPROVED"

    async def test_invalid_review_id_format_returns_422(self, authenticated_client: AsyncClient):
        """Invalid UUID format should return validation error."""
        response = await authenticated_client.post(
            "/api/v1/hitl/resume/not-a-uuid",
            json={"decision": "approve", "feedback": ""}
        )
        assert response.status_code == 422, "Should return 422 for invalid UUID format"

    async def test_missing_request_body_returns_422(self, authenticated_client: AsyncClient, test_review_item):
        """Missing request body should return validation error."""
        response = await authenticated_client.post(
            f"/api/v1/hitl/resume/{test_review_item.id}"
        )
        assert response.status_code == 422, "Should return 422 for missing body"


class TestConcurrency:
    """Test concurrent resume attempts."""

    async def test_duplicate_resume_attempts_are_idempotent(self, authenticated_client: AsyncClient, test_review_item):
        """Multiple resume calls for same review should be idempotent."""
        # First call
        await authenticated_client.post(
            f"/api/v1/hitl/resume/{test_review_item.id}",
            json={"decision": "approve", "feedback": "First call"}
        )

        # Second call (duplicate)
        response2 = await authenticated_client.post(
            f"/api/v1/hitl/resume/{test_review_item.id}",
            json={"decision": "approve", "feedback": "Second call"}
        )

        # Second call should either succeed (idempotent) or fail gracefully (400)
        assert response2.status_code in [200, 400], "Duplicate resume should be handled safely"
