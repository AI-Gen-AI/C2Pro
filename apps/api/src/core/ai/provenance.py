"""Shared model-provenance contract and helpers (one semantics for every AI producer).

``router_model_provenance`` is the deterministic wrapper-selected model resolution first written
for semantic diff; it lives here so no caller forks it. ``ModelProvenance`` is what an AI run
records: provider, requested and served model, routing tier, integer sampling config, prompt
template identities, profile pins, contract versions and token / cost telemetry references.
"""

from __future__ import annotations

import hashlib
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.core.ai.model_router import AITaskType

_DIGEST = r"^sha256:[0-9a-f]{64}$"


def template_digest(template_text: str) -> str:
    return "sha256:" + hashlib.sha256(template_text.encode("utf-8")).hexdigest()


def router_model_provenance(llm: Any, task_type: AITaskType = AITaskType.CLASSIFICATION) -> dict[str, str | None]:
    """Resolve the deterministic wrapper-selected model before execution."""
    try:
        model_config = llm.model_router.select_model_with_budget_mode(
            task_type=task_type,
            low_budget_mode=False,
            input_token_estimate=0,
            force_tier=None,
        )
        return {
            "provider": "anthropic",
            "model": model_config.name,
            "version": model_config.name,
        }
    except Exception:  # pragma: no cover - defensive compatibility for alternate wrappers
        return {"provider": type(llm).__name__, "model": None, "version": None}


class PromptTemplateIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task: str = Field(min_length=1)
    version: str = Field(min_length=1)
    digest: str = Field(pattern=_DIGEST)


class ModelProvenance(BaseModel):
    """Immutable provenance of one AI run (integers only: no float configuration)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str = Field(min_length=1)
    requested_model: str = Field(min_length=1)
    served_model_id: str | None = None
    routing_tier: str | None = None
    temperature_milli: int | None = Field(default=None, ge=0, le=2000)
    max_tokens: int | None = Field(default=None, ge=1)
    prompt_templates: tuple[PromptTemplateIdentity, ...] = ()
    profile_pins: tuple[dict[str, str], ...] = ()
    proposal_contract_version: str | None = None
    qualification_vocab_version: str | None = None
    orchestration_version: str | None = None
    usage_log_ids: tuple[UUID, ...] = ()
    calls: int = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cost_micro_usd: int = Field(default=0, ge=0)


__all__ = ["ModelProvenance", "PromptTemplateIdentity", "router_model_provenance", "template_digest"]
