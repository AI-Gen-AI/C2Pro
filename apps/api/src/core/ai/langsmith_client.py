"""TS-AI-LANGSMITH-001: LangSmith client wrapper and tracing helpers."""

from __future__ import annotations

import functools
import os
from dataclasses import dataclass
from typing import Any

import structlog
from langsmith import Client as NativeLangSmithClient
from langsmith.run_helpers import get_current_run_tree
from langsmith.schemas import Run

logger = structlog.get_logger()


@dataclass(frozen=True)
class LangSmithConfig:
    """TS-AI-LANGSMITH-001: Runtime settings for LangSmith integration."""

    api_key: str | None
    endpoint: str
    project_name: str
    tracing_enabled: bool

    @classmethod
    def from_env(cls, *, project_name: str) -> LangSmithConfig:
        tracing_value = os.getenv("LANGSMITH_TRACING", "true").strip().lower()
        tracing_enabled = tracing_value in {"1", "true", "yes", "on"}
        return cls(
            api_key=os.getenv("LANGSMITH_API_KEY"),
            endpoint=os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com"),
            project_name=project_name,
            tracing_enabled=tracing_enabled,
        )


LLM_SPAN_ATTRIBUTE_ALLOWLIST = {
    # Core request identifiers
    "request_id",
    "tenant_id",
    "project_name",
    # Execution context
    "task_type",
    "environment",
    "span_name",
    "function_name",
    "run_id",
    # Model and parameters
    "model_name",
    "model_params",
    # Performance and cost metrics
    "cost_usd",
    "latency_ms",
    "cached",
    # Status and errors
    "status",
    "error",
}


class LangSmithClient:
    """TS-AI-LANGSMITH-001: Lightweight wrapper used by AI pipelines."""

    def __init__(
        self,
        *,
        project_name: str = "c2pro",
        enabled: bool | None = None,
        project: str | None = None,
        environment: str | None = None,
    ) -> None:
        if project is not None:
            project_name = project
        if environment is not None:
            os.environ["ENVIRONMENT"] = environment
        self._enabled_override = enabled
        self.config = LangSmithConfig.from_env(project_name=project_name)
        self._client: NativeLangSmithClient | None = None
        if self.config.api_key and self.config.tracing_enabled:
            self._client = NativeLangSmithClient(
                api_key=self.config.api_key,
                api_url=self.config.endpoint,
            )

    @property
    def is_enabled(self) -> bool:
        """Return True when tracing can be used safely."""
        if self._enabled_override is not None:
            return self._enabled_override
        return bool(self.config.api_key and self.config.tracing_enabled)

    @property
    def enabled(self) -> bool:
        """Backwards-compatible alias for is_enabled (used by prompt_registry)."""
        return self.is_enabled

    def start_span(
        self,
        name: str,
        run_type: str,
        metadata: dict[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> Run | None:
        """TS-AI-LANGSMITH-001: Start a new span with SDK-required inputs."""
        if not self.is_enabled or not self._client:
            return None

        parent_run = get_current_run_tree()
        create_run_kwargs: dict[str, Any] = {
            "name": name,
            "run_type": run_type,
            "inputs": inputs or {},
            "metadata": metadata or {},
            "project_name": self.config.project_name,
            "parent_run": parent_run,
        }
        if tags:
            create_run_kwargs["tags"] = tags
        try:
            run = self._client.create_run(**create_run_kwargs)
            return run
        except Exception as exc:  # noqa: BLE001 - telemetry must never block app flow
            logger.warning(
                "langsmith_start_span_failed",
                span_name=name,
                run_type=run_type,
                error=str(exc),
            )
            return None

    def end_span(
        self,
        span: Run,
        error: Exception | None = None,
        outputs: dict[str, Any] | None = None,
    ) -> None:
        """Ends a span, marking as error if one occurred."""
        if not self.is_enabled or not self._client or not span:
            return

        error_message = str(error) if error else None
        try:
            self._client.end_run(run_id=span.id, error=error_message, outputs=outputs or {})
        except Exception as exc:  # noqa: BLE001 - telemetry must never block app flow
            logger.warning(
                "langsmith_end_span_failed",
                run_id=str(span.id),
                error=str(exc),
            )

    def update_span_metadata(self, span: Run, metadata: dict[str, Any]) -> None:
        """Updates the metadata of an existing span."""
        if not self.is_enabled or not self._client or not span:
            return

        self._client.update_run(run_id=span.id, metadata=metadata)

    def create_event(self, name: str, metadata: dict[str, Any], event_type: str) -> None:
        """Creates a discrete event in the trace."""
        if not self.is_enabled or not self._client:
            return

        current_run = get_current_run_tree()
        if not current_run:
            return

        self._client.create_feedback(
            run_id=current_run.id,
            key=event_type,
            comment=name,
            source_info={"metadata": metadata}
        )

    def build_tags(
        self,
        *,
        task_type: str | None = None,
        tenant_id: str | None = None,
        extra_tags: list[str] | None = None,
    ) -> list[str]:
        """Build stable tags for traces and observability queries."""
        tags: list[str] = []
        if extra_tags:
            tags.extend(extra_tags)
        if task_type:
            tags.append(f"task:{task_type}")
        if tenant_id:
            tags.append("tenant")
            tags.append(f"tenant:{tenant_id}")
        return tags

    def build_metadata(
        self,
        *,
        request_id: str,
        tenant_id: str | None = None,
        task_type: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build consistent metadata for downstream tracing clients."""
        metadata: dict[str, Any] = {
            "request_id": request_id,
            "tenant_id": tenant_id,
            "task_type": task_type,
            "environment": os.getenv("ENVIRONMENT", "development"),
            "project_name": self.config.project_name,
        }
        if extra:
            metadata.update(extra)

        # Filter metadata to only include allow-listed attributes
        return {
            key: value
            for key, value in metadata.items()
            if key in LLM_SPAN_ATTRIBUTE_ALLOWLIST and value is not None
        }

    def create_feedback(
        self, *, run_id: str, key: str, score: float | None = None, comment: str | None = None
    ) -> None:
        """Create feedback for a given run."""
        if not self.enabled or not self._client:
            logger.warning("langsmith_client_disabled_feedback_skipped", run_id=run_id, key=key)
            return

        from uuid import UUID
        self._client.create_feedback(
            run_id=UUID(run_id),
            key=key,
            score=score,
            comment=comment,
        )


@functools.lru_cache(maxsize=1)
def get_client() -> LangSmithClient:
    """Returns a cached instance of the LangSmithClient."""
    return LangSmithClient()
