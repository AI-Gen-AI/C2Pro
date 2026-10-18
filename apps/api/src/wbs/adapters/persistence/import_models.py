"""WBS import sources ORM (PC-2b.3 #922): the immutable, deterministic parse of ONE source revision.

Mirrors Alembic revision ``20261007_0003``: same table, constraint names and (via ``import_ddl``)
the same guard function, so create_all-built test schemas enforce the same invariants as migrated
databases. RLS lives in the migration only (proven on a migrated database with a NOBYPASSRLS role).

An import source is INPUT: it never creates a DRAFT, never writes canonical WBS and confers no
authority. Its ``status`` only describes the deterministic parse.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    DDL,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    event,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.projects.adapters.persistence.models import ProjectORM  # noqa: F401 - FK target
from src.temporal.adapters.persistence.models import DocumentRevisionORM  # noqa: F401 - FK target
from src.wbs.adapters.persistence.governance_ddl import DIGEST_PATTERN_SQL
from src.wbs.adapters.persistence.import_ddl import (
    IMPORT_FORMAT_CHECK,
    IMPORT_SOURCES_GUARD_FUNCTION_SQL,
    IMPORT_SOURCES_TRIGGER_SQL,
    IMPORT_STATUS_CHECK,
)

_DDL: Any = DDL
_UUID = PGUUID(as_uuid=True)
_D = DIGEST_PATTERN_SQL


class WBSImportSourceORM(Base):
    """One deterministic parse of one immutable WBS source revision (insert-only)."""

    __tablename__ = "wbs_import_sources"

    id: Mapped[UUID] = mapped_column(_UUID, primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    project_id: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    document_id: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    revision_id: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    blob_hash: Mapped[str] = mapped_column(Text, nullable=False)
    format: Mapped[str] = mapped_column(Text, nullable=False)
    parser_id: Mapped[str] = mapped_column(Text, nullable=False)
    parser_version: Mapped[str] = mapped_column(Text, nullable=False)
    parse_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    parse_config_digest: Mapped[str] = mapped_column(Text, nullable=False)
    import_key: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_schema_version: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    snapshot_digest: Mapped[str] = mapped_column(Text, nullable=False)
    diagnostics: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    warning_count: Mapped[int] = mapped_column(Integer, nullable=False)
    blocking_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    created_by_kind: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "id", name="uq_wbs_import_sources_tenant_project_id"),
        UniqueConstraint("tenant_id", "import_key", name="uq_wbs_import_sources_import_key"),
        ForeignKeyConstraint(
            ["tenant_id", "project_id"], ["projects.tenant_id", "projects.id"],
            name="fk_wbs_import_sources_project", ondelete="CASCADE",
        ),
        # The exact revision of the exact document of the same tenant and project. NO ACTION: an
        # individual document deletion can never silently remove an import's source.
        ForeignKeyConstraint(
            ["revision_id", "document_id", "project_id", "tenant_id"],
            ["document_revisions.revision_id", "document_revisions.document_id", "document_revisions.project_id",
             "document_revisions.tenant_id"],
            name="fk_wbs_import_sources_revision", ondelete="NO ACTION",
        ),
        CheckConstraint("blob_hash ~ '^[0-9a-f]{64}$'", name="ck_wbs_import_sources_blob_hash"),
        CheckConstraint("format IN ('xlsx', 'csv', 'json')", name="ck_wbs_import_sources_format"),
        CheckConstraint(IMPORT_FORMAT_CHECK, name="ck_wbs_import_sources_parser"),
        CheckConstraint("parser_version ~ '^v[0-9]+$'", name="ck_wbs_import_sources_parser_version"),
        CheckConstraint("jsonb_typeof(parse_config) = 'object'", name="ck_wbs_import_sources_parse_config"),
        CheckConstraint(f"parse_config_digest ~ {_D}", name="ck_wbs_import_sources_parse_config_digest"),
        CheckConstraint(f"import_key ~ {_D}", name="ck_wbs_import_sources_import_key"),
        CheckConstraint("snapshot_schema_version = 'wbs-import-snapshot/v1'", name="ck_wbs_import_sources_schema"),
        CheckConstraint("jsonb_typeof(snapshot) = 'object'", name="ck_wbs_import_sources_snapshot"),
        CheckConstraint(f"snapshot_digest ~ {_D}", name="ck_wbs_import_sources_snapshot_digest"),
        CheckConstraint("jsonb_typeof(diagnostics) = 'array'", name="ck_wbs_import_sources_diagnostics"),
        CheckConstraint("row_count >= 0 AND warning_count >= 0 AND blocking_count >= 0",
                        name="ck_wbs_import_sources_counts"),
        CheckConstraint("status IN ('READY', 'READY_WITH_WARNINGS', 'INVALID')", name="ck_wbs_import_sources_status"),
        CheckConstraint(IMPORT_STATUS_CHECK, name="ck_wbs_import_sources_status_counts"),
        CheckConstraint("created_by_kind = 'human'", name="ck_wbs_import_sources_created_by_kind"),
        Index("ix_wbs_import_sources_document", "tenant_id", "project_id", "document_id"),
    )


event.listen(WBSImportSourceORM.__table__, "after_create",
             _DDL(IMPORT_SOURCES_GUARD_FUNCTION_SQL).execute_if(dialect="postgresql"))
event.listen(WBSImportSourceORM.__table__, "after_create",
             _DDL(IMPORT_SOURCES_TRIGGER_SQL).execute_if(dialect="postgresql"))
