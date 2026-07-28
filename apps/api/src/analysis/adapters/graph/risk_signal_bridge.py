"""Bridge: LLM-extracted risks → coherence ``FindingSignal``s (v1 patch).

Refers to Suite ID: TS-UA-ANA-GRAPH-001.

The v1 coherence engine consumes ``FindingSignal`` objects produced by
deterministic evaluators (pattern-matching on clause text) and by the
LLM semantic layer (which is OFF when ``low_budget_mode=True``).
Until the evidence module (ADR-011 Phase 2A) is wired through the
pipeline, the categorical risks already extracted by the LLM (N4) are
not surfaced to the coherence dashboard — categories like LEGAL
appear as ``unassessed`` even when N4 found several risks in them.

This bridge closes the gap **for v1 only**: it converts the N4 risk
dicts into ``FindingSignal``s tagged ``source="llm"`` with a synthetic
``EXTRACTOR-RISK`` rule_id so they can be distinguished from real rule
hits in diagnostics.  It also returns a coverage seed so the dashboard
state moves from ``unassessed`` → ``assessed_findings`` for any
category that has at least one extracted risk.

Design notes:

* Risks with missing/unknown ``category`` are dropped (with a log
  warning + a counter in the returned summary) rather than fabricated
  into SCOPE.  Coherence is what we sell — we do not invent it.
* ``risk_score`` (0-10 scale from N4) maps to ``impact_score`` ∈ [0,1].
  When ``risk_score`` is absent, we fall back to mapping the
  categorical ``impact`` field (CRITICAL=0.9, HIGH=0.7, MEDIUM=0.5,
  LOW=0.3) — never a default of 0 (would silently zero out the
  category) or 1 (would dominate the bucket).
* ``confidence`` is fixed at 0.7 to reflect that this is an LLM
  extraction, not a deterministic rule hit.  Downstream scoring
  weighs LLM evidence less than deterministic, which is correct.
* This is an **interim bridge**.  It will be removed when 2A.5 wires
  the evidence module to the coherence engine through ``EvidenceClaim``
  + CVC.

IR-3 (TASK-V3-013-12) — producer/consumer key drift:
    ``_risk_contract_item`` (``analysis/adapters/graph/nodes.py``) validates
    N4's raw extractor dict against the FROZEN ``RiskItem`` contract
    (``analysis/domain/contracts.py``) and ``.model_dump()``s the result before
    it reaches ``state["extracted_risks"]``. Both real callers of this bridge
    (``nodes_extended.py`` N8 and ``project_graph.py`` cross-artifact
    aggregation) therefore hand it ``RiskItem``-shaped dicts, not N4's raw
    dict. The field helpers below read both the canonical ``RiskItem`` key
    and N4's legacy raw key (preferring the former) so the bridge works
    against either shape — this also keeps it a true "bridge" between the
    pre-contract extractor tests and the post-contract pipeline shape:
      - ``likelihood`` (canonical) / ``probability`` (legacy raw) — same
        concept, diagnostic-only (not used for scoring).
      - ``description`` (canonical) / ``summary`` (legacy raw) — used to
        build ``evidence_summary``.
      - ``source`` (canonical) / ``source_quote`` + ``source_text_snippet``
        (legacy raw) — used to build ``quote``.
    ``risk_score``, ``immediate_alert``, and ``mitigation_suggestion`` have
    **no equivalent field on ``RiskItem``** — they are genuinely dropped at
    the contract boundary, not renamed. Re-adding them would require
    re-freezing the contract with implementer sign-off (out of scope here;
    see TASK-V3-013-12). Decision recorded: leave them out of the frozen
    contract. This is not material — ``risk_score`` already has a graceful
    categorical fallback via ``impact`` (see above), and
    ``immediate_alert``/``mitigation_suggestion`` are informational-only
    ``raw_data`` fields that are simply absent (``None``) for
    contract-shaped input, same as any other optional field with no data.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from src.coherence.models import CoherenceCategory, FindingSignal, SeverityLevel

logger = logging.getLogger(__name__)


# Risk extractor uses some legacy category names that differ from the
# canonical coherence taxonomy.  Map them forward; drop anything else.
_RISK_CATEGORY_TO_COHERENCE: dict[str, CoherenceCategory] = {
    "SCOPE": "SCOPE",
    "BUDGET": "BUDGET",
    "FINANCIAL": "BUDGET",
    "SCHEDULE": "TIME",
    "TIME": "TIME",
    "TECHNICAL": "TECHNICAL",
    "LEGAL": "LEGAL",
    "QUALITY": "QUALITY",
}

_IMPACT_TO_SEVERITY: dict[str, SeverityLevel] = {
    "CRITICAL": "critical",
    "HIGH": "high",
    "MEDIUM": "medium",
    "LOW": "low",
}

_IMPACT_TO_SCORE: dict[str, float] = {
    "CRITICAL": 0.9,
    "HIGH": 0.7,
    "MEDIUM": 0.5,
    "LOW": 0.3,
}

_EXTRACTOR_RULE_ID = "EXTRACTOR-RISK"
_EXTRACTOR_CONFIDENCE = 0.7
_QUOTE_MAX_CHARS = 1000


@dataclass(frozen=True)
class RiskBridgeResult:
    """Closed result of one bridge invocation."""

    signals: tuple[FindingSignal, ...]
    coverage_seed: dict[str, bool]
    dropped_count: int
    dropped_reasons: dict[str, int]


def build_risk_signals(
    risks: list[dict[str, Any]],
    *,
    clause_id: str,
) -> RiskBridgeResult:
    """Convert N4 risk dicts into coherence FindingSignals + coverage seed.

    Args:
        risks: List of risk dicts as produced by
            ``RiskExtractionTool._risk_item_to_dict`` and stored in
            ``state["extracted_risks"]``.
        clause_id: ID of the source document clause (used as the
            ``clause_id`` on every emitted signal so downstream
            diagnostics can trace back).

    Returns:
        ``RiskBridgeResult`` with the emitted signals, coverage seed,
        and drop diagnostics.  Empty input → empty result, never raises.
    """
    signals: list[FindingSignal] = []
    coverage_seed: dict[str, bool] = {}
    dropped_reasons: dict[str, int] = {}

    for raw in risks:
        if not isinstance(raw, dict):
            _bump(dropped_reasons, "not_a_dict")
            continue

        raw_category = (raw.get("category") or "").upper().strip()
        canonical = _RISK_CATEGORY_TO_COHERENCE.get(raw_category)
        if canonical is None:
            _bump(dropped_reasons, "unknown_category")
            logger.warning(
                "risk_signal_bridge.dropped_unknown_category",
                extra={"category": raw_category, "title": raw.get("title")},
            )
            continue

        impact_score = _impact_score_for(raw)
        if impact_score is None:
            _bump(dropped_reasons, "no_impact_signal")
            continue

        signals.append(
            FindingSignal(
                rule_id=_EXTRACTOR_RULE_ID,
                clause_id=clause_id,
                source="llm",
                impact_score=impact_score,
                confidence=_EXTRACTOR_CONFIDENCE,
                severity=_severity_for(raw),
                category=canonical,
                evidence_summary=_summary_for(raw),
                quote=_quote_for(raw),
                raw_data={
                    "extractor_category": raw_category,
                    # `likelihood` is the RiskItem contract field; `probability`
                    # is N4's pre-contract raw key for the same concept (IR-3).
                    "likelihood": raw.get("likelihood", raw.get("probability")),
                    "impact": raw.get("impact"),
                    # Dropped at the RiskItem contract boundary — see IR-3 module
                    # docstring. Only present for pre-contract raw extractor dicts.
                    "risk_score": raw.get("risk_score"),
                    "title": raw.get("title"),
                    "immediate_alert": raw.get("immediate_alert", False),
                    "mitigation_suggestion": raw.get("mitigation_suggestion"),
                },
            )
        )
        coverage_seed[canonical] = True

    dropped = sum(dropped_reasons.values())
    return RiskBridgeResult(
        signals=tuple(signals),
        coverage_seed=coverage_seed,
        dropped_count=dropped,
        dropped_reasons=dict(dropped_reasons),
    )


# ---------------------------------------------------------------------------
# Field helpers
# ---------------------------------------------------------------------------


def _impact_score_for(raw: dict[str, Any]) -> float | None:
    """Derive a [0,1] impact score from risk_score (preferred) or impact."""
    score = raw.get("risk_score")
    if isinstance(score, int | float) and score >= 0:
        # N4 emits risk_score on a 0-10 scale.  Clamp to [0,1] in case
        # the extractor ever returns 0-100 (legacy) or noisy values.
        normalized = float(score) / 10.0 if score <= 10 else float(score) / 100.0
        return max(0.0, min(1.0, normalized))

    impact = (raw.get("impact") or "").upper().strip()
    return _IMPACT_TO_SCORE.get(impact)


def _severity_for(raw: dict[str, Any]) -> SeverityLevel:
    impact = (raw.get("impact") or "").upper().strip()
    return _IMPACT_TO_SEVERITY.get(impact, "medium")


def _summary_for(raw: dict[str, Any]) -> str:
    title = (raw.get("title") or "").strip()
    # `description` is the RiskItem contract field; `summary` is N4's
    # pre-contract raw key for the same concept (IR-3).
    summary = (raw.get("description") or raw.get("summary") or "").strip()
    if title and summary:
        return f"{title} — {summary}"
    return title or summary or "Risk extracted by LLM"


def _quote_for(raw: dict[str, Any]) -> str:
    # `source` is the RiskItem contract field; `source_quote` /
    # `source_text_snippet` are N4's pre-contract raw keys (IR-3).
    quote = (
        raw.get("source")
        or raw.get("source_quote")
        or raw.get("source_text_snippet")
        or ""
    )
    quote = str(quote).strip()
    if len(quote) > _QUOTE_MAX_CHARS:
        return quote[:_QUOTE_MAX_CHARS] + "..."
    return quote


def _bump(counter: dict[str, int], key: str) -> None:
    counter[key] = counter.get(key, 0) + 1
