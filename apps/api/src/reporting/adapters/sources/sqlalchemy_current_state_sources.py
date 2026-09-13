"""TS-P0D-REPORT-004 - SQLAlchemy sources for the Current State Report.

Each loader reads one domain through that domain's existing repository or use
case, inside its own tenant-scoped session. Separate sessions keep one failed
query from aborting the transaction another domain would use.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.alerts.adapters.persistence.alert_repository import SqlAlchemyAlertRepository
from src.alerts.domain.models import Alert
from src.config import get_settings
from src.core.auth.models import User
from src.core.database import get_session_with_tenant
from src.core.tenants.types import require_tenant_id
from src.documents.adapters.persistence.sqlalchemy_document_repository import (
    SqlAlchemyDocumentRepository,
)
from src.modules.hitl.adapters.persistence.repository import SqlAlchemyReviewQueueRepository
from src.modules.hitl.domain.entities import ReviewStatus
from src.procurement.adapters.persistence.budget_repository import SQLAlchemyBudgetRepository
from src.procurement.adapters.persistence.wbs_repository import SQLAlchemyWBSRepository
from src.procurement.application.budget_use_cases import BudgetResponse, GetBudgetUseCase
from src.procurement.domain.models import WBSItem
from src.projects.adapters.persistence.project_repository import SQLAlchemyProjectRepository
from src.reporting.application.ports import (
    DocumentsInput,
    HitlInput,
    SourceUnavailableError,
    StakeholdersInput,
)
from src.stakeholders.adapters.persistence.sqlalchemy_stakeholder_repository import (
    SqlAlchemyStakeholderRepository,
)
from src.stakeholders.application.dtos import RaciMatrixViewResponse
from src.stakeholders.application.get_raci_matrix_use_case import GetRaciMatrixUseCase
from src.stakeholders.application.list_project_stakeholders_use_case import (
    ListProjectStakeholdersUseCase,
)
from src.temporal.adapters.persistence.project_snapshot_repository import (
    SqlAlchemyProjectSnapshotRepository,
)
from src.temporal.domain.project_snapshot import ProjectSnapshot

# The document and stakeholder repositories page with OFFSET/LIMIT and no ORDER BY,
# so a multi-page read could repeat or skip rows. Each is read once, bounded, and
# the projection marks counts partial when the true total is larger.
MAX_DOCUMENTS = 1000
MAX_STAKEHOLDERS = 500
MAX_REVIEW_ITEMS_PER_STATUS = 200

# Items still waiting on a human decision. Escalated items are included: they have
# been routed to another reviewer but are not yet decided.
AWAITING_DECISION_STATUSES: tuple[ReviewStatus, ...] = (
    ReviewStatus.PENDING_REVIEW_REQUIRED,
    ReviewStatus.PENDING_REVIEW_CONDITIONAL,
    ReviewStatus.ESCALATED,
)

COHERENCE_DISABLED_REASON = "Coherence analysis is not enabled in this environment."

SessionScope = Callable[[UUID], AbstractAsyncContextManager[AsyncSession]]


async def _read_coherence_dashboard(project_id: UUID, current_user: User, session: AsyncSession) -> Any:
    """Reuse the Coherence dashboard read so the report shows exactly what the Coherence tab shows.

    Imported lazily: the coherence router pulls in the evaluation graph, and it is
    only mounted when coherence analysis is enabled.
    """
    from src.coherence.router import get_coherence_dashboard, get_flags_service

    return await get_coherence_dashboard(
        project_id=project_id,
        current_user=current_user,
        db=session,
        flags_service=get_flags_service(db=session),
    )


class SqlAlchemyCurrentStateSources:
    def __init__(
        self,
        *,
        current_user: User,
        session_scope: SessionScope = get_session_with_tenant,
        settings_provider: Callable[[], Any] = get_settings,
    ) -> None:
        self._current_user = current_user
        self._session_scope = session_scope
        self._settings_provider = settings_provider

    async def load_documents(self, project_id: UUID, tenant_id: UUID) -> DocumentsInput:
        scoped = require_tenant_id(tenant_id)
        async with self._session_scope(tenant_id) as session:
            documents, total = await SqlAlchemyDocumentRepository(session).list_for_project(
                scoped, project_id, 0, MAX_DOCUMENTS
            )
            return DocumentsInput(documents=list(documents), total=total)

    async def load_health(self, project_id: UUID, tenant_id: UUID) -> ProjectSnapshot | None:
        scoped = require_tenant_id(tenant_id)
        async with self._session_scope(tenant_id) as session:
            return await SqlAlchemyProjectSnapshotRepository(session).latest(project_id, scoped)

    async def load_coherence(self, project_id: UUID, tenant_id: UUID) -> Any:
        if not getattr(self._settings_provider(), "feature_coherence_analysis", False):
            raise SourceUnavailableError(COHERENCE_DISABLED_REASON)
        async with self._session_scope(tenant_id) as session:
            return await _read_coherence_dashboard(project_id, self._current_user, session)

    async def load_alerts(self, project_id: UUID, tenant_id: UUID) -> list[Alert]:
        scoped = require_tenant_id(tenant_id)
        async with self._session_scope(tenant_id) as session:
            return await SqlAlchemyAlertRepository(session, scoped).list_for_project(project_id, scoped)

    async def load_hitl(self, project_id: UUID, tenant_id: UUID) -> HitlInput:
        scoped = require_tenant_id(tenant_id)
        async with self._session_scope(tenant_id) as session:
            repository = SqlAlchemyReviewQueueRepository(session=session, tenant_id=scoped)
            pending = 0
            items: list[Any] = []
            for status in AWAITING_DECISION_STATUSES:
                pending += await repository.count_by_status(status, project_id=project_id)
                items.extend(
                    await repository.list_by_status(
                        status,
                        skip=0,
                        limit=MAX_REVIEW_ITEMS_PER_STATUS,
                        project_id=project_id,
                    )
                )
            return HitlInput(items=items, pending_count=pending)

    async def load_budget(self, project_id: UUID, tenant_id: UUID) -> BudgetResponse:
        scoped = require_tenant_id(tenant_id)
        async with self._session_scope(tenant_id) as session:
            return await GetBudgetUseCase(SQLAlchemyBudgetRepository(session)).execute(project_id, scoped)

    async def load_wbs(self, project_id: UUID, tenant_id: UUID) -> list[WBSItem]:
        # GET /projects/{id}/wbs is served at runtime by the projects router (registered before the
        # in-memory wbs router it shadows), which reads procurement WBS items; RACI rows use the same store.
        scoped = require_tenant_id(tenant_id)
        async with self._session_scope(tenant_id) as session:
            return await SQLAlchemyWBSRepository(session).get_by_project(project_id, scoped)

    async def load_stakeholders(self, project_id: UUID, tenant_id: UUID) -> StakeholdersInput:
        scoped = require_tenant_id(tenant_id)
        async with self._session_scope(tenant_id) as session:
            stakeholders, total = await ListProjectStakeholdersUseCase(
                SqlAlchemyStakeholderRepository(session)
            ).execute(project_id, scoped, limit=MAX_STAKEHOLDERS)
            return StakeholdersInput(stakeholders=list(stakeholders), total=total)

    async def load_raci(self, project_id: UUID, tenant_id: UUID) -> RaciMatrixViewResponse:
        scoped = require_tenant_id(tenant_id)
        async with self._session_scope(tenant_id) as session:
            use_case = GetRaciMatrixUseCase(
                stakeholder_repository=SqlAlchemyStakeholderRepository(session),
                wbs_repository=SQLAlchemyWBSRepository(session),
                project_repository=SQLAlchemyProjectRepository(session),
            )
            return await use_case.execute(project_id, scoped)


__all__ = [
    "AWAITING_DECISION_STATUSES",
    "COHERENCE_DISABLED_REASON",
    "MAX_DOCUMENTS",
    "MAX_STAKEHOLDERS",
    "SqlAlchemyCurrentStateSources",
]
