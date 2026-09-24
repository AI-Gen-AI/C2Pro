
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
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text

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

    async def load_checkpoint(self, thread_id: str, checkpoint_id: str | None = None) -> dict[str, str]:
        self.loaded.append((thread_id, checkpoint_id))
        return {"thread_id": thread_id, "checkpoint_id": checkpoint_id}

    async def restore_checkpoint(self, thread_id: str, checkpoint_id: str | None = None):
        """C2PRO P0b true-resume hotfix: the resume layer needs the exact
        checkpoint CONFIG (thread_id + checkpoint_ns + checkpoint_id), not
        just the checkpoint body."""
        from src.modules.hitl.adapters.checkpoint_service import CheckpointRestore

        self.loaded.append((thread_id, checkpoint_id))
        configurable: dict[str, object] = {"thread_id": thread_id, "checkpoint_ns": ""}
        if checkpoint_id:
            configurable["checkpoint_id"] = checkpoint_id
        return CheckpointRestore(
            checkpoint={"thread_id": thread_id, "checkpoint_id": checkpoint_id},
            config={"configurable": configurable},
            metadata={},
        )

    def extract_state(self, checkpoint: dict[str, str]) -> dict[str, object]:
        return {
            "thread_id": checkpoint["thread_id"],
            "checkpoint_id": checkpoint["checkpoint_id"],
        }


class _FakeGraphApp:
    """Records state updates and resume invocations without real LangGraph runtime."""

    def __init__(self, tenant_id: UUID) -> None:
        self.updates: list[tuple[dict[str, object], dict[str, object]]] = []
        self.invocations: list[tuple[object, dict[str, object]]] = []
        self.resume_decisions: list[str | None] = []
        # In production the tenant comes from the graph STATE, which this
        # fake has no checkpoint to carry; the fixture supplies it instead.
        self._tenant_id = tenant_id
        self._ran = False

    async def aupdate_state(
        self,
        config: dict[str, object],
        state: dict[str, object],
    ) -> dict[str, object]:
        """Fork the given checkpoint, as real LangGraph does.

        C2PRO P0b crash-safe resume V3: each attempt resumes a CHILD of the
        interrupt checkpoint, because re-resuming a checkpoint re-delivers
        the FIRST attempt's payload. Returning the new config is part of
        that contract, so the fake has to return one too.
        """
        self.updates.append((config, dict(state)))
        configurable = dict(config.get("configurable") or {})
        parent = configurable.get("checkpoint_id") or "cp"
        configurable["checkpoint_id"] = f"{parent}-fork-{len(self.updates)}"
        return {**config, "configurable": configurable}

    async def aget_state(self, config: dict[str, object]) -> object:
        """Report terminality the way the use case verifies it.

        `ainvoke` returning is NOT evidence the graph finished, so the use
        case asks LangGraph for the thread's state and treats an empty
        `next`/`tasks` as END. Before any resume has run, this thread is
        still sitting at its interrupt.
        """
        configurable = dict(config.get("configurable") or {})
        if not self._ran:
            return SimpleNamespace(
                next=("human_interrupt",), tasks=(), config={"configurable": configurable}
            )
        configurable["checkpoint_id"] = "cp-terminal"
        return SimpleNamespace(next=(), tasks=(), config={"configurable": configurable})

    async def ainvoke(
        self,
        state: object,
        config: dict[str, object],
    ) -> dict[str, object]:
        """C2PRO P0b true-resume hotfix: resume arrives as
        Command(resume={"decision": ..., "feedback": ...}); the decision is
        read FROM it, mirroring interrupt()'s return value in the real node.
        """
        from tests.support.hitl_resume_fakes import decision_from_resume

        self.invocations.append((state, config))
        self._ran = True
        decision, feedback = decision_from_resume(state)
        self.resume_decisions.append(decision)
        if decision == "reject":
            return {
                "human_decision": "reject",
                "human_approval_required": False,
                "workflow_terminated": True,
                "termination_reason": feedback,
            }
        analysis_id = await self._run_real_n17(state)
        return {"analysis_id": str(analysis_id), "human_decision": decision}

    async def _run_real_n17(self, resume_signal: object) -> object:
        """Persist for real, exactly as the production N17 node does.

        This fake stands in for the LangGraph RUNTIME, not for durability.
        Returning a made-up analysis_id would assert a fiction: under V3 an
        approval is only finalized when the analysis is genuinely durable
        for this operation, so a fake that persists nothing would prove the
        endpoint can report a success that never happened -- the exact
        failure this design removes.
        """
        from src.analysis.application.persist_resume_analysis import (
            ResumeProvenance,
            persist_resume_analysis_atomically,
        )
        from src.core.database import get_session_with_tenant

        payload = getattr(resume_signal, "resume", None) or {}
        raw = payload.get("resume_provenance") or {}
        provenance = ResumeProvenance.from_state(
            {"resume_provenance": raw, "tenant_id": str(self._tenant_id)}
        )
        assert provenance is not None, "the resume must carry attempt provenance"

        # The operation row is the authority for what this resume is about.
        async with get_session_with_tenant(provenance.tenant_id) as session:
            row = (
                await session.execute(
                    text(
                        "SELECT project_id, document_id FROM resume_operations "
                        " WHERE id = cast(:op as uuid)"
                    ),
                    {"op": str(provenance.operation_id)},
                )
            ).first()

        result = await persist_resume_analysis_atomically(
            state={
                "project_id": str(row.project_id),
                "document_id": str(row.document_id),
                "tenant_id": str(provenance.tenant_id),
                "extracted_risks": [],
                "extracted_wbs": [],
                "coherence_score": 90,
                "coherence_breakdown": {"overall": 90},
            },
            provenance=provenance,
        )
        return result.analysis_id


@pytest_asyncio.fixture
async def hitl_resume_override(
    app,
    db,
    test_user,
) -> AsyncGenerator[tuple[_FakeCheckpointService, _FakeGraphApp], None]:
    """Override the resume workflow dependency with deterministic collaborators."""
    checkpoint_service = _FakeCheckpointService()
    graph_app = _FakeGraphApp(tenant_id=test_user.tenant_id)

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
        tenant_id=test_project.tenant_id,
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
        sla_due_date=datetime.now(UTC).replace(tzinfo=None),
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
        sla_due_date=datetime.now(UTC).replace(tzinfo=None),
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
        _, graph_app = hitl_resume_override
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
        assert graph_app.invocations, "Approve must invoke LangGraph to resume"
        # C2PRO P0b true-resume hotfix: the first argument is no longer
        # None (which did NOT resume) -- it is a Command carrying the
        # decision.
        assert graph_app.resume_decisions[-1] == "approve"

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
            sla_due_date=datetime.now(UTC).replace(tzinfo=None),
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

    async def test_resume_succeeds_with_thread_id_but_no_checkpoint_id(
        self,
        authenticated_client: AsyncClient,
        db,
        test_project,
        test_document,
        test_tenant,
        hitl_resume_override,
    ):
        """C2PRO P0b HITL resume hotfix (section 2/5): thread_id alone must
        be sufficient to resume. checkpoint_id, when never captured for any
        reason, must never permanently block a legitimate pending review --
        CheckpointService.load_checkpoint already falls back to the latest
        checkpoint for a thread, which for a freshly-interrupted thread IS
        the interrupt point.
        """
        item_id = uuid4()
        review = ReviewItemORM(
            id=item_id,
            item_id=item_id,
            item_type="test_review",
            tenant_id=test_tenant.id,
            current_status=ReviewStatus.PENDING_REVIEW_REQUIRED,
            impact_level=ImpactLevel.HIGH,
            confidence=0.2,
            sla_due_date=datetime.now(UTC).replace(tzinfo=None),
            item_data={},
            review_metadata={},
            project_id=test_project.id,
            document_id=test_document.id,
            review_type="analysis_critique",
            checkpoint_id=None,  # never captured -- must not be fatal
            thread_id=f"document:{test_document.id}:analysis",
        )
        db.add(review)
        await db.commit()

        response = await authenticated_client.post(
            f"/api/v1/hitl/resume/{review.id}",
            json={"decision": "approve", "feedback": "thread_id alone is sufficient"},
        )

        assert response.status_code == 200, (
            f"Resume must succeed on thread_id alone: {response.text}"
        )
        assert response.json()["status"] in {"resumed", "APPROVED"}


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
        # C2PRO P0b true-resume hotfix: the decision is no longer injected
        # into stored state via aupdate_state -- it travels in
        # Command(resume=...), which is what interrupt() returns inside the
        # node. Assert the real carrier.
        from tests.support.hitl_resume_fakes import decision_from_resume

        resumed_decision, resumed_feedback = decision_from_resume(graph_app.invocations[-1][0])
        assert resumed_decision == "approve"
        assert resumed_feedback == feedback

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
        # See the approve case: the rejection now travels in the resume
        # command and the graph itself terminates, rather than a
        # "workflow_terminated" flag being patched into stored state.
        from tests.support.hitl_resume_fakes import decision_from_resume

        resumed_decision, resumed_feedback = decision_from_resume(graph_app.invocations[-1][0])
        assert resumed_decision == "reject"
        assert resumed_feedback == reason


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
