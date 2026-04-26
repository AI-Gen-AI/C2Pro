"""TS-AI-LANGSMITH-001: LangSmith client wrapper and tracing helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
import functools
from langsmith import Client as NativeLangSmithClient
from langsmith.run_helpers import get_current_run_tree
from langsmith.schemas import Run


@dataclass(frozen=True)
class LangSmithConfig:
    """TS-AI-LANGSMITH-001: Runtime settings for LangSmith integration."""

    api_key: str | None
    endpoint: str
    project_name: str
    tracing_enabled: bool

    @classmethod
    def from_env(cls, *, project_name: str) -> "LangSmithConfig":
        tracing_value = os.getenv("LANGSMITH_TRACING", "true").strip().lower()
        tracing_enabled = tracing_value in {"1", "true", "yes", "on"}
        return cls(
            api_key=os.getenv("LANGSMITH_API_KEY"),
            endpoint=os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com"),
            project_name=project_name,
            tracing_enabled=tracing_enabled,
        )


class LangSmithClient:
    """TS-AI-LANGSMITH-001: Lightweight wrapper used by AI pipelines."""

    def __init__(self, *, project_name: str = "c2pro") -> None:
        self.config = LangSmithConfig.from_env(project_name=project_name)
        self._client: NativeLangSmithClient | None = None
        if self.is_enabled:
            self._client = NativeLangSmithClient(
                api_key=self.config.api_key,
                api_url=self.config.endpoint,
            )

    @property
    def is_enabled(self) -> bool:
        """Return True when tracing can be used safely."""
        return bool(self.config.api_key and self.config.tracing_enabled)

    @property
    def enabled(self) -> bool:
        """Backwards-compatible alias for is_enabled (used by prompt_registry)."""
        return self.is_enabled

    def start_span(self, name: str, run_type: str, metadata: dict[str, Any] | None = None) -> Run | None:
        """Starts a new span."""
        if not self.is_enabled or not self._client:
            return None
        
        parent_run = get_current_run_tree()
        run = self._client.create_run(
            name=name,
            run_type=run_type,
            metadata=metadata or {},
            project_name=self.config.project_name,
            parent_run=parent_run,
        )
        return run

    def end_span(self, span: Run, error: Exception | None = None) -> None:
        """Ends a span, marking as error if one occurred."""
        if not self.is_enabled or not self._client or not span:
            return
        
        error_message = str(error) if error else None
        self._client.end_run(run_id=span.id, error=error_message)

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
        return metadata

@functools.lru_cache(maxsize=1)
def get_client() -> LangSmithClient:
    """Returns a cached instance of the LangSmithClient."""
    return LangSmithClient()
