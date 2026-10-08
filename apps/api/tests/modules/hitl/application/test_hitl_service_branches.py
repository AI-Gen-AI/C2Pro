"""
Branch coverage tests for HumanInTheLoopService error paths.

Test Suite: TS-I11-HITL-APP-001
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.hitl.application.human_in_the_loop_service import (
    HumanInTheLoopService,
    StaleCritiqueReviewEvidence,
)
from src.modules.hitl.domain.entities import (
    ImpactLevel,
    ReviewItem,
    ReviewStatus,
)
from src.modules.hitl.domain.services import ConfidenceRouter
from src.modules.hitl.ports.notification_service import INotificationService
from src.modules.hitl.ports.review_queue_repository import IReviewQueueRepository


@pytest.fixture
def mock_repo() -> AsyncMock:
    repo = AsyncMock(spec=IReviewQueueRepository)
    return repo


@pytest.fixture
def mock_notification() -> AsyncMock:
    svc = AsyncMock(spec=INotificationService)
    return svc


@pytest.fixture
def hitl_service(mock_repo: AsyncMock, mock_notification: AsyncMock) -> HumanInTheLoopService:
    return HumanInTheLoopService(
        review_queue_repo=mock_repo,
        notification_service=mock_notification,
        confidence_router=ConfidenceRouter(
            low_confidence_threshold=0.3,
            high_confidence_threshold=0.8,
        ),
    )


@pytest.mark.asyncio
class TestApproveItemBranches:
    async def test_approve_item_not_found_raises(
        self,
        hitl_service: HumanInTheLoopService,
        mock_repo: AsyncMock,
    ) -> None:
        mock_repo.get_review_item.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await hitl_service.approve_item(
                item_id=uuid4(),
                reviewer_id=uuid4(),
                reviewer_name="reviewer",
            )

    async def test_approve_item_wrong_status_raises(
        self,
        hitl_service: HumanInTheLoopService,
        mock_repo: AsyncMock,
    ) -> None:
        item = ReviewItem(
            item_id=uuid4(),
            item_type="CoherenceAlert",
            current_status=ReviewStatus.CLOSED,
            confidence=0.5,
            impact_level=ImpactLevel.LOW,
            created_at=datetime.now(),
            sla_due_date=datetime.now() + timedelta(days=1),
            item_data={},
        )
        mock_repo.get_review_item.return_value = item

        with pytest.raises(ValueError, match="cannot be approved"):
            await hitl_service.approve_item(
                item_id=item.item_id,
                reviewer_id=uuid4(),
                reviewer_name="reviewer",
            )


@pytest.mark.asyncio
class TestReleaseItemBranches:
    async def test_release_item_not_found_raises(
        self,
        hitl_service: HumanInTheLoopService,
        mock_repo: AsyncMock,
    ) -> None:
        mock_repo.get_review_item.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await hitl_service.release_item(item_id=uuid4())

    async def test_release_item_wrong_tenant_raises(
        self,
        hitl_service: HumanInTheLoopService,
        mock_repo: AsyncMock,
    ) -> None:
        item_tenant_id = uuid4()
        reviewer_tenant_id = uuid4()
        item = ReviewItem(
            item_id=uuid4(),
            item_type="CoherenceAlert",
            current_status=ReviewStatus.APPROVED,
            confidence=0.9,
            impact_level=ImpactLevel.HIGH,
            created_at=datetime.now(),
            sla_due_date=datetime.now() + timedelta(days=1),
            approved_by="reviewer",
            approved_at=datetime.now(),
            item_data={},
            metadata={"tenant_id": str(item_tenant_id)},
        )
        mock_repo.get_review_item.return_value = item

        with pytest.raises(ValueError, match="tenant mismatch"):
            await hitl_service.release_item(
                item_id=item.item_id,
                reviewer_tenant_id=reviewer_tenant_id,
            )

    async def test_release_item_not_approved_raises(
        self,
        hitl_service: HumanInTheLoopService,
        mock_repo: AsyncMock,
    ) -> None:
        item = ReviewItem(
            item_id=uuid4(),
            item_type="CoherenceAlert",
            current_status=ReviewStatus.PENDING_REVIEW_REQUIRED,
            confidence=0.5,
            impact_level=ImpactLevel.MEDIUM,
            created_at=datetime.now(),
            sla_due_date=datetime.now() + timedelta(days=1),
            item_data={},
        )
        mock_repo.get_review_item.return_value = item

        with pytest.raises(ValueError, match="requires human approval"):
            await hitl_service.release_item(item_id=item.item_id)



@pytest.mark.asyncio
class TestExistingCritiqueEvidenceAuthority:
    async def test_active_review_rejects_changed_observations_without_rebinding(
        self, hitl_service: HumanInTheLoopService, mock_repo: AsyncMock,
    ) -> None:
        document = uuid4()
        existing = ReviewItem(
            item_id=document,
            item_type="contract",
            current_status=ReviewStatus.PENDING_REVIEW_REQUIRED,
            confidence=0.8,
            impact_level=ImpactLevel.HIGH,
            created_at=datetime.now(),
            sla_due_date=datetime.now() + timedelta(days=1),
            item_data={"critique_observations": [{"claim": "old", "claim_verified": False}]},
            metadata={"review_type": "analysis_critique"},
        )
        mock_repo.find_active_review.return_value = existing
        with pytest.raises(StaleCritiqueReviewEvidence):
            await hitl_service.route_for_review(
                item_id=document,
                item_type="contract",
                confidence=0.8,
                impact_level=ImpactLevel.HIGH,
                item_data={
                    "critique_observations": [{"claim": "new", "claim_verified": False}]
                },
                metadata={"document_id": str(document), "review_type": "analysis_critique"},
            )
        mock_repo.add_review_item.assert_not_called()
        mock_repo.update_review_item.assert_not_called()

    async def test_identical_active_critique_evidence_reuses_review_without_update(
        self, hitl_service: HumanInTheLoopService, mock_repo: AsyncMock,
    ) -> None:
        document = uuid4()
        observations = [{"claim": "same", "claim_verified": False}]
        existing = ReviewItem(
            item_id=document,
            item_type="contract",
            current_status=ReviewStatus.PENDING_REVIEW_REQUIRED,
            confidence=0.8,
            impact_level=ImpactLevel.HIGH,
            created_at=datetime.now(),
            sla_due_date=datetime.now() + timedelta(days=1),
            item_data={"critique_observations": observations},
            metadata={"review_type": "analysis_critique"},
        )
        mock_repo.find_active_review.return_value = existing
        status = await hitl_service.route_for_review(
            item_id=document,
            item_type="contract",
            confidence=0.8,
            impact_level=ImpactLevel.HIGH,
            item_data={"critique_observations": observations},
            metadata={"document_id": str(document), "review_type": "analysis_critique"},
        )
        assert status is ReviewStatus.PENDING_REVIEW_REQUIRED
        mock_repo.add_review_item.assert_not_called()
        mock_repo.update_review_item.assert_not_called()



@pytest.mark.asyncio
async def test_late_candidate_binding_does_not_block_same_evidence_review() -> None:
    """#714: N13 can first create the review before artifact binding is durable."""
    from unittest.mock import AsyncMock

    from src.modules.hitl.application.human_in_the_loop_service import (
        HumanInTheLoopService,
    )

    document = uuid4()
    evidence = [{"claim": "Read the original", "claim_verified": False}]
    existing = ReviewItem(
        item_id=document,
        item_type="contract",
        current_status=ReviewStatus.PENDING_REVIEW_REQUIRED,
        confidence=0.7,
        impact_level=ImpactLevel.HIGH,
        created_at=datetime.now(),
        sla_due_date=datetime.now() + timedelta(days=1),
        item_data={"critique_observations": evidence},
        metadata={
            "review_type": "analysis_critique",
            "candidate_binding": {"artifact_id": "bound-after-initial-review"},
        },
    )
    repo = AsyncMock(spec=IReviewQueueRepository)
    repo.find_active_review.return_value = existing
    service = HumanInTheLoopService(
        review_queue_repo=repo,
        notification_service=AsyncMock(spec=INotificationService),
        confidence_router=ConfidenceRouter(),
    )
    status = await service.route_for_review(
        item_id=document,
        item_type="contract",
        confidence=0.7,
        impact_level=ImpactLevel.HIGH,
        item_data={"critique_observations": evidence},
        metadata={"document_id": str(document), "review_type": "analysis_critique"},
    )
    assert status is ReviewStatus.PENDING_REVIEW_REQUIRED
    repo.update_review_item.assert_not_called()


@pytest.mark.asyncio
async def test_two_conflicting_explicit_candidate_bindings_fail_closed() -> None:
    """A genuine candidate rebind may not silently inherit the prior review."""
    from unittest.mock import AsyncMock

    from src.modules.hitl.application.human_in_the_loop_service import (
        HumanInTheLoopService,
        StaleCritiqueReviewEvidence,
    )

    document = uuid4()
    evidence = [{"claim": "Same text", "claim_verified": False}]
    existing = ReviewItem(
        item_id=document, item_type="contract",
        current_status=ReviewStatus.PENDING_REVIEW_REQUIRED,
        confidence=0.7, impact_level=ImpactLevel.HIGH,
        created_at=datetime.now(), sla_due_date=datetime.now() + timedelta(days=1),
        item_data={"critique_observations": evidence},
        metadata={
            "review_type": "analysis_critique",
            "candidate_binding": {"artifact_hash": "a" * 64},
        },
    )
    repo = AsyncMock(spec=IReviewQueueRepository)
    repo.find_active_review.return_value = existing
    service = HumanInTheLoopService(
        review_queue_repo=repo,
        notification_service=AsyncMock(spec=INotificationService),
        confidence_router=ConfidenceRouter(),
    )
    with pytest.raises(StaleCritiqueReviewEvidence):
        await service.route_for_review(
            item_id=document, item_type="contract", confidence=0.7,
            impact_level=ImpactLevel.HIGH,
            item_data={"critique_observations": evidence},
            metadata={
                "document_id": str(document),
                "review_type": "analysis_critique",
                "candidate_binding": {"artifact_hash": "b" * 64},
            },
        )
    repo.update_review_item.assert_not_called()
