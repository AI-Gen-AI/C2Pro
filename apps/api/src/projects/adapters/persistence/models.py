"""
SQLAlchemy ORM model for Project (minimal).

Transitional model to satisfy relationships in other modules.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base


class ProjectORM(Base):
    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    documents = relationship("DocumentORM", back_populates="project", lazy="selectin")
    stakeholders = relationship("StakeholderORM", back_populates="project", lazy="selectin")
    wbs_items = relationship("WBSItemORM", back_populates="project", lazy="selectin")
    bom_items = relationship("BOMItemORM", back_populates="project", lazy="selectin")
    analyses = relationship("Analysis", back_populates="project", lazy="selectin")
    alerts = relationship("Alert", back_populates="project", lazy="selectin")
