"""TS-P0D-REPORT-002 - Current State Report source ports.

Sources read authoritative domain data. They raise ``SourceUnavailableError``
when a source legitimately has nothing to offer (for example a disabled
feature); any other exception is treated as a read failure by the use case.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic, Protocol, TypeVar
from uuid import UUID

if TYPE_CHECKING:
    from src.alerts.domain.models import Alert
    from src.coherence.models import DashboardSummary
    from src.documents.domain.models import Document
    from src.modules.hitl.domain.entities import ReviewItem
    from src.procurement.application.budget_use_cases import BudgetResponse
    from src.stakeholders.application.dtos import RaciMatrixViewResponse
    from src.stakeholders.domain.models import Stakeholder
    from src.temporal.domain.project_snapshot import ProjectSnapshot
    from src.wbs.domain.models import WBSNode

T = TypeVar("T")


class SourceUnavailableError(Exception):
    """A source has no data to offer for a legitimate, user-explainable reason."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class SourceOk(Generic[T]):
    value: T


@dataclass(frozen=True)
class SourceUnavailable:
    reason: str


@dataclass(frozen=True)
class SourceFailed:
    reason: str


@dataclass(frozen=True)
class DocumentsInput:
    documents: list[Document]
    total: int


@dataclass(frozen=True)
class HitlInput:
    items: list[ReviewItem]
    pending_count: int


@dataclass(frozen=True)
class CurrentStateInputs:
    documents: SourceOk[DocumentsInput] | SourceUnavailable | SourceFailed
    health: SourceOk[ProjectSnapshot | None] | SourceUnavailable | SourceFailed
    coherence: SourceOk[DashboardSummary | None] | SourceUnavailable | SourceFailed
    alerts: SourceOk[list[Alert]] | SourceUnavailable | SourceFailed
    hitl: SourceOk[HitlInput] | SourceUnavailable | SourceFailed
    budget: SourceOk[BudgetResponse] | SourceUnavailable | SourceFailed
    wbs: SourceOk[list[WBSNode]] | SourceUnavailable | SourceFailed
    stakeholders: SourceOk[list[Stakeholder]] | SourceUnavailable | SourceFailed
    raci: SourceOk[RaciMatrixViewResponse] | SourceUnavailable | SourceFailed


class CurrentStateSources(Protocol):
    async def load_documents(self, project_id: UUID, tenant_id: UUID) -> DocumentsInput: ...

    async def load_health(self, project_id: UUID, tenant_id: UUID) -> ProjectSnapshot | None: ...

    async def load_coherence(self, project_id: UUID, tenant_id: UUID) -> DashboardSummary | None: ...

    async def load_alerts(self, project_id: UUID, tenant_id: UUID) -> list[Alert]: ...

    async def load_hitl(self, project_id: UUID, tenant_id: UUID) -> HitlInput: ...

    async def load_budget(self, project_id: UUID, tenant_id: UUID) -> BudgetResponse: ...

    async def load_wbs(self, project_id: UUID, tenant_id: UUID) -> list[WBSNode]: ...

    async def load_stakeholders(self, project_id: UUID, tenant_id: UUID) -> list[Stakeholder]: ...

    async def load_raci(self, project_id: UUID, tenant_id: UUID) -> RaciMatrixViewResponse: ...


__all__ = [
    "CurrentStateInputs",
    "CurrentStateSources",
    "DocumentsInput",
    "HitlInput",
    "SourceFailed",
    "SourceOk",
    "SourceUnavailable",
    "SourceUnavailableError",
]
