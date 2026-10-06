from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.analysis.adapters.persistence.models import Alert, Analysis
from src.analysis.domain.enums import AlertSeverity, AnalysisStatus, AnalysisType
from src.analysis.ports.coherence_repository import ICoherenceRepository
from src.core.database import get_session_with_tenant
from src.core.json_types import JsonDict, JsonValue
from src.documents.adapters.persistence.models import DocumentORM
from src.projects.adapters.persistence.models import ProjectORM
from src.shared_kernel.enums import WBSItemType


def _wbs_item_type(value: object) -> WBSItemType | None:
    try:
        return WBSItemType(str(value).lower()) if value else None
    except ValueError:
        return None


class SqlAlchemyCoherenceRepository(ICoherenceRepository):
    def __init__(self, db: AsyncSession, tenant_id: UUID | None = None) -> None:
        self._db = db
        self._tenant_id = tenant_id

    async def _load_project(
        self, project_id: UUID, required_tenant_id: UUID | None = None
    ) -> ProjectORM | None:
        """Load project with optional tenant verification."""
        result = await self._db.execute(select(ProjectORM).where(ProjectORM.id == project_id))
        project = result.scalar_one_or_none()
        if project is None:
            return None
        if required_tenant_id is not None and project.tenant_id != required_tenant_id:
            raise PermissionError("Cannot access project outside tenant context")
        return project

    async def list_documents_with_clauses(
        self, project_id: UUID, tenant_id: UUID | None = None
    ) -> list[DocumentORM]:
        effective_tenant_id = tenant_id or self._tenant_id
        project = await self._load_project(project_id, effective_tenant_id)
        if not project:
            return []
        async with get_session_with_tenant(project.tenant_id) as tenant_db:
            result = await tenant_db.execute(
                select(DocumentORM)
                .where(DocumentORM.project_id == project_id)
                .options(selectinload(DocumentORM.clauses))
            )
            return list(result.scalars().all())

    async def save_analysis_and_alerts(
        self,
        project_id: UUID,
        started_at: datetime,
        coherence_score: float,
        alerts: Iterable[JsonDict],
        tenant_id: UUID | None = None,
    ) -> None:
        effective_tenant_id = tenant_id or self._tenant_id
        project = await self._load_project(project_id, effective_tenant_id)
        if not project:
            return

        alert_payloads = list(alerts)
        async with get_session_with_tenant(project.tenant_id) as tenant_db:
            new_analysis = Analysis(
                tenant_id=project.tenant_id,
                project_id=project_id,
                analysis_type=AnalysisType.COHERENCE,
                status=AnalysisStatus.COMPLETED,
                coherence_score=int(coherence_score),
                alerts_count=len(alert_payloads),
                started_at=started_at,
                completed_at=datetime.now(UTC),
                result_json={
                    "message": f"Coherence analysis completed with score {coherence_score}",
                },
            )
            tenant_db.add(new_analysis)
            await tenant_db.flush()

            if alert_payloads:
                for alert_data in alert_payloads:
                    affected_entities = cast(
                        list[JsonDict], alert_data.get("affected_entities", [])
                    )
                    affected_document_ids = [
                        UUID(cast(str, e["id"]))
                        for e in affected_entities
                        if e["type"] == "document"
                    ]
                    affected_wbs_ids = [
                        UUID(cast(str, e["id"]))
                        for e in affected_entities
                        if e["type"] == "wbs"
                    ]
                    affected_bom_ids = [
                        UUID(cast(str, e["id"]))
                        for e in affected_entities
                        if e["type"] == "bom"
                    ]
                    source_clause_id = next(
                        (
                            UUID(cast(str, e["id"]))
                            for e in affected_entities
                            if e["type"] == "clause"
                        ),
                        None,
                    )

                    new_alert = Alert(
                        tenant_id=project.tenant_id,
                        project_id=project_id,
                        analysis_id=new_analysis.id,
                        severity=AlertSeverity[
                            cast(str, alert_data.get("severity", "LOW")).upper()
                        ],
                        rule_id=cast(str | None, alert_data.get("rule_id")),
                        title=f"Inconsistency Detected: {alert_data.get('rule_id')}",
                        message=cast(str, alert_data.get("message", "No message provided.")),
                        description=cast(
                            str, alert_data.get("message", "No message provided.")
                        ),
                        recommendation=cast(str | None, alert_data.get("suggested_action")),
                        source_clause_id=source_clause_id,
                        affected_entities={
                            "documents": affected_document_ids,
                            "wbs": affected_wbs_ids,
                            "bom": affected_bom_ids,
                        },
                        alert_metadata={"raw": cast(JsonValue, alert_data)},
                    )
                    tenant_db.add(new_alert)

            if hasattr(project, "coherence_score"):
                project.coherence_score = int(coherence_score)
            if hasattr(project, "last_analysis_at"):
                project.last_analysis_at = new_analysis.completed_at
            tenant_db.add(project)

            await tenant_db.commit()
