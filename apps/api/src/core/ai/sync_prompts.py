"""TS-AI-LANGSMITH-004: CLI entrypoint for Prompt Hub template synchronization."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from src.core.ai.langsmith_client import LangSmithClient
from src.core.ai.prompt_registry import PromptHubClient, PromptRegistry


def run_sync(
    *,
    templates_root: Path,
    project_name: str = "c2pro",
    hub_client: PromptHubClient | None = None,
) -> dict[str, Any]:
    """Discover and sync all managed prompt templates to Prompt Hub."""
    registry = PromptRegistry(
        langsmith_client=LangSmithClient(project_name=project_name),
        hub_client=hub_client,
        templates_root=templates_root,
    )

    records = registry.discover_templates()
    synced_count = 0
    template_names: list[str] = []

    for record in records:
        metadata = registry.build_template_metadata(
            owner="ai-team",
            description=f"Managed prompt template synced from {record.source_path}",
            tags=["managed", "deployment-sync"],
            extra={"source_path": record.source_path},
        )
        registry.sync_template_to_hub(
            template_name=record.template_name,
            version=record.version,
            jinja_content=record.jinja_content,
            metadata=metadata,
        )
        synced_count += 1
        template_names.append(record.template_name)

    return {
        "templates_root": str(templates_root),
        "discovered": len(records),
        "synced": synced_count,
        "template_names": sorted(set(template_names)),
        "project_name": project_name,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m core.ai.sync_prompts",
        description="Sync managed Jinja prompt templates to LangSmith Prompt Hub.",
    )
    parser.add_argument(
        "--templates-root",
        default=os.getenv("PROMPT_TEMPLATES_ROOT", "."),
        help="Root directory containing managed .jinja/.jinja2 templates.",
    )
    parser.add_argument(
        "--project-name",
        default=os.getenv("LANGSMITH_PROJECT", "c2pro"),
        help="LangSmith project name used for metadata.",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = run_sync(
        templates_root=Path(args.templates_root),
        project_name=args.project_name,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
