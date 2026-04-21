"""TS-AI-LANGSMITH-013: Persist AI usage logs with trace linkage and tenant ownership checks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select

from src.core.ai.models import AIUsageLogORM
from src.core.database import get_session_with_tenant

logger = structlog.get_logger()


@dataclass(slots=True)
class AIUsageLogRecord:
    tenant_id: UUID
    model: str
    operation: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: float
    project_id: UUID | None = None
    prompt_version: str | None = None
    cached: bool = False
    trace_id: str | None = None
    trace_url: str | None = None
    metadata: dict[str, Any] | None = None


class AIUsageLogger:
    """TS-AI-LANGSMITH-013: Tenant-scoped usage logging for successful AI invocations."""

    async def log_success(self, record: AIUsageLogRecord) -> None:
        total_tokens = record.input_tokens + record.output_tokens
        log_metadata = {"prompt_version": record.prompt_version, "cached": record.cached}
        if record.metadata:
            log_metadata.update(record.metadata)

        try:
            async with get_session_with_tenant(record.tenant_id) as session:
                session.add(
                    AIUsageLogORM(
                        tenant_id=record.tenant_id,
                        project_id=record.project_id,
                        model_name=record.model,
                        operation_type=record.operation,
                        input_tokens=record.input_tokens,
                        output_tokens=record.output_tokens,
                        total_tokens=total_tokens,
                        estimated_cost=record.cost_usd,
                        duration_ms=round(record.latency_ms),
                        status="cached" if record.cached else "success",
                        log_metadata=log_metadata,
                        trace_id=record.trace_id,
                        trace_url=record.trace_url,
                    )
                )
        except Exception:
            logger.exception(
                "ai_usage_log_save_failed",
                tenant_id=str(record.tenant_id),
                model=record.model,
                operation=record.operation,
                trace_id=record.trace_id,
            )

    async def tenant_owns_trace(self, *, tenant_id: UUID, trace_id: str) -> bool:
        async with get_session_with_tenant(tenant_id) as session:
            stmt = select(AIUsageLogORM.id).where(
                AIUsageLogORM.tenant_id == tenant_id,
                AIUsageLogORM.trace_id == trace_id,
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none() is not None

    async def record_feedback(
        self,
        *,
        tenant_id: UUID,
        trace_id: str,
        score: float,
        comment: str | None,
    ) -> bool:
        async with get_session_with_tenant(tenant_id) as session:
            stmt = select(AIUsageLogORM).where(
                AIUsageLogORM.tenant_id == tenant_id,
                AIUsageLogORM.trace_id == trace_id,
            )
            result = await session.execute(stmt)
            record = result.scalars().first()
            if record is None:
                return False

            metadata = dict(record.log_metadata or {})
            metadata["feedback_score"] = score
            if comment:
                metadata["feedback_comment"] = comment
            metadata["feedback_at"] = datetime.now(UTC).isoformat()
            record.log_metadata = metadata
            return True
