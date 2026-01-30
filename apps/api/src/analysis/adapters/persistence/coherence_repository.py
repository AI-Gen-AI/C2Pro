from __future__ import annotations

from datetime import datetime
from typing import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.analysis.adapters.persistence.models import Alert, Analysis
from src.analysis.domain.enums import AnalysisStatus, AnalysisType, AlertSeverity
from src.analysis.ports.coherence_repository import ICoherenceRepository
from src.core.database import get_session_with_tenant
from src.documents.adapters.persistence.models import DocumentORM
from src.procurement.adapters.persistence.models import BOMItemORM, WBSItemORM
from src.projects.adapters.persistence.models import ProjectORM


class SqlAlchemyCoherenceRepository(ICoherenceRepository):
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_documents_with_clauses(self, project_id: UUID) -> list[DocumentORM]:
        project = await self._load_project(project_id)
        if not project:
            return []
        async with get_session_with_tenant(project.tenant_id) as tenant_db:
            result = await tenant_db.execute(
                select(DocumentORM)
                .where(DocumentORM.project_id == project_id)
                .options(selectinload(DocumentORM.clauses))
            )
            return list(result.scalars().all())

    async def persist_wbs_bom_items(
        self,
        project_id: UUID,
        wbs_items: list[dict],
        bom_items: list[dict],
    ) -> tuple[list[WBSItemORM], list[BOMItemORM]]:
        project = await self._load_project(project_id)
        if not project:
            return [], []

        created_wbs: list[WBSItemORM] = []
        created_bom: list[BOMItemORM] = []

        async with get_session_with_tenant(project.tenant_id) as tenant_db:
            for item in wbs_items:
                existing_wbs = await tenant_db.scalar(
                    select(WBSItemORM).where(
                        WBSItemORM.project_id == project_id,
                        WBSItemORM.wbs_code == item["wbs_code"],
                    )
                )
                if existing_wbs:
                    continue
                wbs = WBSItemORM(
                    project_id=project_id,
                    wbs_code=item["wbs_code"],
                    name=item["name"],
                    description=item.get("description"),
                    level=item.get("level", 1),
                    item_type=item.get("item_type"),
                    funded_by_clause_id=item.get("funded_by_clause_id"),
                    wbs_metadata={"source_document_id": str(item.get("source_document_id"))},
                )
                tenant_db.add(wbs)
                created_wbs.append(wbs)

            for item in bom_items:
                existing_bom = await tenant_db.scalar(
                    select(BOMItemORM).where(
                        BOMItemORM.project_id == project_id,
                        BOMItemORM.item_name == item["item_name"],
                        BOMItemORM.unit == item.get("unit"),
                    )
                )
                if existing_bom:
                    continue
                bom = BOMItemORM(
                    project_id=project_id,
                    item_name=item["item_name"],
                    quantity=item["quantity"],
                    unit=item.get("unit"),
                    description=item.get("description"),
                    category=item.get("category"),
                    unit_price=item.get("unit_price"),
                    total_price=item.get("total_price"),
                    currency=item.get("currency", "EUR"),
                    contract_clause_id=item.get("contract_clause_id"),
                    bom_metadata={"source_document_id": str(item.get("source_document_id"))},
                )
                tenant_db.add(bom)
                created_bom.append(bom)

            await tenant_db.commit()

            for item in created_wbs:
                await tenant_db.refresh(item)
            for item in created_bom:
                await tenant_db.refresh(item)

        return created_wbs, created_bom

    async def save_analysis_and_alerts(
        self,
        project_id: UUID,
        started_at: datetime,
        coherence_score: float,
        alerts: Iterable[dict],
    ) -> None:
        project = await self._load_project(project_id)
        if not project:
            return

        alert_payloads = list(alerts)
        async with get_session_with_tenant(project.tenant_id) as tenant_db:
            new_analysis = Analysis(
                project_id=project_id,
                analysis_type=AnalysisType.COHERENCE,
                status=AnalysisStatus.COMPLETED,
                coherence_score=int(coherence_score),
                alerts_count=len(alert_payloads),
                started_at=started_at,
                completed_at=datetime.utcnow(),
                result_json={
                    "message": f"Coherence analysis completed with score {coherence_score}",
                },
            )
            tenant_db.add(new_analysis)
            await tenant_db.flush()

            if alert_payloads:
                for alert_data in alert_payloads:
                    affected_entities = alert_data.get("affected_entities", [])
                    affected_document_ids = [
                        UUID(e["id"]) for e in affected_entities if e["type"] == "document"
                    ]
                    affected_wbs_ids = [
                        UUID(e["id"]) for e in affected_entities if e["type"] == "wbs"
                    ]
                    affected_bom_ids = [
                        UUID(e["id"]) for e in affected_entities if e["type"] == "bom"
                    ]
                    source_clause_id = next(
                        (
                            UUID(e["id"])
                            for e in affected_entities
                            if e["type"] == "clause"
                        ),
                        None,
                    )

                    new_alert = Alert(
                        project_id=project_id,
                        analysis_id=new_analysis.id,
                        severity=AlertSeverity[alert_data.get("severity", "LOW").upper()],
                        rule_id=alert_data.get("rule_id"),
                        title=f"Inconsistency Detected: {alert_data.get('rule_id')}",
                        description=alert_data.get("message", "No message provided."),
                        recommendation=alert_data.get("suggested_action"),
                        source_clause_id=source_clause_id,
                        affected_entities={
                            "documents": affected_document_ids,
                            "wbs": affected_wbs_ids,
                            "bom": affected_bom_ids,
                        },
                        alert_metadata={"raw": alert_data},
                    )
                    tenant_db.add(new_alert)

            if hasattr(project, "coherence_score"):
                project.coherence_score = int(coherence_score)
            if hasattr(project, "last_analysis_at"):
                project.last_analysis_at = new_analysis.completed_at
            tenant_db.add(project)

            await tenant_db.commit()

    async def _load_project(self, project_id: UUID) -> ProjectORM | None:
        result = await self._db.execute(select(ProjectORM).where(ProjectORM.id == project_id))
        return result.scalar_one_or_none()
