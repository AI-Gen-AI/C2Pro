"""Canonical reasons for a Coherence Score that is NOT shown (S3).

A null Score always travels with a reason, so that a person who opens the dashboard later -- another session, another
login -- is told WHY there is no number, and the four situations are never confused:

* ``contract_pending_approval`` -- the contract is a PROPOSED candidate awaiting a human decision;
* ``contract_rejected``         -- a human REJECTED the contract source and nothing replaced it;
* ``insufficient_*``            -- an evaluation ran and the evidence cannot support a Score
  (``insufficient_active_weight``: too few categories carry qualifying evidence);
* ``not_evaluated``             -- no evaluation exists at all (not "evaluated and zero").

A Score is never invented or defaulted to 0 for any of them.
"""

from __future__ import annotations

CONTRACT_PENDING_APPROVAL = "contract_pending_approval"
CONTRACT_REJECTED = "contract_rejected"
NOT_EVALUATED = "not_evaluated"
INSUFFICIENT_PREFIX = "insufficient"

WITHHELD_EVALUATION_EVENT = "coherence.evaluation_withheld"

__all__ = [
    "CONTRACT_PENDING_APPROVAL",
    "CONTRACT_REJECTED",
    "INSUFFICIENT_PREFIX",
    "NOT_EVALUATED",
    "WITHHELD_EVALUATION_EVENT",
]
