"""
DLQ (Dead Letter Queue) Service for failed task retry management.
Part of TASK-BCK-022: Wire TriggerDocumentAnalysisUseCase to Celery ingestion completion.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select

from src.core.database import get_session_with_tenant
from src.core.dlq.models import DLQFailedTask


class DLQService:
    """
    Service for managing failed tasks in the Dead Letter Queue.

    Implements exponential backoff retry logic:
    - Retry 0 → 1: wait 2^1 = 2 minutes
    - Retry 1 → 2: wait 2^2 = 4 minutes
    - Retry 2 → 3: wait 2^3 = 8 minutes
    - After max_retries (default 3), mark as 'exhausted'
    """

    async def push(
        self,
        *,
        tenant_id: UUID,
        task_type: str,
        document_id: UUID | None,
        payload: dict[str, Any],
        error_message: str,
        error_traceback: str | None = None,
        max_retries: int = 3,
    ) -> UUID:
        """
        Push a failed task to the DLQ with initial status 'pending'.

        Args:
            tenant_id: Tenant identifier for isolation
            task_type: Type of task (e.g., "document_analysis")
            document_id: Related document ID (nullable)
            payload: Original task payload for retry (JSON-serializable dict)
            error_message: Brief error message
            error_traceback: Full error traceback (optional)
            max_retries: Maximum retry attempts before exhaustion (default 3)

        Returns:
            UUID: DLQ record ID for tracking
        """
        async with get_session_with_tenant(tenant_id) as session:
            dlq_record = DLQFailedTask(
                id=uuid4(),
                tenant_id=tenant_id,
                task_type=task_type,
                document_id=document_id,
                payload_json=payload,
                error_message=error_message,
                error_traceback=error_traceback,
                retry_count=0,
                max_retries=max_retries,
                status="pending",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                next_retry_at=None,  # First retry is immediate
            )

            session.add(dlq_record)
            await session.commit()
            await session.refresh(dlq_record)

            return dlq_record.id

    async def increment_retry(self, dlq_id: UUID) -> None:
        """
        Increment retry count and calculate next retry time with exponential backoff.

        Retry Logic:
        - If retry_count < max_retries: status='retrying', next_retry_at = now + 2^(retry_count) minutes
        - If retry_count >= max_retries: status='exhausted', next_retry_at = None

        Args:
            dlq_id: DLQ record identifier
        """
        # Fetch record to determine tenant_id for session context
        from src.core.database import get_raw_session

        async with get_raw_session() as session:
            # First, fetch the record to get tenant_id
            result = await session.execute(
                select(DLQFailedTask).where(DLQFailedTask.id == dlq_id)
            )
            dlq_record = result.scalar_one_or_none()

            if dlq_record is None:
                raise ValueError(f"DLQ record {dlq_id} not found")

            tenant_id = dlq_record.tenant_id

        # Now use tenant-scoped session for update
        async with get_session_with_tenant(tenant_id) as session:
            # Fetch record again in tenant context
            result = await session.execute(
                select(DLQFailedTask).where(DLQFailedTask.id == dlq_id)
            )
            dlq_record = result.scalar_one()

            # Increment retry count
            new_retry_count = dlq_record.retry_count + 1
            now = datetime.now(UTC)

            # Determine new status and next_retry_at
            if new_retry_count >= dlq_record.max_retries:
                # Exhausted after max retries
                new_status = "exhausted"
                next_retry_at = None
            else:
                # Still have retries left - calculate exponential backoff
                new_status = "retrying"
                backoff_minutes = 2 ** new_retry_count
                next_retry_at = now + timedelta(minutes=backoff_minutes)

            # Update record
            dlq_record.retry_count = new_retry_count
            dlq_record.status = new_status
            dlq_record.updated_at = now
            dlq_record.next_retry_at = next_retry_at

            await session.commit()

    async def get_pending_retries(self, tenant_id: UUID) -> list[DLQFailedTask]:
        """
        Get all DLQ tasks that are ready for retry.

        Returns tasks where:
        - status IN ('pending', 'retrying')
        - next_retry_at IS NULL OR next_retry_at <= NOW()

        Args:
            tenant_id: Tenant identifier for isolation

        Returns:
            List of DLQ records ready for retry
        """
        async with get_session_with_tenant(tenant_id) as session:
            now = datetime.now(UTC)

            result = await session.execute(
                select(DLQFailedTask)
                .where(
                    DLQFailedTask.status.in_(["pending", "retrying"]),
                    (DLQFailedTask.next_retry_at.is_(None)) | (DLQFailedTask.next_retry_at <= now),
                )
                .order_by(DLQFailedTask.created_at.asc())
            )

            return list(result.scalars().all())

    async def get_by_status(self, tenant_id: UUID, status: str) -> list[DLQFailedTask]:
        """
        Get all DLQ tasks with a specific status.

        Args:
            tenant_id: Tenant identifier for isolation
            status: Status to filter by ('pending', 'retrying', 'exhausted')

        Returns:
            List of DLQ records with matching status
        """
        async with get_session_with_tenant(tenant_id) as session:
            result = await session.execute(
                select(DLQFailedTask)
                .where(DLQFailedTask.status == status)
                .order_by(DLQFailedTask.created_at.desc())
            )

            return list(result.scalars().all())

    async def get_by_id(self, dlq_id: UUID) -> DLQFailedTask | None:
        """
        Get a DLQ record by ID (no tenant filtering for admin access).

        Args:
            dlq_id: DLQ record identifier

        Returns:
            DLQ record or None if not found
        """
        from src.core.database import get_raw_session

        async with get_raw_session() as session:
            result = await session.execute(
                select(DLQFailedTask).where(DLQFailedTask.id == dlq_id)
            )

            return result.scalar_one_or_none()
