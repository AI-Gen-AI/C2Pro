"""Synthetic extraction fixture: EPC contract #001.

Refers to Suite ID: TS-UD-EVI-LEGAL-001.

Simulates an LLM extractor pass over a realistic mid-complexity EPC
turnkey contract.  Used to validate ``LegalExtractionAdapter`` end-to-end
without touching Celery or PDF parsing — Phase 2A.2 of the ADR-011
roadmap.

------------------------------------------------------------------
Scenario
------------------------------------------------------------------

* Project:        250 MW solar PV plant, Andalucía, Spain.
* Contract value: EUR 187,500,000 (turnkey EPC).
* Governing law: Spain (Código Civil + Ley de Contratos del Sector
                 Público where applicable for the public off-taker).
* PDF length:    87 pages.

Sections this fixture pulls claims from:

    §7   Payment Schedule                          (p. 18-21)
    §11  Liquidated Damages for Delay              (p. 34-36)
    §15  Limitation of Liability                   (p. 48-49)
    §16  Force Majeure                             (p. 50-51)   ← out-of-scope
    Schedule 4 — Milestone restatement             (p. 72-74)   ← partial payment terms

------------------------------------------------------------------
Extractor profile
------------------------------------------------------------------

The simulated extractor is "well-calibrated but noisy":

* Emits high-confidence EXACT-locator claims for the three main
  clauses.
* Emits an APPROXIMATE-locator restatement of payment terms from
  Schedule 4 with only the field that the schedule actually states
  (the others remain None — no fabrication).
* Emits two genuine extractor-drift payloads: a TIME-dimension claim
  routed here by mistake, and a LEGAL ``force_majeure`` claim that
  the pilot does not yet model.
* Emits one malformed late-fees payload: the LLM hallucinated an
  ``adjustment_factor`` field that is not in the schema.  Adapter
  must surface this as a ``schema_validation_error`` ProcessingError
  — NOT as a fabricated claim.

This shape (5 valid + 1 partial + 2 out-of-scope + 1 schema error)
mirrors what we expect to see in real shadow runs once the extractor
is wired.  Adjust as the extractor profile becomes better known.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

# Stable UUID for deterministic test assertions and trace correlation.
EPC_001_DOCUMENT_ID = UUID("11111111-2222-3333-4444-555555555555")


def build_epc_001_payloads() -> list[dict[str, Any]]:
    """Return the synthetic extraction payload batch for EPC contract #001."""
    return [
        # ----- §7 Payment Schedule (p.18-21) — main payment terms -----
        {
            "dimension": "LEGAL",
            "claim_type": "payment_terms",
            "value": {
                "currency": "EUR",
                "net_days": 45,
                "advance_payment_pct": 15.0,
                "retention_pct": 5.0,
                "milestone_count": 7,
            },
            "confidence": 0.91,
            "freshness": 1.0,
            "page": 18,
            "char_start": 1240,
            "char_end": 1830,
            "quote": (
                "The Owner shall pay each undisputed invoice within "
                "forty-five (45) days of receipt. An advance payment "
                "equal to fifteen percent (15%) of the Contract Price "
                "shall be released against an irrevocable bank "
                "guarantee. A retention of five percent (5%) of each "
                "invoice shall be withheld until Final Acceptance."
            ),
        },
        # ----- §11 Liquidated Damages (p.34-36) -----
        {
            "dimension": "LEGAL",
            "claim_type": "late_fees_penalties",
            "value": {
                "currency": "EUR",
                "rate_pct_per_day": 0.15,
                "cap_pct_of_contract": 10.0,
                "basis": "contract_value",
            },
            "confidence": 0.86,
            "freshness": 1.0,
            "page": 34,
            "char_start": 410,
            "char_end": 980,
            "quote": (
                "For every Day of delay beyond the Scheduled "
                "Substantial Completion Date the Contractor shall pay "
                "Liquidated Damages equal to zero point fifteen percent "
                "(0.15%) of the Contract Price per Day, up to a maximum "
                "aggregate of ten percent (10%) of the Contract Price."
            ),
        },
        # ----- §15 Limitation of Liability (p.48-49) -----
        {
            "dimension": "LEGAL",
            "claim_type": "liability_cap",
            "value": {
                "currency": "EUR",
                "cap_pct_of_contract": 100.0,
                "excludes_gross_negligence": True,
                "basis": "contract_value",
            },
            "confidence": 0.93,
            "freshness": 1.0,
            "page": 48,
            "char_start": 220,
            "char_end": 820,
            "quote": (
                "The aggregate liability of the Contractor under or in "
                "connection with this Contract shall not exceed one "
                "hundred percent (100%) of the Contract Price, save "
                "that no such cap shall apply in cases of wilful "
                "misconduct or gross negligence."
            ),
        },
        # ----- Schedule 4 restatement (p.72-74) — partial payment terms -----
        # The schedule only restates the milestone count; everything else
        # is silent. Adapter must keep the silent fields as None.
        {
            "dimension": "LEGAL",
            "claim_type": "payment_terms",
            "value": {
                "milestone_count": 7,
            },
            "confidence": 0.62,
            "freshness": 1.0,
            "page": 72,
            "char_start": None,
            "char_end": None,
            "quote": (
                "Schedule 4 — Milestones (M1 through M7) as set forth "
                "in Annex II."
            ),
        },
        # ----- Drift #1: TIME-dimension claim routed here by mistake -----
        {
            "dimension": "TIME",
            "claim_type": "milestone_definition",
            "value": {"milestone": "Mechanical Completion", "deadline_days": 540},
            "confidence": 0.88,
            "freshness": 1.0,
            "page": 21,
            "char_start": 100,
            "char_end": 220,
            "quote": "Mechanical Completion shall occur within 540 Days.",
        },
        # ----- Drift #2: LEGAL claim_type not in pilot scope -----
        {
            "dimension": "LEGAL",
            "claim_type": "force_majeure",
            "value": {"notice_days": 14},
            "confidence": 0.74,
            "freshness": 1.0,
            "page": 50,
            "char_start": 80,
            "char_end": 360,
            "quote": (
                "A Party affected by a Force Majeure event shall notify "
                "the other Party in writing within fourteen (14) Days."
            ),
        },
        # ----- Schema error: hallucinated extra key inside `value` -----
        # The LLM produced a field that is not in LateFeesPenaltiesValue.
        # extra="forbid" on the schema → ValidationError → ProcessingError.
        # MUST NOT be turned into a FABRICATION_SUSPECTED claim.
        {
            "dimension": "LEGAL",
            "claim_type": "late_fees_penalties",
            "value": {
                "currency": "EUR",
                "rate_pct_per_day": 0.10,
                "adjustment_factor": "tiered",  # hallucinated
            },
            "confidence": 0.55,
            "freshness": 1.0,
            "page": 36,
            "char_start": 1100,
            "char_end": 1240,
            "quote": "Tiered adjustment applies after the first month of delay.",
        },
    ]


# Deterministic expectations consumed by the integration tests.  Update
# in lockstep with the payload builder.
EPC_001_EXPECTATIONS = {
    "total_payloads": 7,
    "claim_count": 4,
    "claim_type_distribution": {
        "payment_terms": 2,
        "late_fees_penalties": 1,
        "liability_cap": 1,
    },
    "out_of_scope_count": 2,
    "out_of_scope_reasons": {"wrong_dimension": 1, "unknown_claim_type": 1},
    "processing_error_count": 1,
    "processing_error_reasons": {"schema_validation_error": 1},
    "fabrication_suspected_count": 0,  # invariant — must always be zero
}
