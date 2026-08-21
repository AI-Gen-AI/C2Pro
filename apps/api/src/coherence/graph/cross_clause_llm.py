"""
LLM cross-clause contradiction depth pass (ADR-009 — cross-document coherence).

The deterministic floor (`nodes._check_legal_conflict` / `_check_scope_conflict`) catches
keyword-antonym conflicts; this pass adds SEMANTIC contradiction detection over clause
pairs via one bounded, structured LLM call. Gated by `low_budget_mode` at the call site,
bounded by `max_pairs`, and FAIL-OPEN — any LLM/parse error yields no findings and never
breaks `/evaluate`.

Refers to Suite ID: TS-UA-COH-XCLAUSE-LLM-001.
"""
from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel, Field

from src.coherence.graph.state import CrossClausePair
from src.coherence.models import FindingSignal
from src.core.ai.anthropic_wrapper import AIRequest, AnthropicWrapper
from src.core.ai.model_router import AITaskType

logger = logging.getLogger(__name__)

# Impact by severity (mirrors the deterministic heuristics' magnitudes).
_SEVERITY_IMPACT: dict[str, float] = {"low": 0.3, "medium": 0.55, "high": 0.75, "critical": 0.9}
_MAX_CLAUSE_CHARS = 400


class _PairVerdict(BaseModel):
    """One LLM verdict for a clause pair."""

    index: int
    contradicts: bool = False
    category: Literal["LEGAL", "SCOPE", "BUDGET", "TIME", "TECHNICAL", "QUALITY"] = "LEGAL"
    severity: Literal["low", "medium", "high", "critical"] = "high"
    explanation: str = ""


class _BatchVerdict(BaseModel):
    verdicts: list[_PairVerdict] = Field(default_factory=list)


def _build_prompt(pairs: list[CrossClausePair]) -> str:
    lines = [
        "You are a contract coherence auditor. For each clause pair below, decide whether the "
        "two clauses CONTRADICT each other — conflicting obligations, terms, quantities, "
        "penalties/liability, scope inclusion vs exclusion, or dates. Vagueness or incompleteness "
        "alone is NOT a contradiction; only flag a genuine conflict between the two clauses. "
        'Respond as JSON {"verdicts": [{"index": int, "contradicts": bool, "category": one of '
        "LEGAL|SCOPE|BUDGET|TIME|TECHNICAL|QUALITY, \"severity\": low|medium|high|critical, "
        '"explanation": short}]} with exactly one verdict per pair index.',
        "",
    ]
    for index, pair in enumerate(pairs):
        lines.append(f"[{index}] A ({pair.clause_a.category}): {pair.clause_a.text[:_MAX_CLAUSE_CHARS]}")
        lines.append(f"    B ({pair.clause_b.category}): {pair.clause_b.text[:_MAX_CLAUSE_CHARS]}")
    return "\n".join(lines)


async def llm_contradiction_signals(
    pairs: list[CrossClausePair],
    *,
    wrapper: AnthropicWrapper,
    max_pairs: int = 20,
) -> list[FindingSignal]:
    """One bounded, structured LLM call over clause pairs → contradiction `FindingSignal`s.

    FAIL-OPEN: any error (LLM call or JSON/schema parse) returns ``[]`` and never raises, so
    the depth pass can never break the live evaluation.
    """
    considered = pairs[:max_pairs]
    if not considered:
        return []

    request = AIRequest(prompt=_build_prompt(considered), task_type=AITaskType.COHERENCE_ANALYSIS)
    try:
        batch = await wrapper.generate_structured(request, _BatchVerdict)
    except Exception:  # noqa: BLE001 — depth pass must never break /evaluate
        logger.warning("cross_clause_llm_failed", exc_info=True)
        return []

    signals: list[FindingSignal] = []
    for verdict in batch.verdicts:
        if not verdict.contradicts or not 0 <= verdict.index < len(considered):
            continue
        pair = considered[verdict.index]
        signals.append(
            FindingSignal(
                rule_id="CROSS-LLM-CONTRADICTION",
                clause_id=f"{pair.clause_a.clause_id}|{pair.clause_b.clause_id}",
                source="llm",
                impact_score=_SEVERITY_IMPACT.get(verdict.severity, 0.75),
                confidence=0.7,
                severity=verdict.severity,
                category=verdict.category,
                evidence_summary=(verdict.explanation[:300] or "Cross-clause contradiction detected."),
                quote=f"A: {pair.clause_a.text[:80]}... | B: {pair.clause_b.text[:80]}...",
                raw_data={"source": "llm_cross_clause", "pair_index": verdict.index},
            )
        )
    return signals


__all__ = ["llm_contradiction_signals"]
