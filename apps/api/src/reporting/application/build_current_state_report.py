"""TS-P0D-REPORT-002 - Build the Current State Report from authoritative sources.

Sources are read one at a time and isolated from each other: a failure in one
domain becomes an ERROR section, and the rest of the report is still returned.
Internal exception detail is logged, never placed in the report payload.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, TypeVar
from uuid import UUID

import structlog

from src.reporting.application.current_state_projection import assemble_current_state_report
from src.reporting.application.ports import (
    CurrentStateInputs,
    CurrentStateSources,
    SourceFailed,
    SourceOk,
    SourceUnavailable,
    SourceUnavailableError,
)
from src.reporting.domain.current_state_report import CurrentStateReport, ProjectIdentity

logger = structlog.get_logger(__name__)

SOURCE_READ_FAILED_REASON = "This source could not be read when the report was generated."

T = TypeVar("T")


def _utc_now() -> datetime:
    return datetime.now(UTC)


class BuildCurrentStateReportUseCase:
    def __init__(
        self,
        sources: CurrentStateSources,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._sources = sources
        self._clock = clock

    async def execute(self, project: ProjectIdentity, tenant_id: UUID) -> CurrentStateReport:
        generated_at = self._clock()
        sources = self._sources
        project_id = project.id

        inputs = CurrentStateInputs(
            documents=await self._read("documents", sources.load_documents, project_id, tenant_id),
            health=await self._read("health", sources.load_health, project_id, tenant_id),
            coherence=await self._read("coherence", sources.load_coherence, project_id, tenant_id),
            alerts=await self._read("alerts", sources.load_alerts, project_id, tenant_id),
            hitl=await self._read("hitl", sources.load_hitl, project_id, tenant_id),
            budget=await self._read("budget", sources.load_budget, project_id, tenant_id),
            wbs=await self._read("wbs", sources.load_wbs, project_id, tenant_id),
            stakeholders=await self._read("stakeholders", sources.load_stakeholders, project_id, tenant_id),
            raci=await self._read("raci", sources.load_raci, project_id, tenant_id),
        )
        return assemble_current_state_report(project, inputs, generated_at=generated_at)

    async def _read(
        self,
        source: str,
        loader: Callable[[UUID, UUID], Awaitable[T]],
        project_id: UUID,
        tenant_id: UUID,
    ) -> SourceOk[Any] | SourceUnavailable | SourceFailed:
        try:
            return SourceOk(await loader(project_id, tenant_id))
        except SourceUnavailableError as exc:
            return SourceUnavailable(exc.reason)
        except Exception:  # noqa: BLE001 - one domain's failure must not fail the whole report
            logger.exception(
                "current_state_report_source_failed",
                source=source,
                project_id=str(project_id),
            )
            return SourceFailed(SOURCE_READ_FAILED_REASON)


__all__ = ["SOURCE_READ_FAILED_REASON", "BuildCurrentStateReportUseCase"]
