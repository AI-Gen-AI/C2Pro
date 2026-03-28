# Coherence Engine v0.3 — LangGraph Subgraph Integration

## Architecture Decision: Composable Subgraph for Project-Level Coherence

---

## 1. Why a Subgraph (Not a New Node in the Existing Graph)

Your master flow is: `Upload → Anonymize → Extract → Analyze → Coherence`

The coherence evaluation is fundamentally different from the preceding steps because it operates at **project scope**, not document scope. The extraction and analysis steps run per-document, but coherence must see *all* documents in a project simultaneously — contracts against schedules against budgets. This is C2Pro's tridimensional auditing core.

A **composable subgraph** is the right choice because:

1. **Different granularity** — The upstream nodes process individual documents. The coherence subgraph consumes the *aggregate output* of all document extractions for a project.
2. **Independent lifecycle** — The scoring algorithm, LLM prompts, and rule registry will evolve faster than the ingestion pipeline. A subgraph can be versioned and tested independently.
3. **Reusability** — The same subgraph can be invoked from the main pipeline *and* from a standalone API endpoint (`POST /v0/coherence/evaluate`) and future re-evaluation triggers.
4. **Parallel internal nodes** — Inside the subgraph, deterministic evaluation and LLM semantic evaluation run in parallel. LangGraph's native fan-out handles this cleanly.

### How It Connects to the Main Graph

```
Main LangGraph Pipeline
┌────────────────────────────────────────────────────────────────┐
│                                                                │
│  [Upload] → [Anonymize] → [Extract] → [Analyze] ──┐           │
│                                                     │           │
│                              ┌──────────────────────▼────────┐ │
│                              │   coherence_subgraph          │ │
│                              │   (invoked as compiled graph) │ │
│                              └──────────────────────┬────────┘ │
│                                                     │           │
│                                              [Store Result]     │
└────────────────────────────────────────────────────────────────┘
```

In LangGraph terms, the main graph calls the subgraph like this:

```python
from langgraph.graph import StateGraph
from coherence.graph import coherence_subgraph  # The compiled subgraph

main_graph = StateGraph(MainPipelineState)
# ... upstream nodes ...
main_graph.add_node("coherence", coherence_subgraph)
main_graph.add_edge("analyze", "coherence")
main_graph.add_edge("coherence", "store_result")
```

---

## 2. Subgraph State Design

The subgraph state carries everything needed for a full project coherence evaluation, including references to existing embeddings and chunks from your RAG infrastructure.

```python
"""
coherence/graph/state.py — LangGraph state for the coherence subgraph.
Follows C2Pro hexagonal architecture: this lives in the domain/application layer.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Literal
from uuid import UUID


@dataclass
class ClauseWithEmbedding:
    """A clause enriched with its embedding vector and chunk reference."""
    clause_id: str
    document_id: str
    text: str
    data: dict  # structured data extracted upstream
    category: Literal["SCOPE", "BUDGET", "TIME", "TECH", "LEGAL", "QUALITY"]
    embedding_id: Optional[str] = None  # reference to pgvector row
    chunk_ids: list[str] = field(default_factory=list)  # associated chunk IDs
    

@dataclass  
class FindingSignal:
    """Unified signal from any evaluator (deterministic or LLM)."""
    rule_id: str
    source: Literal["deterministic", "llm", "rag_similarity"]
    clause_id: str
    impact_score: float  # 0.0 to 1.0
    confidence: float  # 0.0 to 1.0
    severity: Literal["critical", "high", "medium", "low"]
    evidence_summary: str = ""
    quote: str = ""
    related_clause_ids: list[str] = field(default_factory=list)


@dataclass
class CoherenceGraphState:
    """
    Full state for the coherence subgraph.
    
    This state is populated by the upstream 'analyze' node and then
    flows through all coherence evaluation nodes.
    """
    # ─── Input (set by upstream pipeline) ─────────────────────
    project_id: str = ""
    tenant_id: Optional[UUID] = None
    clauses: list[ClauseWithEmbedding] = field(default_factory=list)
    
    # Configuration
    low_budget_mode: bool = True
    
    # ─── Internal (populated by subgraph nodes) ───────────────
    # Phase 1: Deterministic findings
    deterministic_signals: list[FindingSignal] = field(default_factory=list)
    
    # Phase 2: RAG similarity findings (cross-document)
    rag_signals: list[FindingSignal] = field(default_factory=list)
    
    # Phase 3: LLM semantic findings  
    llm_signals: list[FindingSignal] = field(default_factory=list)
    
    # Phase 4: Cross-clause findings
    cross_clause_signals: list[FindingSignal] = field(default_factory=list)
    
    # ─── Output (consumed by downstream nodes) ────────────────
    all_signals: list[FindingSignal] = field(default_factory=list)
    score: float = 100.0
    alerts: list[dict] = field(default_factory=list)
    diagnostics: dict = field(default_factory=dict)
    
    # Cost tracking
    total_llm_cost_usd: float = 0.0
    llm_calls_count: int = 0
```

---

## 3. The Subgraph: Node-by-Node Architecture

```
                    ┌──────────────────────┐
                    │   prepare_context    │
                    │  (load embeddings,   │
                    │   group by category) │
                    └──────────┬───────────┘
                               │
                  ┌────────────┼────────────┐
                  │            │            │
         ┌───────▼──────┐ ┌───▼────────┐ ┌─▼──────────────┐
         │ deterministic │ │ rag_similar│ │ llm_semantic    │
         │ _evaluate     │ │ ity_check  │ │ _evaluate       │
         │               │ │            │ │                 │
         │ Agent A       │ │ Agent A+   │ │ Agent B         │
         │ Hard rules    │ │ Embedding  │ │ Qualitative     │
         │ Thresholds    │ │ similarity │ │ analysis        │
         │ Date checks   │ │ detection  │ │ Ambiguity check │
         └───────┬───────┘ └───┬────────┘ └─┬───────────────┘
                 │             │             │
                 └─────────────┼─────────────┘
                               │
                    ┌──────────▼───────────┐
                    │  cross_clause_eval   │
                    │                      │
                    │  Agent B+            │
                    │  Contradictions      │
                    │  Timeline conflicts  │
                    │  Scope overlaps      │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  scoring_arbiter     │
                    │                      │
                    │  Agent C             │
                    │  Merge all signals   │
                    │  Exponential decay   │
                    │  Scope normalization │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  format_output       │
                    │  (CoherenceResult)   │
                    └──────────────────────┘
```

### Injectable Code: `coherence/graph/graph.py`

```python
"""
coherence/graph/graph.py — LangGraph coherence subgraph definition.

This is the composable subgraph that plugs into the main C2Pro pipeline.
It can also be invoked standalone via the coherence API endpoint.

Location: apps/api/src/coherence/graph/graph.py
"""

from langgraph.graph import StateGraph, END
from coherence.graph.state import CoherenceGraphState
from coherence.graph.nodes import (
    prepare_context,
    deterministic_evaluate,
    rag_similarity_check,
    llm_semantic_evaluate,
    cross_clause_eval,
    scoring_arbiter,
    format_output,
)


def build_coherence_subgraph() -> StateGraph:
    """
    Build the coherence evaluation subgraph.
    
    Graph topology:
      prepare_context 
        → [deterministic_evaluate, rag_similarity_check, llm_semantic_evaluate]  (parallel)
        → cross_clause_eval 
        → scoring_arbiter 
        → format_output
    """
    graph = StateGraph(CoherenceGraphState)
    
    # ─── Nodes ────────────────────────────────────────────────
    graph.add_node("prepare_context", prepare_context)
    graph.add_node("deterministic_evaluate", deterministic_evaluate)
    graph.add_node("rag_similarity_check", rag_similarity_check)
    graph.add_node("llm_semantic_evaluate", llm_semantic_evaluate)
    graph.add_node("cross_clause_eval", cross_clause_eval)
    graph.add_node("scoring_arbiter", scoring_arbiter)
    graph.add_node("format_output", format_output)
    
    # ─── Edges ────────────────────────────────────────────────
    # Entry point
    graph.set_entry_point("prepare_context")
    
    # Fan-out: three evaluators run in parallel after preparation
    graph.add_edge("prepare_context", "deterministic_evaluate")
    graph.add_edge("prepare_context", "rag_similarity_check")
    graph.add_edge("prepare_context", "llm_semantic_evaluate")
    
    # Fan-in: all three feed into cross-clause analysis
    graph.add_edge("deterministic_evaluate", "cross_clause_eval")
    graph.add_edge("rag_similarity_check", "cross_clause_eval")
    graph.add_edge("llm_semantic_evaluate", "cross_clause_eval")
    
    # Sequential: cross-clause → scoring → output
    graph.add_edge("cross_clause_eval", "scoring_arbiter")
    graph.add_edge("scoring_arbiter", "format_output")
    graph.add_edge("format_output", END)
    
    return graph


# Compile the subgraph for use in the main pipeline
coherence_subgraph = build_coherence_subgraph().compile()
```

---

## 4. Node Implementations

### Injectable Code: `coherence/graph/nodes.py`

```python
"""
coherence/graph/nodes.py — Individual node implementations for the coherence subgraph.

Each function receives and returns CoherenceGraphState.
Follows hexagonal architecture: nodes orchestrate, domain logic lives in services.

Location: apps/api/src/coherence/graph/nodes.py
"""

import json
import logging
import math
from typing import Optional
from uuid import UUID

from coherence.graph.state import (
    CoherenceGraphState,
    ClauseWithEmbedding,
    FindingSignal,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# NODE 1: PREPARE CONTEXT
# ═══════════════════════════════════════════════════════════════

async def prepare_context(state: CoherenceGraphState) -> dict:
    """
    Enriches clauses with their embeddings and chunks from pgvector/RAG store.
    Groups clauses by category for efficient downstream processing.
    
    This node bridges the upstream extraction pipeline with the coherence
    evaluation by loading embedding references that the rag_similarity_check
    node will use.
    """
    from coherence.ports import EmbeddingRepositoryPort
    
    # Get the embedding repository (injected via DI container)
    # In the actual implementation, this comes from the composition root
    embedding_repo: EmbeddingRepositoryPort = _get_embedding_repo()
    
    enriched_clauses = []
    for clause in state.clauses:
        # Load embedding reference if not already present
        if not clause.embedding_id:
            embedding = await embedding_repo.find_by_clause_id(
                clause_id=clause.clause_id,
                tenant_id=state.tenant_id,
            )
            if embedding:
                clause.embedding_id = embedding.id
                clause.chunk_ids = embedding.chunk_ids
        
        enriched_clauses.append(clause)
    
    return {
        "clauses": enriched_clauses,
    }


# ═══════════════════════════════════════════════════════════════
# NODE 2A: DETERMINISTIC EVALUATE (Agent A)
# ═══════════════════════════════════════════════════════════════

async def deterministic_evaluate(state: CoherenceGraphState) -> dict:
    """
    Agent A — Deterministic Risk Analyst.
    
    Evaluates hard rules that don't need LLM:
    - Budget thresholds (current > planned * 1.1)
    - Date validations (past dates, unrealistic timelines)
    - Missing required fields
    - Numeric constraint violations
    
    These produce confidence=1.0 signals (no uncertainty).
    """
    signals: list[FindingSignal] = []
    
    for clause in state.clauses:
        data = clause.data or {}
        
        # ─── Budget overrun detection ─────────────────────────
        if clause.category == "BUDGET":
            current = data.get("current")
            planned = data.get("planned")
            if current is not None and planned is not None and planned > 0:
                overrun_ratio = current / planned
                if overrun_ratio > 1.0:
                    # Continuous impact: 10% over = 0.4, 25% over = 0.7, 50%+ = 0.95
                    excess = overrun_ratio - 1.0
                    impact = min(0.95, 0.4 + (excess * 2.2))
                    
                    signals.append(FindingSignal(
                        rule_id="DET-BUDGET-OVERRUN",
                        source="deterministic",
                        clause_id=clause.clause_id,
                        impact_score=round(impact, 3),
                        confidence=1.0,
                        severity=_impact_to_severity(impact),
                        evidence_summary=(
                            f"Budget overrun: {current:,.0f} vs planned "
                            f"{planned:,.0f} ({(excess*100):.1f}% over)"
                        ),
                        quote=clause.text[:200],
                    ))
        
        # ─── Schedule delay detection ─────────────────────────
        if clause.category == "TIME":
            status = data.get("status", "").lower()
            if status in ("delayed", "at_risk", "behind"):
                impact_map = {"delayed": 0.7, "at_risk": 0.5, "behind": 0.6}
                impact = impact_map.get(status, 0.5)
                
                signals.append(FindingSignal(
                    rule_id="DET-SCHEDULE-DELAY",
                    source="deterministic",
                    clause_id=clause.clause_id,
                    impact_score=impact,
                    confidence=1.0,
                    severity=_impact_to_severity(impact),
                    evidence_summary=f"Schedule status: {status}",
                    quote=clause.text[:200],
                ))
        
        # ─── Past date detection ──────────────────────────────
        if clause.category == "TIME":
            from datetime import date, datetime
            end_date_str = data.get("end_date") or data.get("deadline")
            if end_date_str:
                try:
                    if isinstance(end_date_str, str):
                        end_date = datetime.fromisoformat(
                            end_date_str.replace("Z", "+00:00")
                        ).date()
                    else:
                        end_date = end_date_str
                    
                    if end_date < date.today():
                        days_past = (date.today() - end_date).days
                        impact = min(0.9, 0.5 + (days_past / 365) * 0.4)
                        
                        signals.append(FindingSignal(
                            rule_id="DET-DATE-PAST",
                            source="deterministic",
                            clause_id=clause.clause_id,
                            impact_score=round(impact, 3),
                            confidence=1.0,
                            severity=_impact_to_severity(impact),
                            evidence_summary=(
                                f"Deadline {end_date} is {days_past} days in the past"
                            ),
                            quote=clause.text[:200],
                        ))
                except (ValueError, TypeError):
                    pass
        
        # ─── Contract review overdue ──────────────────────────
        if clause.category == "LEGAL":
            from datetime import date, datetime, timedelta
            last_review = data.get("last_review_date")
            if last_review:
                try:
                    if isinstance(last_review, str):
                        review_date = datetime.fromisoformat(
                            last_review.replace("Z", "+00:00")
                        ).date()
                    else:
                        review_date = last_review
                    
                    days_since = (date.today() - review_date).days
                    if days_since > 180:  # 6 months
                        impact = min(0.7, 0.25 + (days_since / 730) * 0.45)
                        signals.append(FindingSignal(
                            rule_id="DET-REVIEW-OVERDUE",
                            source="deterministic",
                            clause_id=clause.clause_id,
                            impact_score=round(impact, 3),
                            confidence=1.0,
                            severity=_impact_to_severity(impact),
                            evidence_summary=(
                                f"Last review {days_since} days ago ({review_date})"
                            ),
                            quote=clause.text[:200],
                        ))
                except (ValueError, TypeError):
                    pass
    
    return {"deterministic_signals": signals}


# ═══════════════════════════════════════════════════════════════
# NODE 2B: RAG SIMILARITY CHECK (Agent A+ / Embedding-based)
# ═══════════════════════════════════════════════════════════════

async def rag_similarity_check(state: CoherenceGraphState) -> dict:
    """
    Agent A+ — Embedding Similarity Detector.
    
    Uses the existing pgvector embeddings to detect:
    - Contradictory clauses with high textual similarity but opposing semantics
    - Duplicate or redundant clauses across documents
    - Clauses that reference the same entity with different values
    
    This is computationally cheap (vector cosine similarity in PostgreSQL)
    and doesn't require any LLM calls.
    """
    signals: list[FindingSignal] = []
    
    if len(state.clauses) < 2:
        return {"rag_signals": signals}
    
    from coherence.ports import EmbeddingRepositoryPort
    embedding_repo: EmbeddingRepositoryPort = _get_embedding_repo()
    
    # Group clauses by category for intra-category comparison
    category_groups: dict[str, list[ClauseWithEmbedding]] = {}
    for clause in state.clauses:
        category_groups.setdefault(clause.category, []).append(clause)
    
    for category, group_clauses in category_groups.items():
        if len(group_clauses) < 2:
            continue
        
        # Find high-similarity pairs within the same category
        # This query runs in pgvector: SELECT ... ORDER BY embedding <=> target
        for i, clause_a in enumerate(group_clauses):
            if not clause_a.embedding_id:
                continue
            
            similar_clauses = await embedding_repo.find_similar(
                embedding_id=clause_a.embedding_id,
                tenant_id=state.tenant_id,
                threshold=0.85,  # High similarity threshold
                limit=5,
                exclude_clause_ids=[clause_a.clause_id],
            )
            
            for match in similar_clauses:
                # High similarity + same category = potential contradiction or redundancy
                similarity = match.similarity_score
                
                # Only flag if from different documents
                matched_clause = next(
                    (c for c in group_clauses 
                     if c.clause_id == match.clause_id),
                    None
                )
                if not matched_clause:
                    continue
                if matched_clause.document_id == clause_a.document_id:
                    continue  # Same document — skip
                
                # Impact based on similarity (0.85-1.0 range → 0.3-0.7 impact)
                impact = 0.3 + (similarity - 0.85) * 2.67
                impact = round(min(0.7, impact), 3)
                
                signals.append(FindingSignal(
                    rule_id=f"RAG-SIMILARITY-{category}",
                    source="rag_similarity",
                    clause_id=clause_a.clause_id,
                    impact_score=impact,
                    confidence=round(similarity, 3),
                    severity=_impact_to_severity(impact),
                    evidence_summary=(
                        f"High similarity ({similarity:.0%}) between clauses "
                        f"from different documents in category {category}"
                    ),
                    related_clause_ids=[match.clause_id],
                ))
    
    return {"rag_signals": signals}


# ═══════════════════════════════════════════════════════════════
# NODE 2C: LLM SEMANTIC EVALUATE (Agent B)
# ═══════════════════════════════════════════════════════════════

async def llm_semantic_evaluate(state: CoherenceGraphState) -> dict:
    """
    Agent B — LLM Semantic Evaluator.
    
    Uses Claude (Haiku in low_budget_mode, Sonnet otherwise) to evaluate
    qualitative rules: ambiguity, unclear responsibilities, vague payment
    terms, missing quality standards.
    
    In low_budget_mode: sends ALL clauses + ALL rules in a single batch call.
    In standard mode: sends individual clause×rule pairs in parallel.
    """
    from coherence.graph.prompts import (
        COHERENCE_SYSTEM_PROMPT,
        BATCH_EVALUATION_PROMPT,
        RULE_EVALUATION_PROMPT,
    )
    from core.ai.anthropic_wrapper import get_anthropic_wrapper
    
    signals: list[FindingSignal] = []
    llm = get_anthropic_wrapper()
    
    # Predefined qualitative rules
    QUALITATIVE_RULES = [
        {
            "id": "R-SCOPE-CLARITY-01",
            "name": "Scope Clarity",
            "description": "Checks for ambiguous scope terms",
            "detection_logic": (
                "Look for open-ended phrases like 'as needed', "
                "'as deemed necessary', 'and other work', 'etc.', "
                "'approximately', 'reasonable efforts'"
            ),
            "category": "SCOPE",
        },
        {
            "id": "R-PAYMENT-CLARITY-01",
            "name": "Payment Terms",
            "description": "Validates payment specificity",
            "detection_logic": (
                "Check that payments specify exact amounts, currency, "
                "due dates, and payment conditions. Flag 'to be determined', "
                "'market rate', 'competitive pricing'"
            ),
            "category": "BUDGET",
        },
        {
            "id": "R-RESPONSIBILITY-01",
            "name": "Responsibility Assignment",
            "description": "Checks responsibility clarity",
            "detection_logic": (
                "Verify that each obligation has a named responsible party. "
                "Flag passive voice ('shall be done') without actor"
            ),
            "category": "LEGAL",
        },
        {
            "id": "R-TERMINATION-01",
            "name": "Termination Conditions",
            "description": "Validates termination clauses",
            "detection_logic": (
                "Check for specific termination triggers, notice periods, "
                "and balanced termination rights"
            ),
            "category": "LEGAL",
        },
        {
            "id": "R-QUALITY-STANDARDS-01",
            "name": "Quality Standards",
            "description": "Validates quality references",
            "detection_logic": (
                "Look for references to specific standards (ISO, ASTM, EN). "
                "Flag vague 'industry standards' or 'best practices'"
            ),
            "category": "QUALITY",
        },
    ]
    
    # Filter rules by categories present in clauses
    active_categories = {c.category for c in state.clauses}
    active_rules = [
        r for r in QUALITATIVE_RULES 
        if r["category"] in active_categories
    ]
    
    if not active_rules:
        return {"llm_signals": signals, "llm_calls_count": 0}
    
    if state.low_budget_mode:
        # ─── Batch mode: single LLM call ─────────────────────
        clauses_data = [
            {"id": c.clause_id, "text": c.text[:500], "category": c.category}
            for c in state.clauses
        ]
        
        prompt = BATCH_EVALUATION_PROMPT.format(
            rules_json=json.dumps(active_rules, indent=2),
            clauses_json=json.dumps(clauses_data, indent=2),
        )
        
        try:
            response = await llm.generate(
                prompt=prompt,
                system_prompt=COHERENCE_SYSTEM_PROMPT,
                task_type="coherence_check",  # Routes to Haiku
                tenant_id=state.tenant_id,
            )
            
            findings = _parse_llm_json(response)
            
            for f in findings:
                impact = _clamp(float(f.get("impact_score", 0)))
                confidence = _clamp(float(f.get("confidence", 0.5)))
                
                if impact > 0.2:
                    signals.append(FindingSignal(
                        rule_id=f.get("rule_id", "unknown"),
                        source="llm",
                        clause_id=f.get("clause_id", "unknown"),
                        impact_score=round(impact, 3),
                        confidence=round(confidence, 3),
                        severity=_impact_to_severity(impact),
                        evidence_summary=f.get("evidence", ""),
                        quote=f.get("quote", ""),
                    ))
            
            cost = getattr(response, 'cost_usd', 0.0)
            return {
                "llm_signals": signals,
                "total_llm_cost_usd": state.total_llm_cost_usd + cost,
                "llm_calls_count": state.llm_calls_count + 1,
            }
            
        except Exception as e:
            logger.error(f"Batch LLM evaluation failed: {e}")
            return {"llm_signals": signals}
    
    else:
        # ─── Individual mode: parallel calls ──────────────────
        import asyncio
        
        async def evaluate_single(clause, rule):
            prompt = RULE_EVALUATION_PROMPT.format(
                rule_id=rule["id"],
                rule_name=rule["name"],
                rule_description=rule["description"],
                detection_logic=rule["detection_logic"],
                category=rule["category"],
                clause_id=clause.clause_id,
                clause_text=clause.text[:500],
                clause_data=json.dumps(clause.data or {}, default=str),
            )
            
            resp = await llm.generate(
                prompt=prompt,
                system_prompt=COHERENCE_SYSTEM_PROMPT,
                task_type="coherence_analysis",  # Routes to Sonnet
                tenant_id=state.tenant_id,
            )
            return resp, clause.clause_id, rule["id"]
        
        tasks = [
            evaluate_single(clause, rule)
            for clause in state.clauses
            for rule in active_rules
            if rule["category"] == clause.category
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_cost = 0.0
        
        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"LLM eval failed: {result}")
                continue
            
            resp, clause_id, rule_id = result
            total_cost += getattr(resp, 'cost_usd', 0.0)
            
            parsed = _parse_llm_json_single(resp)
            if parsed:
                impact = _clamp(float(parsed.get("impact_score", 0)))
                confidence = _clamp(float(parsed.get("confidence", 0.5)))
                
                if impact > 0.2:
                    signals.append(FindingSignal(
                        rule_id=rule_id,
                        source="llm",
                        clause_id=clause_id,
                        impact_score=round(impact, 3),
                        confidence=round(confidence, 3),
                        severity=_impact_to_severity(impact),
                        evidence_summary=parsed.get("evidence", ""),
                        quote=parsed.get("quote", ""),
                    ))
        
        return {
            "llm_signals": signals,
            "total_llm_cost_usd": state.total_llm_cost_usd + total_cost,
            "llm_calls_count": state.llm_calls_count + len(tasks),
        }


# ═══════════════════════════════════════════════════════════════
# NODE 3: CROSS-CLAUSE EVALUATION (Agent B+)
# ═══════════════════════════════════════════════════════════════

async def cross_clause_eval(state: CoherenceGraphState) -> dict:
    """
    Agent B+ — Cross-Clause Coherence Analyzer.
    
    This is the core of C2Pro's tridimensional auditing: it checks
    coherence BETWEEN documents:
    - Contract says X but schedule says Y
    - Budget allocates Z but scope requires more
    - Timeline conflicts between parallel workstreams
    
    Uses RAG signals as hints: if rag_similarity_check found high-similarity
    pairs across documents, this node sends those specific pairs to the LLM
    for semantic contradiction detection, instead of sending all clauses.
    
    This dramatically reduces token cost while focusing attention on the
    most likely contradiction candidates.
    """
    from coherence.graph.prompts import (
        COHERENCE_SYSTEM_PROMPT,
        CROSS_CLAUSE_PROMPT,
    )
    from core.ai.anthropic_wrapper import get_anthropic_wrapper
    
    signals: list[FindingSignal] = []
    
    if len(state.clauses) < 2:
        return {"cross_clause_signals": signals}
    
    llm = get_anthropic_wrapper()
    
    # Strategy: Use RAG similarity signals to focus the LLM analysis
    # Instead of sending ALL clauses, send only the suspicious pairs
    # plus a representative sample of each category
    
    # Collect clause pairs flagged by RAG similarity
    flagged_pairs: set[tuple[str, str]] = set()
    for sig in state.rag_signals:
        for related in sig.related_clause_ids:
            pair = tuple(sorted([sig.clause_id, related]))
            flagged_pairs.add(pair)
    
    # Build focused clause set: flagged clauses + 1 representative per category
    focused_clause_ids: set[str] = set()
    for pair in flagged_pairs:
        focused_clause_ids.update(pair)
    
    # Add one representative per category (for tridimensional coverage)
    seen_categories: set[str] = set()
    for clause in state.clauses:
        if clause.category not in seen_categories:
            focused_clause_ids.add(clause.clause_id)
            seen_categories.add(clause.category)
    
    # If no RAG flags, use all clauses (but limited to 15 for token budget)
    if not flagged_pairs:
        focused_clause_ids = {c.clause_id for c in state.clauses[:15]}
    
    focused_clauses = [
        c for c in state.clauses if c.clause_id in focused_clause_ids
    ]
    
    clauses_data = [
        {
            "id": c.clause_id,
            "text": c.text[:400],
            "category": c.category,
            "document_id": c.document_id,
            "data": c.data or {},
        }
        for c in focused_clauses
    ]
    
    prompt = CROSS_CLAUSE_PROMPT.format(
        clauses_json=json.dumps(clauses_data, indent=2, default=str),
    )
    
    try:
        task_type = (
            "coherence_check" if state.low_budget_mode 
            else "coherence_analysis"
        )
        
        response = await llm.generate(
            prompt=prompt,
            system_prompt=COHERENCE_SYSTEM_PROMPT,
            task_type=task_type,
            tenant_id=state.tenant_id,
        )
        
        issues = _parse_llm_json(response)
        
        for issue in issues:
            impact = _clamp(float(issue.get("impact_score", 0)))
            confidence = _clamp(float(issue.get("confidence", 0.5)))
            
            if impact > 0.2:
                affected = issue.get("affected_clauses", [])
                signals.append(FindingSignal(
                    rule_id=f"CROSS-{issue.get('type', 'unknown').upper()}",
                    source="llm",
                    clause_id=affected[0] if affected else "unknown",
                    impact_score=round(impact, 3),
                    confidence=round(confidence, 3),
                    severity=_impact_to_severity(impact),
                    evidence_summary=issue.get("description", ""),
                    related_clause_ids=affected[1:] if len(affected) > 1 else [],
                ))
        
        cost = getattr(response, 'cost_usd', 0.0)
        return {
            "cross_clause_signals": signals,
            "total_llm_cost_usd": state.total_llm_cost_usd + cost,
            "llm_calls_count": state.llm_calls_count + 1,
        }
        
    except Exception as e:
        logger.error(f"Cross-clause analysis failed: {e}")
        return {"cross_clause_signals": signals}


# ═══════════════════════════════════════════════════════════════
# NODE 4: SCORING ARBITER (Agent C)
# ═══════════════════════════════════════════════════════════════

async def scoring_arbiter(state: CoherenceGraphState) -> dict:
    """
    Agent C — Scoring Arbiter.
    
    Merges all signals from Agents A, A+, B, and B+ into a single
    coherence score using exponential decay with scope normalization.
    
    Formula: score = 100 × e^(-λ × penalty_density)
    Where penalty_density = Σ(impact × confidence × weight) / scope_factor
    """
    # Merge all signals
    all_signals = (
        state.deterministic_signals 
        + state.rag_signals 
        + state.llm_signals 
        + state.cross_clause_signals
    )
    
    if not all_signals:
        return {
            "all_signals": [],
            "score": 100.0,
            "diagnostics": {
                "total_findings": 0,
                "score_formula": "no findings → 100.0",
            },
        }
    
    # ─── Configuration ────────────────────────────────────────
    SEVERITY_WEIGHTS = {
        "critical": 1.0,
        "high": 0.7,
        "medium": 0.4,
        "low": 0.15,
    }
    
    SOURCE_WEIGHTS = {
        "deterministic": 1.0,
        "rag_similarity": 0.9,
        "llm": 0.85,
    }
    
    DECAY_LAMBDA = 2.5
    SCORE_FLOOR = 5.0
    SCORE_CEILING = 97.0
    SCOPE_NORM_K = 0.12
    
    # ─── Calculate raw weighted penalty ───────────────────────
    raw_penalty = 0.0
    for sig in all_signals:
        sev_w = SEVERITY_WEIGHTS.get(sig.severity, 0.4)
        src_w = SOURCE_WEIGHTS.get(sig.source, 0.85)
        contribution = sig.impact_score * sig.confidence * sev_w * src_w
        raw_penalty += contribution
    
    # ─── Scope normalization ──────────────────────────────────
    num_clauses = len(state.clauses)
    scope_factor = max(1.0, num_clauses * SCOPE_NORM_K)
    penalty_density = raw_penalty / scope_factor
    
    # ─── Exponential decay ────────────────────────────────────
    raw_score = 100.0 * math.exp(-DECAY_LAMBDA * penalty_density)
    
    # ─── Apply bounds ─────────────────────────────────────────
    score = min(raw_score, SCORE_CEILING)
    score = max(score, SCORE_FLOOR)
    score = round(score, 1)
    
    # ─── Diagnostics ──────────────────────────────────────────
    diagnostics = {
        "total_findings": len(all_signals),
        "by_source": {
            "deterministic": len(state.deterministic_signals),
            "rag_similarity": len(state.rag_signals),
            "llm_semantic": len(state.llm_signals),
            "cross_clause": len(state.cross_clause_signals),
        },
        "by_severity": _severity_dist(all_signals),
        "raw_penalty": round(raw_penalty, 4),
        "scope_factor": round(scope_factor, 4),
        "penalty_density": round(penalty_density, 4),
        "raw_score_pre_bounds": round(raw_score, 2),
        "final_score": score,
        "avg_impact": round(
            sum(s.impact_score for s in all_signals) / len(all_signals), 3
        ),
        "avg_confidence": round(
            sum(s.confidence for s in all_signals) / len(all_signals), 3
        ),
        "llm_cost_usd": round(state.total_llm_cost_usd, 6),
        "llm_calls": state.llm_calls_count,
    }
    
    return {
        "all_signals": all_signals,
        "score": score,
        "diagnostics": diagnostics,
    }


# ═══════════════════════════════════════════════════════════════
# NODE 5: FORMAT OUTPUT
# ═══════════════════════════════════════════════════════════════

async def format_output(state: CoherenceGraphState) -> dict:
    """
    Converts internal FindingSignals to the public API Alert format.
    Ensures backward compatibility with POST /v0/coherence/evaluate.
    """
    alerts = []
    for sig in state.all_signals:
        alerts.append({
            "rule_id": sig.rule_id,
            "severity": sig.severity,
            "message": (
                f"Alert for rule '{sig.rule_id}' "
                f"(impact: {sig.impact_score:.2f}, "
                f"confidence: {sig.confidence:.2f})"
            ),
            "evidence": {
                "source_clause_id": sig.clause_id,
                "claim": sig.evidence_summary,
                "quote": sig.quote,
            },
        })
    
    return {"alerts": alerts}


# ═══════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def _impact_to_severity(impact: float) -> str:
    if impact >= 0.85:
        return "critical"
    elif impact >= 0.6:
        return "high"
    elif impact >= 0.35:
        return "medium"
    return "low"


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _severity_dist(signals: list) -> dict:
    dist = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for s in signals:
        if s.severity in dist:
            dist[s.severity] += 1
    return dist


def _parse_llm_json(response) -> list:
    """Parse LLM response into a list of dicts."""
    content = response.content if hasattr(response, 'content') else response
    if isinstance(content, str):
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            content = content.rsplit("```", 1)[0]
        return json.loads(content)
    elif isinstance(content, list):
        return content
    return []


def _parse_llm_json_single(response) -> Optional[dict]:
    """Parse LLM response into a single dict."""
    content = response.content if hasattr(response, 'content') else response
    if isinstance(content, str):
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            content = content.rsplit("```", 1)[0]
        return json.loads(content)
    elif isinstance(content, dict):
        return content
    return None


def _get_embedding_repo():
    """
    Get the embedding repository from the DI container.
    In production, this is injected. For standalone use, returns a stub.
    """
    # This would be replaced by actual DI resolution in the composition root.
    # Example: return container.resolve(EmbeddingRepositoryPort)
    raise NotImplementedError(
        "Wire this to your composition root. "
        "See coherence/ports.py for the interface."
    )
```

---

## 5. Ports for RAG Integration

```python
"""
coherence/ports.py — Ports (interfaces) for the coherence module.

These follow the hexagonal architecture pattern: the coherence graph
nodes depend on these interfaces, not on concrete implementations.

Location: apps/api/src/coherence/ports.py
"""

from typing import Protocol, Optional
from uuid import UUID
from dataclasses import dataclass


@dataclass
class EmbeddingMatch:
    """Result from a similarity search."""
    clause_id: str
    embedding_id: str
    similarity_score: float
    chunk_ids: list[str]


@dataclass
class EmbeddingRecord:
    """Reference to a stored embedding."""
    id: str
    clause_id: str
    chunk_ids: list[str]


class EmbeddingRepositoryPort(Protocol):
    """
    Port for accessing the embedding/vector store.
    
    Implement this with your Supabase pgvector adapter.
    The concrete implementation lives in:
      coherence/adapters/persistence/pgvector_embedding_repo.py
    """
    
    async def find_by_clause_id(
        self,
        clause_id: str,
        tenant_id: Optional[UUID] = None,
    ) -> Optional[EmbeddingRecord]:
        """Find embedding record for a clause."""
        ...
    
    async def find_similar(
        self,
        embedding_id: str,
        tenant_id: Optional[UUID] = None,
        threshold: float = 0.85,
        limit: int = 5,
        exclude_clause_ids: Optional[list[str]] = None,
    ) -> list[EmbeddingMatch]:
        """
        Find clauses with similar embeddings using pgvector cosine similarity.
        
        SQL equivalent:
          SELECT clause_id, 1 - (embedding <=> target_embedding) AS similarity
          FROM clause_embeddings
          WHERE tenant_id = :tenant_id
            AND clause_id NOT IN :exclude
            AND 1 - (embedding <=> target_embedding) > :threshold
          ORDER BY similarity DESC
          LIMIT :limit
        """
        ...
```

---

## 6. LLM Cost Comparison: Old vs New Architecture

| Scenario | Old (v0.2) | New: low_budget_mode | New: standard |
|----------|-----------|---------------------|---------------|
| 5 clauses, 5 rules | 25 LLM calls | **2** (1 batch + 1 cross) | 5-10 calls |
| 20 clauses, 5 rules | 100 LLM calls | **2** (1 batch + 1 cross) | 20-25 calls |
| 50 clauses, 5 rules | 250 LLM calls | **2** (1 batch + 1 cross) | 50-55 calls |

The RAG similarity node costs **zero LLM tokens** — it runs entirely as a PostgreSQL pgvector query, which is why it's so powerful as a pre-filter for the cross-clause LLM analysis.

---

## 7. Router Integration

```python
"""
coherence/router.py — FastAPI endpoint, unchanged public API.

Location: apps/api/src/coherence/router.py
"""

from fastapi import APIRouter, Depends
from coherence.graph.graph import coherence_subgraph
from coherence.graph.state import CoherenceGraphState, ClauseWithEmbedding
from coherence.models import ProjectContext, CoherenceResult


router = APIRouter(prefix="/v0/coherence", tags=["coherence"])


@router.post("/evaluate", response_model=CoherenceResult)
async def evaluate_coherence(context: ProjectContext):
    """
    POST /v0/coherence/evaluate — Public API (unchanged).
    
    Now internally routes through the LangGraph subgraph.
    """
    # Convert ProjectContext clauses to subgraph-compatible format
    graph_clauses = [
        ClauseWithEmbedding(
            clause_id=c.id,
            document_id=getattr(c, 'document_id', 'unknown'),
            text=c.text,
            data=c.data or {},
            category=_infer_category(c),
        )
        for c in context.clauses
    ]
    
    # Build initial state
    initial_state = CoherenceGraphState(
        project_id=context.id,
        clauses=graph_clauses,
        low_budget_mode=True,  # Default to cost-efficient
    )
    
    # Run the subgraph
    result = await coherence_subgraph.ainvoke(initial_state)
    
    # Return backward-compatible response
    return CoherenceResult(
        alerts=result["alerts"],
        score=result["score"],
    )


def _infer_category(clause) -> str:
    """Infer coherence category from clause data."""
    data = clause.data or {}
    text_lower = clause.text.lower()
    
    if any(k in data for k in ("budget", "current", "planned", "cost")):
        return "BUDGET"
    if any(k in data for k in ("status", "end_date", "deadline", "schedule")):
        return "TIME"
    if any(k in data for k in ("scope", "deliverables", "work_items")):
        return "SCOPE"
    if any(k in data for k in ("standard", "quality", "iso", "astm")):
        return "QUALITY"
    if any(k in data for k in ("termination", "liability", "indemnity", "review")):
        return "LEGAL"
    
    # Fallback to text-based heuristic
    if any(w in text_lower for w in ("budget", "cost", "price", "payment")):
        return "BUDGET"
    if any(w in text_lower for w in ("schedule", "deadline", "date", "timeline")):
        return "TIME"
    
    return "SCOPE"  # Default
```

---

## 8. File Placement Map

```
apps/api/src/
├── coherence/
│   ├── __init__.py
│   ├── models.py              # Add FindingSignal (backward compatible)
│   ├── ports.py               # NEW: EmbeddingRepositoryPort
│   ├── router.py              # UPDATED: routes through subgraph
│   ├── scoring.py             # REPLACED: exponential decay (from v0.3 doc)
│   ├── graph/                 # NEW: LangGraph subgraph
│   │   ├── __init__.py
│   │   ├── graph.py           # Subgraph definition + compilation
│   │   ├── state.py           # CoherenceGraphState dataclass
│   │   ├── nodes.py           # All node implementations
│   │   └── prompts.py         # Optimized LLM prompt templates
│   ├── adapters/
│   │   └── persistence/
│   │       └── pgvector_embedding_repo.py  # NEW: implements port
│   ├── rules_engine/          # Existing (still used by deterministic node)
│   │   ├── deterministic.py
│   │   ├── llm_evaluator.py   # UPDATED: continuous scoring
│   │   └── registry.py
│   └── config.py              # Add ScoringConfig
```

---

## 9. Implementation Order

1. **Week 1**: `state.py` + `ports.py` + `scoring.py` (v0.3 exponential decay)
2. **Week 2**: `nodes.py` (deterministic_evaluate + scoring_arbiter) — testable without LLM
3. **Week 3**: `graph.py` + `prompts.py` + `llm_semantic_evaluate` node
4. **Week 4**: `rag_similarity_check` node + `pgvector_embedding_repo.py` adapter
5. **Week 5**: `cross_clause_eval` node + router integration + E2E tests

Each week produces a working, testable increment. The subgraph compiles and runs from Week 2 onward (with stub nodes for phases not yet implemented).
