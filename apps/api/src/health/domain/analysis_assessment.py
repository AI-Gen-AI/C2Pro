"""Versioned single-document assessment artifact persisted in ``analyses.result_json``.

L4-3 persists the L4-2 output alongside the analysis that produced it. ``result_json`` is
an existing JSONB column, so this is an **additive, versioned** extension — the legacy
``risks``/``wbs`` keys are untouched and no DB migration is required.

Honest-null semantics (the distinction this module exists to protect):

- key **absent** (legacy analysis, or an analysis whose assessment step did not run)
  ⇒ :func:`decode_single_document_assessment` returns ``None`` — *NOT AVAILABLE /
  NOT EVALUATED*;
- key **present** with ``finding_signals == ()`` ⇒ the assessment *ran* and found no
  findings — *EVALUATED, EMPTY*.

These must never collapse into each other: "we did not look" and "we looked and found
nothing" are different product claims (INV-1).

Serialization is canonical JSON mode; decoding is strict (validation errors surface
rather than degrading into a fabricated empty result).

The artifact also records **evidence granularity** (P0b-R1): whether the
``evidence_clause_ids`` it carries are persisted ``documents.clauses`` UUIDs or a single
synthetic document-level identifier. A reader must be able to tell the two apart, because
"six categories evidenced by six distinct clauses" and "six categories evidenced by one
whole-document blob" are different product claims — and never by inspecting the shape of
an id. When granularity is ``DOCUMENT`` for a contract, ``degradation_reason`` records
*why*, so "the clause store was unreachable" is never silently indistinguishable from
"this document was never segmented".
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.coherence.models import FindingSignal
from src.health.domain.single_document_coverage import (
    EvidenceGranularity,
    SingleDocumentCoverage,
)

_FROZEN_CONTRACT = ConfigDict(extra="forbid", frozen=True)

# result_json key owning the artifact. Namespaced so it cannot collide with risks/wbs.
SINGLE_DOCUMENT_ASSESSMENT_KEY = "single_document_assessment"

# Bumped whenever the artifact's shape changes incompatibly. A reader that does not
# recognise the version treats the artifact as unavailable rather than misreading it.
SINGLE_DOCUMENT_ASSESSMENT_VERSION = 1


class SingleDocumentAssessment(BaseModel):
    """The versioned artifact: the findings that were evaluated + the coverage they produced."""

    model_config = _FROZEN_CONTRACT

    version: int = Field(default=SINGLE_DOCUMENT_ASSESSMENT_VERSION, ge=1)
    # Additive and backward compatible, so the version stays 1: every artifact written
    # before R1 was whole-document, which is exactly this default. Bumping the version
    # instead would strand those artifacts as "not evaluated" and lose real data.
    evidence_granularity: EvidenceGranularity = EvidenceGranularity.DOCUMENT
    # Why the evidence is document-level. Set only when a document that *could* have
    # carried clause-granular evidence did not — an unreadable clause store reads very
    # differently from a document type that is never segmented, and both read
    # differently from a contract that simply has no clauses yet.
    degradation_reason: str | None = None
    finding_signals: tuple[FindingSignal, ...] = ()
    coverage: SingleDocumentCoverage

    @model_validator(mode="after")
    def _enforce_reason_scope(self) -> SingleDocumentAssessment:
        if (
            self.evidence_granularity is EvidenceGranularity.CLAUSE
            and self.degradation_reason is not None
        ):
            raise ValueError("clause-granular evidence did not degrade; it carries no reason")
        return self


def encode_single_document_assessment(
    coverage: SingleDocumentCoverage,
    finding_signals: Sequence[FindingSignal],
    granularity: EvidenceGranularity = EvidenceGranularity.DOCUMENT,
    degradation_reason: str | None = None,
) -> dict[str, Any]:
    """Build the additive ``result_json`` fragment for one analysis.

    Returns a single-key mapping the caller merges into ``result_json`` — existing keys
    (``risks``, ``wbs``, …) are preserved by the caller's merge, never replaced here.
    """
    artifact = SingleDocumentAssessment(
        version=SINGLE_DOCUMENT_ASSESSMENT_VERSION,
        evidence_granularity=granularity,
        degradation_reason=degradation_reason,
        finding_signals=tuple(finding_signals),
        coverage=coverage,
    )
    return {SINGLE_DOCUMENT_ASSESSMENT_KEY: artifact.model_dump(mode="json")}


def decode_single_document_assessment(
    result_json: Mapping[str, Any] | None,
) -> SingleDocumentAssessment | None:
    """Strictly reconstruct the artifact, or ``None`` when it is genuinely unavailable.

    ``None`` means *not evaluated* — a legacy analysis, a missing ``result_json``, or an
    artifact written by a future/unknown version. It never means "evaluated and empty";
    that case returns a populated :class:`SingleDocumentAssessment` whose
    ``finding_signals`` is empty.
    """
    if not result_json:
        return None
    payload = result_json.get(SINGLE_DOCUMENT_ASSESSMENT_KEY)
    if not isinstance(payload, Mapping):
        return None
    if payload.get("version") != SINGLE_DOCUMENT_ASSESSMENT_VERSION:
        # Unknown shape — honest unavailable beats a misread assessment.
        return None
    return SingleDocumentAssessment.model_validate(dict(payload))


__all__ = [
    "SINGLE_DOCUMENT_ASSESSMENT_KEY",
    "SINGLE_DOCUMENT_ASSESSMENT_VERSION",
    "EvidenceGranularity",
    "SingleDocumentAssessment",
    "decode_single_document_assessment",
    "encode_single_document_assessment",
]
