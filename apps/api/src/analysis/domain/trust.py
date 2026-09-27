"""Trusted-state contract for persisted analysis output (#714 / #706).

"Persisted != trusted". An AI analysis may be persisted for audit,
recovery and HITL resume while it is still only a PROPOSED candidate; only
the exact reviewed candidate (id + version + digest) may become TRUSTED, and
only TRUSTED artifacts feed the canonical ProjectGraph, Health and the
trusted Coherence Score.

State machine (one ``document_artifacts`` row per version)::

    PROPOSED --approve(exact binding)--> TRUSTED
    PROPOSED --reject------------------> REJECTED     (immutable audit evidence)
    PROPOSED --correct / re-analysis---> SUPERSEDED   (by version n+1)

TRUSTED rows are never demoted; a newer trusted version only moves the
older one's ``lifecycle_status`` to ``superseded`` (history).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID


class TrustState(StrEnum):
    PROPOSED = "proposed"
    TRUSTED = "trusted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


TRUST_STATES: tuple[str, ...] = tuple(state.value for state in TrustState)

# review_items.review_metadata key holding the exact candidate a review gates.
REVIEW_BINDING_KEY = "candidate_binding"
# Set on every #714 graph-gated review at creation. A marked review without a
# binding is NOT legacy: its candidate is not persisted/bound yet, so no
# decision may be taken on it. Pre-#714 reviews lack the marker.
TRUST_CANDIDATE_REQUIRED_KEY = "trust_candidate_required"


def review_decision_ready(review_metadata: Mapping[str, Any] | None) -> bool:
    """False while a #714 review still waits for its exact candidate binding."""
    metadata = review_metadata or {}
    if not metadata.get(TRUST_CANDIDATE_REQUIRED_KEY):
        return True
    return isinstance(metadata.get(REVIEW_BINDING_KEY), Mapping)


def artifact_digest(payload: Mapping[str, Any]) -> str:
    """SHA-256 of the canonical JSON payload -- the reviewed content's identity."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CandidateBinding:
    """The exact candidate a human decision applies to."""

    artifact_id: UUID
    document_id: UUID
    artifact_version: int
    artifact_hash: str

    def as_json(self) -> dict[str, Any]:
        return {
            "artifact_id": str(self.artifact_id),
            "document_id": str(self.document_id),
            "artifact_version": self.artifact_version,
            "artifact_hash": self.artifact_hash,
        }

    @classmethod
    def from_json(
        cls, raw: Any, *, default_document_id: UUID | None = None
    ) -> CandidateBinding | None:
        """Parse a stored binding; ``document_id`` may be implied by the review."""
        if not isinstance(raw, Mapping):
            return None
        try:
            raw_document = raw.get("document_id") or default_document_id
            return cls(
                artifact_id=UUID(str(raw["artifact_id"])),
                document_id=UUID(str(raw_document)),
                artifact_version=int(raw["artifact_version"]),
                artifact_hash=str(raw["artifact_hash"]),
            )
        except (KeyError, TypeError, ValueError):
            return None


@dataclass(frozen=True)
class CandidateScoring:
    """The canonical engine's (N8) output for one analysis run.

    Stored on the artifact envelope so a pending candidate can be projected
    with the SAME engine output and score_version -- never recomputed ad hoc.
    """

    coherence_score: float | None
    score_version: str | None

    def as_json(self) -> dict[str, Any]:
        return {"coherence_score": self.coherence_score, "score_version": self.score_version}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> CandidateScoring:
        raw = state.get("coherence_score")
        return cls(
            coherence_score=float(raw) if isinstance(raw, int | float) else None,
            score_version=(
                str(state["coherence_score_version"])
                if state.get("coherence_score_version")
                else None
            ),
        )

    @classmethod
    def from_json(cls, raw: Any) -> CandidateScoring | None:
        if not isinstance(raw, Mapping):
            return None
        score = raw.get("coherence_score")
        version = raw.get("score_version")
        return cls(
            coherence_score=float(score) if isinstance(score, int | float) else None,
            score_version=str(version) if version else None,
        )


class TrustedCommitOutcome(StrEnum):
    COMMITTED = "committed"
    ALREADY_TRUSTED = "already_trusted"


@dataclass(frozen=True)
class TrustedCommit:
    """Result of promoting an exact candidate to TRUSTED."""

    outcome: TrustedCommitOutcome
    binding: CandidateBinding
    project_id: UUID
    tenant_id: UUID


class StaleCandidateError(RuntimeError):
    """The bound candidate is not the current PROPOSED version: fail closed."""


class CandidateNotReadyError(ValueError):
    """A #714 review whose exact candidate is not persisted/bound yet.

    A ValueError on purpose: it is a request that cannot be honoured *yet*
    (HTTP 400), refused before any resume operation, graph run or
    finalization is started -- never a recorded failure.
    """


__all__ = [
    "REVIEW_BINDING_KEY",
    "TRUST_CANDIDATE_REQUIRED_KEY",
    "CandidateNotReadyError",
    "review_decision_ready",
    "TRUST_STATES",
    "CandidateBinding",
    "CandidateScoring",
    "StaleCandidateError",
    "TrustState",
    "TrustedCommit",
    "TrustedCommitOutcome",
    "artifact_digest",
]
