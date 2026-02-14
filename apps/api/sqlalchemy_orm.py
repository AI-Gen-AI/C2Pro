"""
SQLAlchemy ORM models for the Documents module.
"""
from sqlalchemy import Column, DateTime, Enum, Integer, String, Uuid
from sqlalchemy.sql import func

from src.core.database import Base
from src.documents.domain.models import DocumentStatus, DocumentType


class DocumentORM(Base):
    __tablename__ = "documents"

    id = Column(Uuid, primary_key=True)
    project_id = Column(Uuid, nullable=False, index=True)
    tenant_id = Column(Uuid, nullable=False, index=True)

    filename = Column(String, nullable=False)
    storage_path = Column(String, nullable=False, unique=True)
    file_size_bytes = Column(Integer, nullable=False)

    document_type = Column(Enum(DocumentType), nullable=False)
    status = Column(Enum(DocumentStatus), nullable=False, default=DocumentStatus.UPLOADED)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )