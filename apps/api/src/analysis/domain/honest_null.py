"""TS-ADR-013-GRAPH-001 - Honest-null helper for INV-1."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.evidence.domain.runtime_trust import EvidenceRef


class HonestNull(BaseModel):
    """A null critical value with an explicit reason and evidence context."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    value: None = None
    reason: str
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


def honest_null(
    *,
    reason: str,
    evidence_refs: list[EvidenceRef] | None = None,
) -> HonestNull:
    return HonestNull(reason=reason, evidence_refs=evidence_refs or [])


def value_or_honest_null(
    value: Any,
    *,
    reason: str,
    evidence_refs: list[EvidenceRef] | None = None,
) -> Any | HonestNull:
    if value is None:
        return honest_null(reason=reason, evidence_refs=evidence_refs)
    return value


__all__ = ["HonestNull", "honest_null", "value_or_honest_null"]
