from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.models import Analysis
from src.core.observability.schemas import (
    AnalysisStatus,
    RecentAnalysesResponse,
    SystemStatusResponse,
)


class ObservabilityService:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_system_status(self) -> SystemStatusResponse:
        """
        Retrieves the current system status, including API and database connectivity.
        """
        api_status = "OK"
        database_status = "OK"

        try:
            # Attempt a simple database query to check connectivity
            await self.db_session.execute(select(func.now()))
        except Exception as e:
            database_status = f"ERROR: {e}"
            api_status = "DEGRADED"  # If DB is down, API is degraded

        return SystemStatusResponse(
            api_status=api_status, database_status=database_status, timestamp=datetime.utcnow()
        )

    async def get_recent_analyses(self, limit: int = 10, offset: int = 0) -> RecentAnalysesResponse:
        """
        Retrieves a list of recent coherence analyses.
        """
        query = select(Analysis).order_by(Analysis.created_at.desc()).offset(offset).limit(limit)
        result = await self.db_session.execute(query)
        analyses = result.scalars().all()

        total_analyses_count = await self.db_session.scalar(select(func.count(Analysis.id)))

        analysis_statuses = [
            AnalysisStatus(
                id=analysis.id,
                project_id=analysis.project_id,
                status=analysis.status.value,  # Convert Enum to string
                coherence_score=analysis.coherence_score,
                alerts_count=analysis.alerts_count,
                started_at=analysis.started_at
                if analysis.started_at
                else analysis.created_at,  # Use created_at if started_at is null
                completed_at=analysis.completed_at,
            )
            for analysis in analyses
        ]

        return RecentAnalysesResponse(
            analyses=analysis_statuses,
            total_analyses=total_analyses_count if total_analyses_count is not None else 0,
        )
