"""Gated L2 semantic diff for modified clause changes only.

TS-UT-CI-SEM-001
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog

from src.change_intelligence.application.semantic_flag import (
    is_change_semantic_llm_enabled,
)
from src.change_intelligence.domain.contracts import ChangeSet, SemanticChange
from src.change_intelligence.domain.semantic_classification import (
    SemanticClassification,
)
from src.core.ai.anthropic_wrapper import AIRequest, get_anthropic_wrapper
from src.core.ai.model_router import AITaskType

logger = structlog.get_logger(__name__)


def _clause_text(snapshot: dict[str, Any] | None) -> str:
    if snapshot is None:
        return ""
    value = snapshot.get("full_text")
    return value if isinstance(value, str) else ""


def _build_request(
    *,
    change: SemanticChange,
    before_text: str,
    after_text: str,
    tenant_id: UUID,
) -> AIRequest:
    prompt = (
        "Classify the meaning of this modified contract clause pair. "
        "Return JSON only matching the requested schema. Do not classify legal "
        "impact beyond the clause text.\n\n"
        f"Anchor: {change.anchor}\n"
        f"Before:\n{before_text}\n\n"
        f"After:\n{after_text}\n"
    )
    return AIRequest(
        prompt=prompt,
        task_type=AITaskType.CLASSIFICATION,
        tenant_id=tenant_id,
        max_tokens=512,
        temperature=0.0,
        use_cache=True,
        metadata={
            "adr": "ADR-016",
            "layer": "L2",
            "change_type": change.change_type,
            "anchor": change.anchor,
        },
    )


async def _enrich_change(
    *,
    change: SemanticChange,
    tenant_id: UUID,
    llm: Any,
) -> SemanticChange:
    request = _build_request(
        change=change,
        before_text=_clause_text(change.before),
        after_text=_clause_text(change.after),
        tenant_id=tenant_id,
    )
    classification = await llm.generate_structured(request, SemanticClassification)
    return change.model_copy(
        update={
            "semantic_summary": classification.semantic_summary,
            "severity": classification.severity,
            "confidence": classification.confidence,
        }
    )


async def enrich_modified_changes(
    changeset: ChangeSet,
    tenant_id: UUID,
    *,
    llm: Any | None = None,
) -> ChangeSet:
    """Enrich modified changes when the tenant L2 flag is on."""

    if not await is_change_semantic_llm_enabled(tenant_id):
        return changeset

    resolved_llm = llm or get_anthropic_wrapper()
    enriched_changes: list[SemanticChange] = []
    for change in changeset.changes:
        if change.change_type != "modified":
            enriched_changes.append(change)
            continue
        try:
            enriched_changes.append(
                await _enrich_change(
                    change=change,
                    tenant_id=tenant_id,
                    llm=resolved_llm,
                )
            )
        except Exception as exc:  # noqa: BLE001 - per-change L2 failure must be honest-null.
            logger.warning(
                "change_semantic_diff_failed",
                changeset_id=str(changeset.changeset_id),
                anchor=change.anchor,
                error=str(exc),
            )
            enriched_changes.append(change)

    return changeset.model_copy(update={"changes": enriched_changes})


__all__ = ["enrich_modified_changes"]
