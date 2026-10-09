"""PQ-HITL-04C: deterministic *membership* of a risk in a bound candidate.

This pure verifier is not evidence of contractual truth: it proves only that
a risk datum exactly matches one position in the persisted candidate payload.
The caller MUST fetch the immutable PROPOSED artifact by its tenant, revision,
artifact id/version/digest and independently verify those DB identity guards.
Critique observations have no typed persisted source envelope yet and are
intentionally not authorized by this verifier.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


class FindingSourceNotBound(ValueError):
    """No such risk exists at that exact ordinal in the scoped candidate."""


@dataclass(frozen=True)
class VerifiedRiskMembership:
    source_kind: str
    source_item_id: str
    source_digest: str
    ordinal: int


def risk_source_item_id(risk: Mapping[str, Any]) -> str:
    """Canonical payload identity; different evidence/content implies a new ID."""
    if not isinstance(risk, Mapping) or not risk:
        raise FindingSourceNotBound("missing structured risk item")
    canonical = json.dumps(
        dict(risk), sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return "risk-sha256:" + digest


def verify_risk_source_membership(
    candidate_payload: Mapping[str, Any],
    *,
    source_item_id: str,
    ordinal: int,
) -> VerifiedRiskMembership:
    """Fail closed if the requested item does not match exactly this candidate."""
    if not isinstance(candidate_payload, Mapping):
        raise FindingSourceNotBound("candidate payload is unavailable")
    risks = candidate_payload.get("extracted_risks")
    if not isinstance(risks, list) or ordinal < 0 or ordinal >= len(risks):
        raise FindingSourceNotBound("risk index not present in candidate")
    risk = risks[ordinal]
    if not isinstance(risk, Mapping):
        raise FindingSourceNotBound("risk at index is not a structured source item")
    try:
        expected = risk_source_item_id(risk)
    except (TypeError, ValueError, OverflowError) as exc:
        raise FindingSourceNotBound("risk source item cannot be canonically hashed") from exc
    if source_item_id != expected:
        raise FindingSourceNotBound("risk source fingerprint differs from candidate item")
    return VerifiedRiskMembership(
        source_kind="RISK",
        source_item_id=expected,
        source_digest=expected.removeprefix("risk-sha256:"),
        ordinal=ordinal,
    )
