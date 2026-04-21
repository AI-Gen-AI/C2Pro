"""Register baseline prompts in LangSmith Hub with metadata/tags for prompt governance."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Any

from langchain import hub

from src.analysis.domain.prompts import CRITIQUE_SYSTEM_PROMPT, ROUTER_SYSTEM_PROMPT
from src.modules.extraction.application.ports import (
    DEFAULT_EXTRACTION_PROMPT,
    DEFAULT_EXTRACTION_PROMPT_REPO,
)


@dataclass(frozen=True)
class PromptRegistration:
    repo: str
    prompt: str
    description: str
    metadata: dict[str, Any]
    tags: list[str]


def build_prompt_catalog(owner: str = "c2pro") -> list[PromptRegistration]:
    return [
        PromptRegistration(
            repo=f"{owner}/core-extraction",
            prompt=DEFAULT_EXTRACTION_PROMPT,
            description="Baseline clause extraction prompt used by Domain Service.",
            metadata={"domain": "extraction", "model_target": "claude-sonnet", "source": DEFAULT_EXTRACTION_PROMPT_REPO},
            tags=["v1.0-baseline", "phase-1", "domain:extraction"],
        ),
        PromptRegistration(
            repo=f"{owner}/analysis-router",
            prompt=ROUTER_SYSTEM_PROMPT,
            description="Document router system prompt.",
            metadata={"domain": "analysis", "model_target": "claude-sonnet", "source": "analysis.domain.prompts.ROUTER_SYSTEM_PROMPT"},
            tags=["v1.0-baseline", "phase-1", "domain:analysis"],
        ),
        PromptRegistration(
            repo=f"{owner}/analysis-critique",
            prompt=CRITIQUE_SYSTEM_PROMPT,
            description="Extraction critique prompt.",
            metadata={"domain": "analysis", "model_target": "claude-sonnet", "source": "analysis.domain.prompts.CRITIQUE_SYSTEM_PROMPT"},
            tags=["v1.0-baseline", "phase-1", "domain:analysis"],
        ),
    ]


def migrate(*, owner: str, dry_run: bool) -> dict[str, Any]:
    payload: list[dict[str, Any]] = []
    for record in build_prompt_catalog(owner):
        entry = {
            "repo": record.repo,
            "tags": record.tags,
            "metadata": record.metadata,
        }
        if not dry_run:
            hub.push(record.repo, record.prompt)
        payload.append(entry)
    return {"owner": owner, "dry_run": dry_run, "registered": payload}


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate prompts to LangSmith Hub.")
    parser.add_argument("--owner", default="c2pro")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    summary = migrate(owner=args.owner, dry_run=args.dry_run)
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
