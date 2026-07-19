"""
SQLAlchemy model for Dead Letter Queue (DLQ) failed tasks.
Part of TASK-BCK-022: Wire TriggerDocumentAnalysisUseCase to Celery ingestion completion.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base


class DLQFailedTask(Base):
    """
    Dead Letter Queue record for failed async tasks with retry logic.

    Supports:
    - Exponential backoff retry scheduling
    - Tenant isolation via tenant_id
    - Task metadata preservation via payload_json
    - Error tracking via error_message and error_traceback
    """
    __tablename__ = "dlq_failed_tasks"
    __table_args__ = (
        Index("idx_dlq_failed_tasks_tenant_status", "tenant_id", "status"),
        Index(
            "idx_dlq_failed_tasks_next_retry",
            "next_retry_at",
            postgresql_where=text("status = 'pending' OR status = 'retrying'"),
        ),
        Index("idx_dlq_failed_tasks_document_id", "document_id"),
    )

    # Primary key
    id = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))

    # Tenant isolation
    tenant_id = Column(PG_UUID(as_uuid=True), nullable=False, comment="Tenant isolation")

    # Task metadata
    task_type = Column(
        String(100),
        nullable=False,
        comment="Type of task that failed (e.g., document_analysis)",
    )
    document_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        comment="Related document ID if applicable",
    )
    payload_json = Column(
        JSONB,
        nullable=False,
        comment="Original task payload for retry",
    )

    # Error tracking
    error_message = Column(Text, nullable=False, comment="Error message from failure")
    error_traceback = Column(Text, nullable=True, comment="Full error traceback for debugging")

    # Retry logic
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="Number of retry attempts",
    )
    max_retries: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("3"),
        comment="Maximum retry attempts before exhaustion",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'pending'"),
        comment="Status: pending, retrying, exhausted",
    )

    # Timestamps
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
    next_retry_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment="Scheduled time for next retry (exponential backoff)",
    )

    # Relationships
    document = relationship("DocumentORM", back_populates="dlq_tasks")

    def __repr__(self) -> str:
        return (
            f"<DLQFailedTask(id={self.id}, task_type={self.task_type}, "
            f"status={self.status}, retry_count={self.retry_count})>"
        )
