"""TS-AI-LANGSMITH-001: LangSmith client wrapper and tracing helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


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

    @property
    def enabled(self) -> bool:
        """Return True when tracing can be used safely."""
        return bool(self.config.api_key and self.config.tracing_enabled)

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
