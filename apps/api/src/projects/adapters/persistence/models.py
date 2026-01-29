"""
SQLAlchemy ORM model for Project.

This is the persistence adapter for the Project domain entity.
Maps domain concepts to database tables.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base


class ProjectORM(Base):
    __tablename__ = "projects"

    # Primary identifiers
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)

    # Basic information
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)

    # Project classification
    project_type: Mapped[str] = mapped_column(String(50), nullable=False, default="construction")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft", index=True)

    # Financial
    estimated_budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")

    # Timeline
    start_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Analysis state
    coherence_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_analysis_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Project metadata (flexible JSON storage)
    # Note: Column is named 'metadata_json' to avoid conflict with SQLAlchemy's reserved 'metadata' attribute
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True, default=dict)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    documents = relationship("DocumentORM", back_populates="project", lazy="selectin")
    stakeholders = relationship("StakeholderORM", back_populates="project", lazy="selectin")
    wbs_items = relationship("WBSItemORM", back_populates="project", lazy="selectin")
    bom_items = relationship("BOMItemORM", back_populates="project", lazy="selectin")
    analyses = relationship("Analysis", back_populates="project", lazy="selectin")
    alerts = relationship("Alert", back_populates="project", lazy="selectin")
