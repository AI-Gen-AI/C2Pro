"""S5 Vn+1: what a DERIVED candidate contains, decided purely from a reconciliation (no I/O, no clock, no randomness).

Contract reused (S5-03, not redesigned): the human decisions taken finding by finding are *provisional intent*. A
DISMISSED finding is EXCLUDED from the effective content and a CORRECTION_PROPOSED one needs a NEW candidate that
carries it; the reconciliation announces both as ``derivations`` and refuses to call the current candidate signable.
This module is the missing producer of that new candidate's CONTENT. It never trusts, approves or promotes anything:
the result is the payload of a PROPOSED candidate Vn+1 that a human must validate and approve again.

What is materialized, and nothing else:

* RETAINED  (CONFIRMED)            -> the risk, byte-for-byte as the source candidate has it;
* EXCLUDED  (DISMISSED)            -> the risk is left out (its history stays in the ledger of the source candidate);
* CORRECTION_PENDING (CORRECTION_PROPOSED) -> the risk with ``CORRECTION_TARGET_FIELD`` replaced by the reviewer's own
  proposed text; every other attribute is the source's. The text is the human's, never generated here.

Anything that is not one of those three (an undecided finding, NEEDS_INFO, an inconsistent ledger) is not derivable:
the caller must have refused before, and this module refuses again (defence in depth).
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.modules.hitl.domain.finding_reconciliation import (
    FindingResolution,
    LedgerEvent,
    ReconciliationResult,
    ReconciliationStatus,
)
from src.modules.hitl.domain.finding_source_membership import risk_source_item_id

DERIVATION_POLICY_VERSION = "s5-derive/v1"

# The ONE field of a risk that a proposed correction replaces. A risk's other attributes (title, category, severity,
# likelihood, confidence, clause reference, source) are the extractor's and are not the reviewer's to rewrite here.
CORRECTION_TARGET_FIELD = "description"

# OWNER RATIFICATION GATE. The reconciliation contract says a correction "needs a NEW candidate" but does not name the
# field the reviewer's replacement text lands in. ``description`` is the only free-text body of a risk and is what the
# review screen's "Proposed replacement text" is shown against, but that is an interpretation. Until the owner ratifies
# it the application layer refuses to materialize corrections (exclusions, which are unambiguous, are not gated).
CORRECTIONS_RATIFIED = False


class NotDerivable(ValueError):
    """The reconciliation or the source payload cannot produce a derived candidate."""


@dataclass(frozen=True)
class ExcludedFinding:
    ordinal: int
    finding_id: str
    source_item_id: str
    decision_event_id: UUID


@dataclass(frozen=True)
class CorrectedFinding:
    ordinal: int
    finding_id: str
    source_item_id: str
    decision_event_id: UUID
    field: str
    original_sha256: str
    proposed_sha256: str


@dataclass(frozen=True)
class DerivedContent:
    risks: tuple[dict[str, Any], ...]  # the effective risks of Vn+1, in the source's order
    retained: tuple[int, ...]  # source ordinals kept untouched
    excluded: tuple[ExcludedFinding, ...]
    corrected: tuple[CorrectedFinding, ...]

    @property
    def changes(self) -> int:
        return len(self.excluded) + len(self.corrected)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def requires_corrections(result: ReconciliationResult) -> bool:
    return any(o.resolution is FindingResolution.CORRECTION_PENDING for o in result.outcomes)


def derive_content(
    source_risks: Sequence[Mapping[str, Any]],
    result: ReconciliationResult,
    ledger: Sequence[LedgerEvent],
) -> DerivedContent:
    """The risks of the derived candidate. Pure and total: the same inputs always give the same content."""
    if result.status is not ReconciliationStatus.CONSISTENT:
        raise NotDerivable("the reconciliation is inconsistent; nothing is derived from it")
    if result.blockers:
        raise NotDerivable("the reconciliation has blockers; every finding must be decided first")
    if not result.derivations:
        raise NotDerivable("the reconciliation needs no derived candidate")

    by_event = {event.event_id: event for event in ledger}
    by_ordinal = {outcome.ordinal: outcome for outcome in result.outcomes}
    if sorted(by_ordinal) != [i for i, risk in enumerate(source_risks) if isinstance(risk, Mapping) and risk]:
        raise NotDerivable("the reconciled findings are not the findings of the source payload")

    risks: list[dict[str, Any]] = []
    retained: list[int] = []
    excluded: list[ExcludedFinding] = []
    corrected: list[CorrectedFinding] = []
    for ordinal, risk in enumerate(source_risks):
        outcome = by_ordinal.get(ordinal)
        if outcome is None:  # an empty slot of the source payload: never a finding, never carried over
            continue
        if outcome.source_item_id != risk_source_item_id(risk):
            raise NotDerivable(f"finding {ordinal} does not match the source payload")
        decisive = outcome.decisive
        if decisive is None:
            raise NotDerivable(f"finding {ordinal} has no decision")
        if outcome.resolution is FindingResolution.RETAINED:
            risks.append(dict(risk))
            retained.append(ordinal)
        elif outcome.resolution is FindingResolution.EXCLUDED:
            excluded.append(ExcludedFinding(ordinal, outcome.finding_id, outcome.source_item_id, decisive.event_id))
        elif outcome.resolution is FindingResolution.CORRECTION_PENDING:
            event = by_event.get(decisive.event_id)
            text = (event.proposed_text if event is not None else None) or ""
            if not text.strip():
                raise NotDerivable(f"finding {ordinal} was marked for correction without a proposed text")
            original = risk.get(CORRECTION_TARGET_FIELD)
            replaced = dict(risk)
            replaced[CORRECTION_TARGET_FIELD] = text.strip()
            risks.append(replaced)
            corrected.append(
                CorrectedFinding(
                    ordinal, outcome.finding_id, outcome.source_item_id, decisive.event_id, CORRECTION_TARGET_FIELD,
                    _sha(original if isinstance(original, str) else ""), _sha(text.strip()),
                )
            )
        else:
            raise NotDerivable(f"finding {ordinal} is {outcome.resolution.value}; it cannot be derived")
    return DerivedContent(tuple(risks), tuple(retained), tuple(excluded), tuple(corrected))


def provenance_entry(
    *,
    result: ReconciliationResult,
    content: DerivedContent,
    source_document_revision_id: UUID,
    derived_artifact_id: UUID,
    derived_artifact_version: int,
    derived_artifact_hash: str,
    derived_by: UUID,
) -> dict[str, Any]:
    """The traceable record kept with the review: WHO derived WHAT from WHICH candidate, on WHICH reconciliation."""
    identity = result.identity
    return {
        "policy": DERIVATION_POLICY_VERSION,
        "source_artifact_id": str(identity.artifact_id),
        "source_artifact_version": identity.artifact_version,
        "source_artifact_hash": identity.artifact_hash,
        "source_document_revision_id": str(source_document_revision_id),
        "source_ledger_revision": result.ledger_revision,
        "reconciliation_policy": result.policy_version,
        "reconciliation_digest": result.digest,
        "derived_artifact_id": str(derived_artifact_id),
        "derived_artifact_version": derived_artifact_version,
        "derived_artifact_hash": derived_artifact_hash,
        "derived_by": str(derived_by),
        "retained": list(content.retained),
        "excluded": [
            {"ordinal": e.ordinal, "finding_id": e.finding_id, "source_item_id": e.source_item_id, "decision_event_id": str(e.decision_event_id)}
            for e in content.excluded
        ],
        "corrected": [
            {
                "ordinal": c.ordinal, "finding_id": c.finding_id, "source_item_id": c.source_item_id,
                "decision_event_id": str(c.decision_event_id), "field": c.field,
                "original_sha256": c.original_sha256, "proposed_sha256": c.proposed_sha256,
            }
            for c in content.corrected
        ],
        # Vn+1 is a PROPOSED candidate: its own findings are undecided, nothing was approved or trusted by deriving it,
        # and the N8 scoring is the source candidate's (carried, not recomputed).
        "derived_state": "PROPOSED",
        "scoring": "INHERITED_FROM_SOURCE",
    }
