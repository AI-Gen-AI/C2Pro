"""
SQLAlchemy implementation of the IDocumentRepository port.
Handles persistence for Document and Clause entities.

Refers to Suite ID: TS-INT-DB-CLS-001, TS-INT-DB-DOC-001.
"""
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import column, func, inspect, select, table, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.models import Alert
from src.documents.adapters.persistence.models import ClauseORM, DocumentORM
from src.documents.domain.models import (
    Clause,
    Document,
    DocumentAlertHistoryEntry,
    DocumentAlertSignal,
    DocumentEvidenceAlert,
    DocumentHistorySnapshot,
    DocumentStatus,
)
from src.documents.ports.document_repository import IDocumentRepository
from src.projects.adapters.persistence.models import ProjectORM


class SqlAlchemyDocumentRepository(IDocumentRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _normalize_naive_utc(value: datetime | None) -> datetime | None:
        """Convert aware UTC datetimes to naive UTC for legacy TIMESTAMP columns."""
        if value is None:
            return None
        if value.tzinfo is None:
            return value
        return value.astimezone(UTC).replace(tzinfo=None)

    async def _get_current_tenant_id(self) -> UUID | None:
        try:
            result = await self.session.execute(
                text("SELECT current_setting('app.current_tenant', true)")
            )
        except Exception:
            return None
        tenant_value = result.scalar_one_or_none()
        if not tenant_value:
            return None
        try:
            return UUID(str(tenant_value))
        except ValueError:
            return None

    async def _apply_document_tenant_filter(self, stmt):
        tenant_id = await self._get_current_tenant_id()
        if tenant_id is None:
            return stmt
        projects = table("projects", column("id"), column("tenant_id"))
        return stmt.join(projects, projects.c.id == DocumentORM.project_id).where(
            projects.c.tenant_id == tenant_id
        )

    async def _apply_clause_tenant_filter(self, stmt):
        tenant_id = await self._get_current_tenant_id()
        if tenant_id is None:
            return stmt
        projects = table("projects", column("id"), column("tenant_id"))
        return stmt.join(projects, projects.c.id == ClauseORM.project_id).where(
            projects.c.tenant_id == tenant_id
        )

    # --- Mapper functions ---
    def _to_domain_document(self, orm_document: DocumentORM) -> Document:
        if orm_document is None:
            return None
        # Avoid triggering lazy-loads in async context (MissingGreenlet).
        # Only map clauses when they are already loaded in instance state.
        clauses: list[Clause] = []
        state = inspect(orm_document)
        if "clauses" in state.mapper.attrs and "clauses" not in state.unloaded:
            raw_clauses = state.dict.get("clauses") or []
            clauses = [self._to_domain_clause(orm_clause) for orm_clause in raw_clauses]

        domain_document = Document(
            id=orm_document.id,
            project_id=orm_document.project_id,
            document_type=orm_document.document_type,
            filename=orm_document.filename,
            file_format=orm_document.file_format,
            storage_url=orm_document.storage_url,
            storage_encrypted=orm_document.storage_encrypted,
            file_size_bytes=orm_document.file_size_bytes,
            upload_status=orm_document.upload_status,
            parsed_at=orm_document.parsed_at,
            parsing_error=orm_document.parsing_error,
            retention_until=orm_document.retention_until,
            created_by=orm_document.created_by,
            created_at=orm_document.created_at,
            updated_at=orm_document.updated_at,
            document_metadata=orm_document.document_metadata or {},
            clauses=clauses,  # Assign the list of domain clauses
            version=orm_document.version,  # TASK-BCK-023
            file_hash=orm_document.file_hash,  # TASK-BCK-023
        )
        return domain_document

    def _to_domain_clause(self, orm_clause: ClauseORM) -> Clause:
        if orm_clause is None:
            return None
        domain_clause = Clause(
            id=orm_clause.id,
            project_id=orm_clause.project_id,
            document_id=orm_clause.document_id,
            clause_code=orm_clause.clause_code,
            clause_type=orm_clause.clause_type,
            title=orm_clause.title,
            full_text=orm_clause.full_text,
            text_start_offset=orm_clause.text_start_offset,
            text_end_offset=orm_clause.text_end_offset,
            extracted_entities=orm_clause.extracted_entities or {},
            extraction_confidence=orm_clause.extraction_confidence,
            extraction_model=orm_clause.extraction_model,
            manually_verified=orm_clause.manually_verified,
            verified_at=orm_clause.verified_at
        )
        return domain_clause

    def _to_orm_document(self, domain_document: Document) -> DocumentORM:
        now = self._normalize_naive_utc(datetime.now(UTC))
        orm_document = DocumentORM(
            id=domain_document.id,
            project_id=domain_document.project_id,
            document_type=domain_document.document_type,
            filename=domain_document.filename,
            file_format=domain_document.file_format,
            storage_url=domain_document.storage_url,
            storage_encrypted=domain_document.storage_encrypted,
            file_size_bytes=domain_document.file_size_bytes,
            upload_status=domain_document.upload_status,
            parsed_at=domain_document.parsed_at,
            parsing_error=domain_document.parsing_error,
            retention_until=domain_document.retention_until,
            created_by=domain_document.created_by,
            created_at=self._normalize_naive_utc(domain_document.created_at) or now,
            updated_at=self._normalize_naive_utc(domain_document.updated_at) or now,
            document_metadata=domain_document.document_metadata,
            version=domain_document.version,  # TASK-BCK-023
            file_hash=domain_document.file_hash,  # TASK-BCK-023
            # Note: clauses are handled separately if it's an aggregate root
        )
        return orm_document

    def _to_orm_clause(self, domain_clause: Clause) -> ClauseORM:
        orm_clause = ClauseORM(
            id=domain_clause.id,
            project_id=domain_clause.project_id,
            document_id=domain_clause.document_id,
            clause_code=domain_clause.clause_code,
            clause_type=domain_clause.clause_type,
            title=domain_clause.title,
            full_text=domain_clause.full_text,
            text_start_offset=domain_clause.text_start_offset,
            text_end_offset=domain_clause.text_end_offset,
            extracted_entities=domain_clause.extracted_entities,
            extraction_confidence=domain_clause.extraction_confidence,
            extraction_model=domain_clause.extraction_model,
            manually_verified=domain_clause.manually_verified,
            verified_at=domain_clause.verified_at
        )
        return orm_clause

    @staticmethod
    def _build_alert_history_detail(alert: Alert, history_item: dict) -> str:
        details: list[str] = [alert.title]
        for key in ("decision", "resolution", "root_cause", "evidence_type", "rule_code"):
            value = history_item.get(key)
            if value:
                details.append(str(value))
        return " · ".join(details)

    @staticmethod
    def _parse_history_timestamp(value: str | None) -> datetime | None:
        if not value:
            return None
        normalized = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None

    # --- Repository Methods ---
    async def add(self, document: Document) -> None:
        tenant_id = await self._get_current_tenant_id()
        if tenant_id is not None:
            doc_tenant = await self.get_project_tenant_id(document.project_id)
            if doc_tenant is None or doc_tenant != tenant_id:
                raise PermissionError("Cannot add document for project outside tenant")
        orm_document = self._to_orm_document(document)
        self.session.add(orm_document)

    async def get_by_id(self, document_id: UUID) -> Document | None:
        stmt = select(DocumentORM).where(DocumentORM.id == document_id)
        stmt = await self._apply_document_tenant_filter(stmt)
        result = await self.session.execute(stmt)
        orm_document = result.scalar_one_or_none()
        return self._to_domain_document(orm_document)

    async def get_document_with_clauses(self, document_id: UUID) -> Document | None:
        stmt = select(DocumentORM).where(DocumentORM.id == document_id)
        stmt = await self._apply_document_tenant_filter(stmt)
        result = await self.session.execute(stmt)
        orm_document = result.scalar_one_or_none()
        if orm_document is None:
            return None
        domain_document = self._to_domain_document(orm_document)
        domain_document.clauses = await self.list_clauses_for_document(document_id)
        return domain_document

    async def get_history_snapshot(self, document_id: UUID) -> DocumentHistorySnapshot | None:
        document_stmt = (
            select(DocumentORM, func.count(ClauseORM.id))
            .outerjoin(ClauseORM, ClauseORM.document_id == DocumentORM.id)
            .where(DocumentORM.id == document_id)
            .group_by(DocumentORM.id)
        )
        document_stmt = await self._apply_document_tenant_filter(document_stmt)
        document_result = await self.session.execute(document_stmt)
        document_row = document_result.one_or_none()
        if document_row is None:
            return None

        document_orm, clause_count = document_row
        alerts = await self._list_document_evidence_alerts(document_id)
        return DocumentHistorySnapshot(
            document=self._to_domain_document(document_orm),
            clause_count=int(clause_count or 0),
            alerts=alerts,
        )

    async def list_alert_signals_for_document(self, document_id: UUID) -> list[DocumentAlertSignal]:
        alert_stmt = (
            select(Alert)
            .join(ProjectORM, ProjectORM.id == Alert.project_id)
            .join(ClauseORM, ClauseORM.id == Alert.source_clause_id)
            .where(ClauseORM.document_id == document_id)
            .order_by(Alert.created_at.asc())
        )
        tenant_id = await self._get_current_tenant_id()
        if tenant_id is not None:
            alert_stmt = alert_stmt.where(ProjectORM.tenant_id == tenant_id)
        alert_result = await self.session.execute(alert_stmt)

        return [
            DocumentAlertSignal(
                id=alert.id,
                title=alert.title,
                severity=alert.severity,
                status=alert.status.value if hasattr(alert.status, "value") else str(alert.status),
                created_at=alert.created_at,
                updated_at=alert.updated_at,
                source_clause_id=alert.source_clause_id,
            )
            for alert in alert_result.scalars().all()
        ]

    async def _list_document_evidence_alerts(self, document_id: UUID) -> list[DocumentEvidenceAlert]:
        alert_stmt = (
            select(Alert)
            .join(ProjectORM, ProjectORM.id == Alert.project_id)
            .join(ClauseORM, ClauseORM.id == Alert.source_clause_id)
            .where(ClauseORM.document_id == document_id)
            .order_by(Alert.created_at.asc())
        )
        tenant_id = await self._get_current_tenant_id()
        if tenant_id is not None:
            alert_stmt = alert_stmt.where(ProjectORM.tenant_id == tenant_id)
        alert_result = await self.session.execute(alert_stmt)

        evidence_alerts: list[DocumentEvidenceAlert] = []
        for alert in alert_result.scalars().all():
            history_items: list[DocumentAlertHistoryEntry] = []
            for history_item in list((alert.alert_metadata or {}).get("history", [])):
                action = str(history_item.get("action") or "").strip()
                occurred_at = self._parse_history_timestamp(history_item.get("timestamp"))
                if not action or occurred_at is None:
                    continue
                history_items.append(
                    DocumentAlertHistoryEntry(
                        action=action,
                        detail=self._build_alert_history_detail(alert, history_item),
                        occurred_at=occurred_at,
                    )
                )

            evidence_alerts.append(
                DocumentEvidenceAlert(
                    id=alert.id,
                    title=alert.title,
                    created_at=alert.created_at,
                    history=history_items,
                )
            )
        return evidence_alerts

    async def update_status(self, document_id: UUID, status: DocumentStatus, parsing_error: str | None = None) -> None:
        tenant_id = await self._get_current_tenant_id()
        orm_document = await self.session.get(DocumentORM, document_id)
        if orm_document:
            if tenant_id is not None:
                doc_tenant = await self.get_project_tenant_id(orm_document.project_id)
                if doc_tenant is None or doc_tenant != tenant_id:
                    raise PermissionError("Cannot update document for project outside tenant")
            orm_document.upload_status = status
            orm_document.parsing_error = parsing_error
            orm_document.updated_at = self._normalize_naive_utc(datetime.now(UTC))

    async def update_storage_path(self, document_id: UUID, storage_url: str) -> None:
        tenant_id = await self._get_current_tenant_id()
        orm_document = await self.session.get(DocumentORM, document_id)
        if orm_document:
            if tenant_id is not None:
                doc_tenant = await self.get_project_tenant_id(orm_document.project_id)
                if doc_tenant is None or doc_tenant != tenant_id:
                    raise PermissionError("Cannot update document for project outside tenant")
            orm_document.storage_url = storage_url
            orm_document.updated_at = self._normalize_naive_utc(datetime.now(UTC))

    async def update_version(
        self,
        document_id: UUID,
        version: int,
        file_hash: str,
        filename: str,
        status: DocumentStatus,
    ) -> Document:
        """
        Updates document version and related fields for re-upload.
        Part of TASK-BCK-023.
        """
        tenant_id = await self._get_current_tenant_id()
        orm_document = await self.session.get(DocumentORM, document_id)
        if not orm_document:
            raise ValueError(f"Document {document_id} not found")

        if tenant_id is not None:
            doc_tenant = await self.get_project_tenant_id(orm_document.project_id)
            if doc_tenant is None or doc_tenant != tenant_id:
                raise PermissionError("Cannot update document for project outside tenant")

        # Update version and file metadata
        orm_document.version = version
        orm_document.file_hash = file_hash
        orm_document.filename = filename
        orm_document.upload_status = status
        orm_document.updated_at = self._normalize_naive_utc(datetime.now(UTC))

        # Clear parsing metadata since document is being re-processed
        orm_document.parsed_at = None
        orm_document.parsing_error = None

        await self.session.flush()
        await self.session.refresh(orm_document)

        return self._to_domain_document(orm_document)

    async def delete(self, document_id: UUID) -> None:
        tenant_id = await self._get_current_tenant_id()
        orm_document = await self.session.get(DocumentORM, document_id)
        if orm_document:
            if tenant_id is not None:
                doc_tenant = await self.get_project_tenant_id(orm_document.project_id)
                if doc_tenant is None or doc_tenant != tenant_id:
                    raise PermissionError("Cannot delete document for project outside tenant")
            await self.session.delete(orm_document)

    async def list_for_project(
        self, project_id: UUID, skip: int, limit: int
    ) -> tuple[list[Document], int]:
        stmt = select(DocumentORM).where(DocumentORM.project_id == project_id).offset(skip).limit(limit)
        stmt = await self._apply_document_tenant_filter(stmt)
        count_stmt = (
            select(func.count())
            .select_from(DocumentORM)
            .where(DocumentORM.project_id == project_id)
        )
        count_stmt = await self._apply_document_tenant_filter(count_stmt)

        results = await self.session.execute(stmt)
        documents_orm = results.scalars().all()

        total_count_result = await self.session.execute(count_stmt)
        total_count = total_count_result.scalar_one()

        return [self._to_domain_document(doc_orm) for doc_orm in documents_orm], total_count

    async def get_project_tenant_id(self, project_id: UUID) -> UUID | None:
        tenant_id = await self._get_current_tenant_id()
        query = "SELECT tenant_id FROM projects WHERE id = :project_id"
        params: dict[str, str] = {"project_id": str(project_id)}
        if tenant_id is not None:
            query += " AND tenant_id = :tenant_id"
            params["tenant_id"] = str(tenant_id)
        result = await self.session.execute(text(query), params)
        return result.scalar_one_or_none()

    async def add_clause(self, clause: Clause) -> None:
        orm_clause = self._to_orm_clause(clause)
        self.session.add(orm_clause)

    async def clause_exists(self, clause_id: UUID) -> bool:
        stmt = select(ClauseORM.id).where(ClauseORM.id == clause_id)
        stmt = await self._apply_clause_tenant_filter(stmt)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_clause_text_map(self, clause_ids: list[UUID]) -> dict[UUID, str]:
        if not clause_ids:
            return {}
        stmt = select(ClauseORM.id, ClauseORM.full_text).where(ClauseORM.id.in_(clause_ids))
        stmt = await self._apply_clause_tenant_filter(stmt)
        result = await self.session.execute(stmt)
        return {row[0]: row[1] for row in result.all() if row[1]}

    async def get_clauses_by_ids(self, clause_ids: list[UUID]) -> list[Clause]:
        if not clause_ids:
            return []
        stmt = select(ClauseORM).where(ClauseORM.id.in_(clause_ids))
        stmt = await self._apply_clause_tenant_filter(stmt)
        result = await self.session.execute(stmt)
        return [self._to_domain_clause(orm) for orm in result.scalars().all()]

    async def get_clause_by_document_and_code(
        self, document_id: UUID, clause_code: str
    ) -> Clause | None:
        stmt = select(ClauseORM).where(
            ClauseORM.document_id == document_id,
            ClauseORM.clause_code == clause_code,
        )
        stmt = await self._apply_clause_tenant_filter(stmt)
        result = await self.session.execute(stmt)
        orm_clause = result.scalar_one_or_none()
        return self._to_domain_clause(orm_clause) if orm_clause else None

    async def list_clauses_for_document(self, document_id: UUID) -> list[Clause]:
        stmt = select(ClauseORM).where(ClauseORM.document_id == document_id)
        stmt = await self._apply_clause_tenant_filter(stmt)
        result = await self.session.execute(stmt)
        return [self._to_domain_clause(orm) for orm in result.scalars().all()]

    async def commit(self) -> None:
        await self.session.commit()

    async def refresh(self, entity: Document | Clause) -> None:
        if isinstance(entity, Document):
            orm_entity = await self.session.get(DocumentORM, entity.id)
        elif isinstance(entity, Clause):
            orm_entity = await self.session.get(ClauseORM, entity.id)
        else:
            raise TypeError(f"Cannot refresh unknown entity type: {type(entity)}")
        if orm_entity:
            await self.session.refresh(orm_entity)
            # Update the domain entity with refreshed ORM data
            if isinstance(entity, Document):
                entity.filename = orm_entity.filename
                entity.file_format = orm_entity.file_format
                entity.storage_url = orm_entity.storage_url
                entity.storage_encrypted = orm_entity.storage_encrypted
                entity.file_size_bytes = orm_entity.file_size_bytes
                entity.upload_status = orm_entity.upload_status
                entity.parsed_at = orm_entity.parsed_at
                entity.parsing_error = orm_entity.parsing_error
                entity.retention_until = orm_entity.retention_until
                entity.created_by = orm_entity.created_by
                entity.created_at = orm_entity.created_at
                entity.updated_at = orm_entity.updated_at
                entity.document_metadata = orm_entity.document_metadata or {}
            elif isinstance(entity, Clause):
                entity.clause_code = orm_entity.clause_code
                entity.clause_type = orm_entity.clause_type
                entity.title = orm_entity.title
                entity.full_text = orm_entity.full_text
                entity.text_start_offset = orm_entity.text_start_offset
                entity.text_end_offset = orm_entity.text_end_offset
                entity.extracted_entities = orm_entity.extracted_entities or {}
                entity.extraction_confidence = orm_entity.extraction_confidence
                entity.extraction_model = orm_entity.extraction_model
                entity.manually_verified = orm_entity.manually_verified
                entity.verified_at = orm_entity.verified_at
