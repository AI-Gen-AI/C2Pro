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
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.coherence.models import FindingSignal
from src.health.domain.single_document_coverage import SingleDocumentCoverage

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
    finding_signals: tuple[FindingSignal, ...] = ()
    coverage: SingleDocumentCoverage


def encode_single_document_assessment(
    coverage: SingleDocumentCoverage,
    finding_signals: Sequence[FindingSignal],
) -> dict[str, Any]:
    """Build the additive ``result_json`` fragment for one analysis.

    Returns a single-key mapping the caller merges into ``result_json`` — existing keys
    (``risks``, ``wbs``, …) are preserved by the caller's merge, never replaced here.
    """
    artifact = SingleDocumentAssessment(
        version=SINGLE_DOCUMENT_ASSESSMENT_VERSION,
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
    "SingleDocumentAssessment",
    "decode_single_document_assessment",
    "encode_single_document_assessment",
]
