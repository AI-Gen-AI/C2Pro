"""TS-AI-LANGSMITH-003: Prompt registry helpers for LangSmith Prompt Hub sync."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from src.core.ai.langsmith_client import LangSmithClient


class PromptHubClient(Protocol):
    """Minimal Prompt Hub contract used by deployment sync tooling."""

    def push_prompt(
        self,
        *,
        template_name: str,
        version: str,
        jinja_content: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...

    def pull_prompt(self, *, template_name: str, version: str) -> dict[str, Any] | None: ...

    def list_prompt_versions(self, *, template_name: str) -> list[str]: ...


@dataclass(frozen=True)
class PromptTemplateRecord:
    """Prompt template payload that can be pushed to Prompt Hub."""

    template_name: str
    version: str
    jinja_content: str
    source_path: str | None = None
    metadata: dict[str, Any] | None = None


class InMemoryPromptHubClient:
    """Simple in-memory Prompt Hub adapter for local tests and dry runs."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, dict[str, Any]]] = {}

    def push_prompt(
        self,
        *,
        template_name: str,
        version: str,
        jinja_content: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        template_store = self._store.setdefault(template_name, {})
        record = {
            "template_name": template_name,
            "version": version,
            "jinja_content": jinja_content,
            "metadata": metadata or {},
        }
        template_store[version] = record
        return record

    def pull_prompt(self, *, template_name: str, version: str) -> dict[str, Any] | None:
        return self._store.get(template_name, {}).get(version)

    def list_prompt_versions(self, *, template_name: str) -> list[str]:
        versions = self._store.get(template_name, {})
        return sorted(versions.keys())


class PromptRegistry:
    """Registry service for discovering and syncing Jinja prompt templates."""

    def __init__(
        self,
        *,
        langsmith_client: LangSmithClient | None = None,
        hub_client: PromptHubClient | None = None,
        templates_root: Path | None = None,
    ) -> None:
        self.langsmith_client = langsmith_client or LangSmithClient()
        self.hub_client = hub_client
        self.templates_root = templates_root

    @property
    def can_sync(self) -> bool:
        """Return whether Prompt Hub sync calls are available."""
        return self.langsmith_client.enabled and self.hub_client is not None

    def build_template_metadata(
        self,
        *,
        owner: str,
        description: str,
        tags: list[str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build canonical metadata payload for Prompt Hub template records."""
        metadata = {
            "owner": owner,
            "description": description,
            "tags": tags or [],
            "project_name": self.langsmith_client.config.project_name,
        }
        if extra:
            metadata.update(extra)
        return metadata

    def sync_template_to_hub(
        self,
        *,
        template_name: str,
        version: str,
        jinja_content: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Push one template revision to Prompt Hub."""
        if not self.can_sync:
            raise RuntimeError("Prompt Hub sync unavailable: missing LangSmith enablement or hub client")
        if self.hub_client is None:  # pragma: no cover
            raise RuntimeError("Prompt Hub client is required")

        return self.hub_client.push_prompt(
            template_name=template_name,
            version=version,
            jinja_content=jinja_content,
            metadata=metadata,
        )

    def pull_template_from_hub(self, *, template_name: str, version: str) -> dict[str, Any] | None:
        """Fetch one template revision from Prompt Hub."""
        if not self.can_sync:
            raise RuntimeError("Prompt Hub sync unavailable: missing LangSmith enablement or hub client")
        if self.hub_client is None:  # pragma: no cover
            raise RuntimeError("Prompt Hub client is required")

        return self.hub_client.pull_prompt(template_name=template_name, version=version)

    def list_template_versions(self, *, template_name: str) -> list[str]:
        """List known versions for a template in Prompt Hub."""
        if not self.can_sync:
            raise RuntimeError("Prompt Hub sync unavailable: missing LangSmith enablement or hub client")
        if self.hub_client is None:  # pragma: no cover
            raise RuntimeError("Prompt Hub client is required")

        return self.hub_client.list_prompt_versions(template_name=template_name)

    def discover_templates(self, *, templates_root: Path | None = None) -> list[PromptTemplateRecord]:
        """Discover .jinja/.jinja2 templates and infer template name + version from filename."""
        root = templates_root or self.templates_root
        if root is None:
            return []

        records: list[PromptTemplateRecord] = []
        for path in sorted(root.rglob("*.jinja*")):
            stem_parts = path.stem.split("_v")
            template_name = stem_parts[0]
            version = stem_parts[1] if len(stem_parts) == 2 else "1.0"
            records.append(
                PromptTemplateRecord(
                    template_name=template_name,
                    version=version,
                    jinja_content=path.read_text(encoding="utf-8"),
                    source_path=str(path),
                )
            )
        return records


__all__ = [
    "InMemoryPromptHubClient",
    "PromptHubClient",
    "PromptRegistry",
    "PromptTemplateRecord",
]
