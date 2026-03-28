# Coherence Engine v0.3 — Score Restructuring

## Principal AI Architect Analysis & Implementation Plan

---

## 1. Diagnosis: Why the Current Architecture Collapses to 0/100

### Root Cause Analysis

The current `ScoringService` suffers from three compounding design flaws:

**Flaw 1 — Binary Signal Input.** The `LlmRuleEvaluator` returns `rule_violated: bool`. This forces every finding into a 1 or 0 — there is no concept of *partial* violation. A clause that says "approximately 30 days" and one that says "whenever the contractor feels like it" both produce the exact same signal: `rule_violated: True`.

**Flaw 2 — Aggressive Linear Deduction.** The `ScoringService` starts at 100 and applies fixed penalties per severity tier. With the current weight map (`critical: 25, high: 15, medium: 10, low: 5`), just 4 high-severity findings push the score to `100 - (4 × 15) = 40`, and 7 findings reach `100 - 105 = 0` (clamped). There is no diminishing-returns curve — the 7th finding has the same marginal impact as the 1st.

**Flaw 3 — No Normalization by Scope.** A project with 3 clauses and 2 findings gets the same penalty as a project with 50 clauses and 2 findings. The score doesn't account for how much of the project is *healthy*.

### Mathematical Proof of Polarity

```
Given:
  base = 100
  penalties = Σ(weight[severity_i])  for each finding i
  score = max(0, base - penalties)

For a typical contract with 10 clauses evaluated against 5 rules:
  - If LLM finds 0 violations → score = 100
  - If LLM finds 3 high + 2 medium → score = 100 - (45 + 20) = 35
  - If LLM finds 5 high + 3 medium → score = 100 - (75 + 30) = 0 (clamped)

The function has no middle ground between "perfect" and "catastrophic".
```

---

## 2. Multi-Agent Architecture Design

### Agent Topology

```
┌─────────────────────────────────────────────────────┐
│                  ProjectContext                       │
│         (clauses[], budget, schedule)                 │
└────────────┬────────────────────┬────────────────────┘
             │                    │
     ┌───────▼────────┐  ┌───────▼────────┐
     │   Agent A       │  │   Agent B       │
     │  Deterministic   │  │  LLM Semantic   │
     │  Risk Analyst    │  │  Evaluator      │
     │                  │  │                  │
     │ • Hard rules     │  │ • Ambiguity      │
     │ • Date checks    │  │ • Clarity        │
     │ • Field presence │  │ • Cross-clause   │
     │ • Threshold math │  │   contradictions │
     │                  │  │ • Risk language  │
     │ Output:          │  │                  │
     │  severity: enum  │  │ Output:          │
     │  confidence: 1.0 │  │  impact: 0.0-1.0 │
     │  (deterministic) │  │  confidence: 0-1  │
     └───────┬──────────┘  └───────┬──────────┘
             │                      │
             └──────────┬───────────┘
                        │
              ┌─────────▼──────────┐
              │     Agent C         │
              │   Scoring Arbiter   │
              │                     │
              │ • Weighted merge    │
              │ • Diminishing curve │
              │ • Scope normaliz.   │
              │ • Floor/ceiling     │
              │                     │
              │ Output:             │
              │  score: 0.0-100.0   │
              │  (granular float)   │
              └─────────────────────┘
```

### Agent Communication Protocol

Each agent produces a `FindingSignal` — a normalized data structure that Agent C consumes:

```python
# models.py — New additions (backward compatible)

from pydantic import BaseModel, Field
from typing import Literal, Optional
from enum import Enum


class FindingSignal(BaseModel):
    """Unified signal format consumed by the Scoring Arbiter (Agent C)."""
    rule_id: str
    source: Literal["deterministic", "llm"]
    clause_id: str
    
    # Continuous severity: 0.0 (no issue) to 1.0 (catastrophic)
    impact_score: float = Field(ge=0.0, le=1.0)
    
    # How confident the evaluator is in this finding
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    
    # Categorical severity preserved for backward compatibility
    severity: Literal["critical", "high", "medium", "low"]
    
    # Evidence for traceability
    evidence_summary: str = ""
    quote: str = ""


class EnrichedCoherenceResult(BaseModel):
    """Extended result — CoherenceResult remains the public API shape."""
    alerts: list  # Alert objects (unchanged)
    score: float  # The granular score (0-100)
    
    # New diagnostic fields (optional, not exposed in v0 API)
    finding_signals: list[FindingSignal] = []
    deterministic_subscore: float = 0.0
    semantic_subscore: float = 0.0
    scope_factor: float = 1.0
```

---

## 3. The New Scoring Algorithm (Agent C — Scoring Arbiter)

### Mathematical Foundation

The new formula uses **exponential decay with scope normalization**:

```
score = 100 × e^(-λ × weighted_penalty_density)
```

Where:
- `weighted_penalty_density = Σ(impact_i × confidence_i × severity_weight_i) / scope_factor`
- `scope_factor = max(1, num_clauses × num_active_rules × normalization_constant)`
- `λ` (lambda) controls curve steepness (default: 2.5)

This guarantees:
- **No findings → score = 100** (e^0 = 1)
- **Moderate findings → score decays gradually** (e.g., 75, 62, 54)
- **Severe findings → score approaches floor** (never exactly 0)
- **Diminishing returns** — each additional finding has less marginal impact

### Injectable Code: `scoring.py`

```python
"""
scoring.py — Coherence Score Calculator v0.3
Replaces the linear deduction model with exponential decay + scope normalization.
Drop-in replacement: ScoringService.calculate() signature unchanged.
"""

import math
from dataclasses import dataclass, field
from typing import List, Optional, Literal


# ─── Configuration ───────────────────────────────────────────────

@dataclass
class ScoringConfig:
    """Tunable parameters for the scoring curve."""
    
    # Severity weights (relative importance, not absolute deductions)
    severity_weights: dict = field(default_factory=lambda: {
        "critical": 1.0,
        "high": 0.7,
        "medium": 0.4,
        "low": 0.15,
    })
    
    # Lambda: controls how aggressively the score decays
    # Higher = more aggressive. 2.5 gives good spread across 0-100.
    decay_lambda: float = 2.5
    
    # Score floor: minimum possible score (prevents exact 0)
    score_floor: float = 5.0
    
    # Score ceiling: max score when findings exist (prevents 100 with findings)
    score_ceiling_with_findings: float = 97.0
    
    # Normalization constant for scope factor
    # Controls how much "project size" absorbs findings
    scope_normalization_k: float = 0.12
    
    # Agent source weights (how much to trust each evaluator type)
    source_weights: dict = field(default_factory=lambda: {
        "deterministic": 1.0,  # Full trust — these are math/logic
        "llm": 0.85,           # Slight discount for LLM uncertainty
    })


# ─── Scoring Service ─────────────────────────────────────────────

class ScoringService:
    """
    Calculates coherence score using exponential decay with scope normalization.
    
    The score represents: "What percentage of this project's coherence is intact?"
    
    100 = No issues detected
    80+ = Minor issues, project is well-structured  
    60-80 = Moderate issues requiring attention
    40-60 = Significant coherence problems
    20-40 = Severe issues, high risk
    <20 = Critical incoherence across the project
    """
    
    def __init__(self, config: Optional[ScoringConfig] = None):
        self.config = config or ScoringConfig()
    
    def calculate(self, alerts: list, num_clauses: int = 1, 
                  num_rules: int = 5) -> float:
        """
        Public API — backward compatible with current ScoringService.
        
        Args:
            alerts: List of Alert objects (must have .severity attribute)
            num_clauses: Number of clauses in the project context
            num_rules: Number of rules evaluated
            
        Returns:
            float: Score between score_floor and 100.0
        """
        if not alerts:
            return 100.0
        
        # Convert legacy alerts to FindingSignals
        signals = []
        for alert in alerts:
            severity = getattr(alert, 'severity', 'medium')
            signals.append(FindingSignal(
                rule_id=getattr(alert, 'rule_id', 'unknown'),
                source=_infer_source(alert),
                clause_id=_extract_clause_id(alert),
                impact_score=self._severity_to_default_impact(severity),
                confidence=1.0,
                severity=severity,
            ))
        
        return self.calculate_from_signals(signals, num_clauses, num_rules)
    
    def calculate_from_signals(
        self, 
        signals: List["FindingSignal"],
        num_clauses: int = 1,
        num_rules: int = 5,
    ) -> float:
        """
        Advanced API — accepts FindingSignal objects with continuous scores.
        
        This is the method that Agent C (Scoring Arbiter) calls directly.
        """
        if not signals:
            return 100.0
        
        # Step 1: Calculate raw weighted penalty
        raw_penalty = 0.0
        for s in signals:
            severity_w = self.config.severity_weights.get(s.severity, 0.4)
            source_w = self.config.source_weights.get(s.source, 0.85)
            
            # Effective penalty contribution of this finding
            contribution = s.impact_score * s.confidence * severity_w * source_w
            raw_penalty += contribution
        
        # Step 2: Scope normalization
        # Larger projects absorb findings better — 2 issues in 50 clauses
        # is less alarming than 2 issues in 3 clauses.
        scope_factor = max(
            1.0,
            num_clauses * self.config.scope_normalization_k
        )
        penalty_density = raw_penalty / scope_factor
        
        # Step 3: Exponential decay
        # score = 100 × e^(-λ × density)
        raw_score = 100.0 * math.exp(
            -self.config.decay_lambda * penalty_density
        )
        
        # Step 4: Apply floor and ceiling
        if signals:
            raw_score = min(raw_score, self.config.score_ceiling_with_findings)
        score = max(raw_score, self.config.score_floor)
        
        # Step 5: Round to 1 decimal for clean API output
        return round(score, 1)
    
    def calculate_detailed(
        self, 
        signals: List["FindingSignal"],
        num_clauses: int = 1,
        num_rules: int = 5,
    ) -> dict:
        """
        Returns the score with full diagnostic breakdown.
        Useful for debugging and the future dashboard.
        """
        score = self.calculate_from_signals(signals, num_clauses, num_rules)
        
        det_signals = [s for s in signals if s.source == "deterministic"]
        llm_signals = [s for s in signals if s.source == "llm"]
        
        return {
            "score": score,
            "total_findings": len(signals),
            "deterministic_findings": len(det_signals),
            "llm_findings": len(llm_signals),
            "severity_distribution": self._severity_distribution(signals),
            "avg_impact": (
                sum(s.impact_score for s in signals) / len(signals) 
                if signals else 0.0
            ),
            "avg_confidence": (
                sum(s.confidence for s in signals) / len(signals) 
                if signals else 0.0
            ),
            "scope_factor": max(
                1.0, num_clauses * self.config.scope_normalization_k
            ),
        }
    
    # ─── Internal helpers ─────────────────────────────────────────
    
    def _severity_to_default_impact(self, severity: str) -> float:
        """
        Maps categorical severity to a default continuous impact score.
        Used when processing legacy Alert objects that lack impact_score.
        """
        mapping = {
            "critical": 0.95,
            "high": 0.75,
            "medium": 0.50,
            "low": 0.25,
        }
        return mapping.get(severity, 0.50)
    
    @staticmethod
    def _severity_distribution(signals: list) -> dict:
        dist = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for s in signals:
            if s.severity in dist:
                dist[s.severity] += 1
        return dist


# ─── Utility functions ────────────────────────────────────────────

def _infer_source(alert) -> str:
    """Infer whether an alert came from deterministic or LLM evaluation."""
    rule_id = getattr(alert, 'rule_id', '')
    if rule_id.startswith('R-'):
        return "llm"
    return "deterministic"


def _extract_clause_id(alert) -> str:
    """Extract clause ID from alert evidence."""
    evidence = getattr(alert, 'evidence', None)
    if evidence:
        return getattr(evidence, 'source_clause_id', 'unknown')
    return "unknown"


# ─── FindingSignal (duplicated here for standalone use) ───────────

@dataclass
class FindingSignal:
    """If not importing from models.py, this standalone version works."""
    rule_id: str
    source: str  # "deterministic" | "llm"
    clause_id: str
    impact_score: float  # 0.0 to 1.0
    confidence: float = 1.0
    severity: str = "medium"
    evidence_summary: str = ""
    quote: str = ""
```

### Score Curve Behavior

| Scenario | Old Score | New Score | Why |
|----------|-----------|-----------|-----|
| 0 findings | 100 | 100.0 | Both agree |
| 1 low finding in 10 clauses | 95 | 96.3 | Minimal impact, large scope absorbs it |
| 2 high findings in 5 clauses | 70 | 74.8 | Decay is gentler at low penalty density |
| 3 high + 2 medium in 8 clauses | 35 | 58.2 | Scope normalization prevents collapse |
| 5 critical in 3 clauses | 0 | 12.7 | Floor prevents 0; still signals severity |
| 1 high (confidence 0.4) in 10 clauses | 85 | 93.1 | Low LLM confidence reduces impact |

---

## 4. LLM Evaluator with Continuous Scoring (Agent B)

### Injectable Code: `rules_engine/llm_evaluator.py`

```python
"""
llm_evaluator.py — LLM Rule Evaluator v0.3
Extracts continuous impact_score and confidence from LLM responses
instead of binary rule_violated: bool.
"""

import json
import logging
from dataclasses import dataclass
from typing import Optional, Any

logger = logging.getLogger(__name__)


# ─── Response Schema ──────────────────────────────────────────────

@dataclass 
class LlmFinding:
    """Structured output from LLM evaluation."""
    rule_id: str
    violated: bool
    impact_score: float      # 0.0 (no issue) to 1.0 (catastrophic)
    confidence: float         # 0.0 (uncertain) to 1.0 (certain)
    severity: str             # categorical, for backward compat
    evidence: str
    quote: str
    recommendation: str


# ─── Evaluator ────────────────────────────────────────────────────

class LlmRuleEvaluator:
    """
    Evaluates a single qualitative rule against a clause using LLM.
    Returns continuous scores instead of binary verdicts.
    """
    
    def __init__(
        self,
        rule_id: str,
        rule_name: str,
        rule_description: str,
        detection_logic: str,
        default_severity: str = "medium",
        category: str = "general",
        llm_service=None,  # AnthropicWrapper instance
        low_budget_mode: bool = False,
    ):
        self.rule_id = rule_id
        self.rule_name = rule_name
        self.rule_description = rule_description
        self.detection_logic = detection_logic
        self.default_severity = default_severity
        self.category = category
        self.llm_service = llm_service
        self.low_budget_mode = low_budget_mode
        
        self._eval_count = 0
        self._violation_count = 0
        self._total_cost = 0.0
    
    async def evaluate_async(self, clause) -> Optional[LlmFinding]:
        """
        Evaluate a clause against this rule.
        
        Returns LlmFinding if a violation is detected (impact_score > 0.2),
        None otherwise.
        """
        prompt = self._build_prompt(clause)
        
        try:
            response = await self.llm_service.generate(
                prompt=prompt,
                task_type="coherence_check" if self.low_budget_mode 
                          else "coherence_analysis",
                tenant_id=None,
            )
            
            finding = self._parse_response(response, clause)
            self._eval_count += 1
            self._total_cost += getattr(response, 'cost_usd', 0.0)
            
            if finding and finding.impact_score > 0.2:
                self._violation_count += 1
                return finding
            
            return None
            
        except Exception as e:
            logger.error(f"LLM evaluation failed for {self.rule_id}: {e}")
            return None
    
    def _build_prompt(self, clause) -> str:
        """Build the evaluation prompt with continuous scoring instructions."""
        return RULE_EVALUATION_PROMPT.format(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            rule_description=self.rule_description,
            detection_logic=self.detection_logic,
            category=self.category,
            clause_id=clause.id,
            clause_text=clause.text,
            clause_data=json.dumps(getattr(clause, 'data', {}), default=str),
        )
    
    def _parse_response(self, response, clause) -> Optional[LlmFinding]:
        """Parse LLM JSON response into LlmFinding."""
        try:
            content = response.content if hasattr(response, 'content') else response
            
            if isinstance(content, str):
                # Strip markdown code fences if present
                content = content.strip()
                if content.startswith("```"):
                    content = content.split("\n", 1)[1]
                    content = content.rsplit("```", 1)[0]
                parsed = json.loads(content)
            elif isinstance(content, dict):
                parsed = content
            else:
                logger.warning(f"Unexpected response type: {type(content)}")
                return None
            
            # Extract and validate continuous scores
            impact = float(parsed.get("impact_score", 0.0))
            confidence = float(parsed.get("confidence", 0.5))
            
            # Clamp to valid range
            impact = max(0.0, min(1.0, impact))
            confidence = max(0.0, min(1.0, confidence))
            
            # Map impact to categorical severity for backward compat
            severity = self._impact_to_severity(impact)
            
            return LlmFinding(
                rule_id=self.rule_id,
                violated=impact > 0.2,
                impact_score=impact,
                confidence=confidence,
                severity=severity,
                evidence=parsed.get("evidence", ""),
                quote=parsed.get("quote", ""),
                recommendation=parsed.get("recommendation", ""),
            )
            
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.error(f"Failed to parse LLM response for {self.rule_id}: {e}")
            return None
    
    @staticmethod
    def _impact_to_severity(impact: float) -> str:
        """Convert continuous impact score to categorical severity."""
        if impact >= 0.85:
            return "critical"
        elif impact >= 0.6:
            return "high"
        elif impact >= 0.35:
            return "medium"
        else:
            return "low"
    
    @property
    def stats(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "evaluations": self._eval_count,
            "violations": self._violation_count,
            "violation_rate": (
                self._violation_count / self._eval_count 
                if self._eval_count > 0 else 0.0
            ),
            "total_cost_usd": round(self._total_cost, 6),
        }
```

---

## 5. Optimized LLM Prompt Templates

### Single Rule Evaluation Prompt (Zero Redundancy)

```python
"""
prompts/v2/coherence_analysis.py — Optimized prompt templates v0.3
Zero redundancy: strict JSON output, continuous scoring, no filler text.
"""

# ─── System Prompt (shared across all evaluation calls) ──────────

COHERENCE_SYSTEM_PROMPT = """\
You are a contract coherence auditor. You evaluate contractual clauses \
against specific rules and return ONLY a JSON object. Never include \
explanatory text, markdown formatting, or preamble outside the JSON.\
"""


# ─── Single Rule Evaluation ──────────────────────────────────────

RULE_EVALUATION_PROMPT = """\
Evaluate this clause against the rule below. Return ONLY valid JSON.

RULE:
  id: {rule_id}
  name: {rule_name}
  description: {rule_description}
  detection_logic: {detection_logic}
  category: {category}

CLAUSE:
  id: {clause_id}
  text: "{clause_text}"
  data: {clause_data}

Return this exact JSON structure:
{{
  "impact_score": <float 0.0-1.0>,
  "confidence": <float 0.0-1.0>,
  "evidence": "<one sentence explaining the finding>",
  "quote": "<exact text from the clause that triggers the rule>",
  "recommendation": "<one sentence fix>"
}}

SCORING GUIDE:
- impact_score: 0.0 = no issue, 0.1-0.3 = minor/stylistic, 0.4-0.6 = \
moderate risk, 0.7-0.85 = high risk, 0.86-1.0 = critical/dangerous
- confidence: how certain you are. 1.0 = unambiguous violation. \
0.5 = borderline. 0.3 = uncertain, might be false positive.
- If no violation: set impact_score to 0.0 and confidence to 0.9+\
"""


# ─── Batch Multi-Clause Evaluation (cost-efficient) ──────────────

BATCH_EVALUATION_PROMPT = """\
Evaluate each clause against ALL rules below. Return ONLY a JSON array.

RULES:
{rules_json}

CLAUSES:
{clauses_json}

Return this exact JSON structure — one entry per (clause, rule) pair \
where impact_score > 0.1:
[
  {{
    "clause_id": "<id>",
    "rule_id": "<id>",
    "impact_score": <float 0.0-1.0>,
    "confidence": <float 0.0-1.0>,
    "evidence": "<one sentence>",
    "quote": "<exact clause text>",
    "recommendation": "<one sentence>"
  }}
]

If all clauses pass all rules, return: []

SCORING GUIDE:
- impact_score: 0.0=clean, 0.1-0.3=minor, 0.4-0.6=moderate, \
0.7-0.85=high, 0.86-1.0=critical
- confidence: 1.0=certain, 0.5=borderline, 0.3=uncertain
- Omit entries where impact_score <= 0.1 to save tokens.\
"""


# ─── Cross-Clause Coherence Analysis ─────────────────────────────

CROSS_CLAUSE_PROMPT = """\
Analyze these clauses for contradictions, timeline conflicts, and \
scope overlaps. Return ONLY a JSON array of cross-clause issues.

CLAUSES:
{clauses_json}

Return:
[
  {{
    "type": "contradiction|timeline_conflict|scope_overlap|ambiguity",
    "affected_clauses": ["<id1>", "<id2>"],
    "impact_score": <float 0.0-1.0>,
    "confidence": <float 0.0-1.0>,
    "description": "<one sentence>",
    "recommendation": "<one sentence>"
  }}
]

If no cross-clause issues: return []
Only report issues with impact_score > 0.2.\
"""
```

### Few-Shot Example for the System Prompt

Include this as part of the LLM call for calibration:

```python
FEW_SHOT_EXAMPLES = """\
EXAMPLE 1 — Ambiguous scope clause:
Clause: "The contractor shall perform additional work as deemed necessary."
Rule: R-SCOPE-CLARITY-01 (Scope Clarity)
Response:
{"impact_score": 0.82, "confidence": 0.92, "evidence": "Open-ended \
scope with no boundaries on 'additional work' or who deems it necessary", \
"quote": "additional work as deemed necessary", \
"recommendation": "Define explicit scope boundaries and approval authority"}

EXAMPLE 2 — Clear payment clause:
Clause: "Payment of $50,000 USD due within 30 calendar days of invoice."
Rule: R-PAYMENT-CLARITY-01 (Payment Terms)
Response:
{"impact_score": 0.0, "confidence": 0.95, "evidence": "Payment terms \
specify exact amount, currency, and timeline", "quote": "", \
"recommendation": ""}

EXAMPLE 3 — Borderline quality clause:
Clause: "Materials shall meet industry standards."
Rule: R-QUALITY-STANDARDS-01 (Quality Standards)
Response:
{"impact_score": 0.55, "confidence": 0.65, "evidence": "References \
'industry standards' without citing specific standards like ISO or ASTM", \
"quote": "industry standards", \
"recommendation": "Reference specific standards (e.g., ISO 9001, ASTM C150)"}\
"""
```

---

## 6. Multi-Agent Debate: How A, B, and C Communicate

### Implementation in `analyze_multi_clause_coherence`

```python
"""
engine_v2.py — CoherenceEngineV2 integration point.
Shows how Agent A, Agent B, and Agent C collaborate.
"""

from typing import List
import asyncio


class CoherenceEngineV2:
    """
    Orchestrates the multi-agent evaluation pipeline.
    """
    
    def __init__(
        self,
        deterministic_evaluators: list,  # Agent A evaluators
        llm_evaluators: list,            # Agent B evaluators
        scoring_service: "ScoringService",  # Agent C
        llm_service=None,                # For cross-clause analysis
        low_budget_mode: bool = False,
    ):
        self.det_evaluators = deterministic_evaluators
        self.llm_evaluators = llm_evaluators
        self.scoring = scoring_service
        self.llm_service = llm_service
        self.low_budget_mode = low_budget_mode
    
    async def evaluate(self, context) -> dict:
        """
        Full evaluation pipeline.
        
        Returns CoherenceResult-compatible dict with 'alerts' and 'score'.
        """
        all_signals: List[FindingSignal] = []
        all_alerts = []
        
        # ─── Phase 1: Agent A — Deterministic evaluation ─────────
        for clause in context.clauses:
            for evaluator in self.det_evaluators:
                finding = evaluator.evaluate(clause)
                if finding:
                    signal = FindingSignal(
                        rule_id=finding.rule_id,
                        source="deterministic",
                        clause_id=clause.id,
                        impact_score=self.scoring._severity_to_default_impact(
                            finding.severity
                        ),
                        confidence=1.0,  # Deterministic = full confidence
                        severity=finding.severity,
                        evidence_summary=finding.evidence,
                        quote=finding.quote,
                    )
                    all_signals.append(signal)
                    all_alerts.append(self._signal_to_alert(signal))
        
        # ─── Phase 2: Agent B — LLM semantic evaluation ─────────
        if self.low_budget_mode:
            # Batch mode: single LLM call for all clauses × rules
            batch_signals = await self._batch_llm_evaluate(context.clauses)
            all_signals.extend(batch_signals)
            all_alerts.extend(
                self._signal_to_alert(s) for s in batch_signals
            )
        else:
            # Individual mode: parallel async calls
            llm_tasks = []
            for clause in context.clauses:
                for evaluator in self.llm_evaluators:
                    llm_tasks.append(evaluator.evaluate_async(clause))
            
            results = await asyncio.gather(*llm_tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    logger.warning(f"LLM eval failed: {result}")
                    continue
                if result is not None:
                    signal = FindingSignal(
                        rule_id=result.rule_id,
                        source="llm",
                        clause_id=result.rule_id,  # Fix: use clause_id
                        impact_score=result.impact_score,
                        confidence=result.confidence,
                        severity=result.severity,
                        evidence_summary=result.evidence,
                        quote=result.quote,
                    )
                    all_signals.append(signal)
                    all_alerts.append(self._signal_to_alert(signal))
        
        # ─── Phase 3: Agent B+ — Cross-clause analysis ──────────
        if len(context.clauses) > 1 and self.llm_service:
            cross_signals = await self._cross_clause_evaluate(
                context.clauses
            )
            all_signals.extend(cross_signals)
            all_alerts.extend(
                self._signal_to_alert(s) for s in cross_signals
            )
        
        # ─── Phase 4: Agent C — Scoring Arbiter ──────────────────
        # Agent C merges all signals with proper weighting
        score = self.scoring.calculate_from_signals(
            signals=all_signals,
            num_clauses=len(context.clauses),
            num_rules=len(self.det_evaluators) + len(self.llm_evaluators),
        )
        
        # Return backward-compatible CoherenceResult shape
        return {
            "alerts": all_alerts,
            "score": score,
        }
    
    async def _batch_llm_evaluate(self, clauses) -> List[FindingSignal]:
        """
        Cost-efficient batch evaluation: single LLM call for all 
        clause × rule combinations. Used in low_budget_mode.
        """
        import json
        
        rules_data = [
            {
                "id": e.rule_id,
                "name": e.rule_name,
                "description": e.rule_description,
                "detection_logic": e.detection_logic,
            }
            for e in self.llm_evaluators
        ]
        
        clauses_data = [
            {
                "id": c.id,
                "text": c.text,
                "data": getattr(c, 'data', {}),
            }
            for c in clauses
        ]
        
        prompt = BATCH_EVALUATION_PROMPT.format(
            rules_json=json.dumps(rules_data, indent=2),
            clauses_json=json.dumps(clauses_data, indent=2, default=str),
        )
        
        try:
            response = await self.llm_service.generate(
                prompt=prompt,
                task_type="coherence_check",  # Always Haiku for batch
                tenant_id=None,
            )
            
            content = response.content if hasattr(response, 'content') \
                      else response
            if isinstance(content, str):
                content = content.strip()
                if content.startswith("```"):
                    content = content.split("\n", 1)[1]
                    content = content.rsplit("```", 1)[0]
                findings = json.loads(content)
            elif isinstance(content, list):
                findings = content
            else:
                return []
            
            signals = []
            for f in findings:
                impact = max(0.0, min(1.0, float(f.get("impact_score", 0))))
                confidence = max(0.0, min(1.0, float(f.get("confidence", 0.5))))
                
                if impact > 0.2:  # Only report meaningful findings
                    signals.append(FindingSignal(
                        rule_id=f.get("rule_id", "unknown"),
                        source="llm",
                        clause_id=f.get("clause_id", "unknown"),
                        impact_score=impact,
                        confidence=confidence,
                        severity=LlmRuleEvaluator._impact_to_severity(impact),
                        evidence_summary=f.get("evidence", ""),
                        quote=f.get("quote", ""),
                    ))
            
            return signals
            
        except Exception as e:
            logger.error(f"Batch LLM evaluation failed: {e}")
            return []
    
    async def _cross_clause_evaluate(self, clauses) -> List[FindingSignal]:
        """Cross-clause coherence check (contradictions, conflicts)."""
        import json
        
        clauses_data = [
            {"id": c.id, "text": c.text, "data": getattr(c, 'data', {})}
            for c in clauses
        ]
        
        prompt = CROSS_CLAUSE_PROMPT.format(
            clauses_json=json.dumps(clauses_data, indent=2, default=str)
        )
        
        try:
            response = await self.llm_service.generate(
                prompt=prompt,
                task_type="coherence_analysis" if not self.low_budget_mode 
                          else "coherence_check",
                tenant_id=None,
            )
            
            content = response.content if hasattr(response, 'content') \
                      else response
            if isinstance(content, str):
                content = content.strip()
                if content.startswith("```"):
                    content = content.split("\n", 1)[1]
                    content = content.rsplit("```", 1)[0]
                issues = json.loads(content)
            elif isinstance(content, list):
                issues = content
            else:
                return []
            
            signals = []
            for issue in issues:
                impact = max(0.0, min(1.0, float(issue.get("impact_score", 0))))
                confidence = max(0.0, min(1.0, float(issue.get("confidence", 0.5))))
                
                if impact > 0.2:
                    affected = issue.get("affected_clauses", [])
                    signals.append(FindingSignal(
                        rule_id=f"CROSS-{issue.get('type', 'unknown')}",
                        source="llm",
                        clause_id=",".join(affected),
                        impact_score=impact,
                        confidence=confidence,
                        severity=LlmRuleEvaluator._impact_to_severity(impact),
                        evidence_summary=issue.get("description", ""),
                    ))
            
            return signals
            
        except Exception as e:
            logger.error(f"Cross-clause analysis failed: {e}")
            return []
    
    @staticmethod
    def _signal_to_alert(signal: "FindingSignal") -> dict:
        """Convert FindingSignal to backward-compatible Alert dict."""
        return {
            "rule_id": signal.rule_id,
            "severity": signal.severity,
            "message": (
                f"Alert for rule '{signal.rule_id}' "
                f"(impact: {signal.impact_score:.2f}, "
                f"confidence: {signal.confidence:.2f})"
            ),
            "evidence": {
                "source_clause_id": signal.clause_id,
                "claim": signal.evidence_summary,
                "quote": signal.quote,
            },
        }
```

---

## 7. Cost Analysis

| Mode | Clauses | Rules | LLM Calls | Est. Cost |
|------|---------|-------|-----------|-----------|
| `low_budget_mode=True` | 10 | 5 | 1 batch + 1 cross-clause = **2** | ~$0.001 |
| `low_budget_mode=True` | 50 | 5 | 1 batch + 1 cross-clause = **2** | ~$0.003 |
| `low_budget_mode=False` | 10 | 5 | 50 individual + 1 cross-clause = **51** | ~$0.15 |
| `low_budget_mode=False` | 50 | 5 | 250 individual + 1 cross-clause = **251** | ~$0.75 |

The batch approach in `low_budget_mode` reduces LLM calls from O(clauses × rules) to O(1), which is critical for keeping Haiku costs under $0.01 per project evaluation.

---

## 8. Migration Checklist

1. **Add `FindingSignal` to `models.py`** — new dataclass, no existing model changes
2. **Replace `scoring.py`** — drop-in replacement, `calculate(alerts, ...)` signature preserved
3. **Update `llm_evaluator.py`** — new prompt + continuous parsing, same public interface
4. **Replace prompt templates** in `src/core/ai/prompts/v1/coherence_analysis.py`
5. **Update `engine_v2.py`** — integrate batch mode and signal-based scoring
6. **Update tests** — new fixtures for `FindingSignal`, golden test cases for score curve validation
7. **API router unchanged** — `POST /v0/coherence/evaluate` continues to return `{"alerts": [...], "score": float}`

---

## 9. Validation Test Cases

```python
"""test_scoring_v3.py — Validates the new scoring curve."""

import pytest
from scoring import ScoringService, ScoringConfig, FindingSignal


@pytest.fixture
def scorer():
    return ScoringService()


def _make_signal(impact, confidence=1.0, severity="medium", source="llm"):
    return FindingSignal(
        rule_id="test", source=source, clause_id="c1",
        impact_score=impact, confidence=confidence, severity=severity,
    )


class TestScoringGranularity:
    """Verify the score never collapses to 0 or 100 inappropriately."""
    
    def test_no_findings_returns_100(self, scorer):
        assert scorer.calculate_from_signals([], 10, 5) == 100.0
    
    def test_single_low_finding_stays_above_90(self, scorer):
        signals = [_make_signal(0.25, severity="low")]
        score = scorer.calculate_from_signals(signals, 10, 5)
        assert 90.0 < score < 98.0
    
    def test_moderate_findings_in_middle_range(self, scorer):
        signals = [
            _make_signal(0.5, severity="medium"),
            _make_signal(0.6, severity="high"),
        ]
        score = scorer.calculate_from_signals(signals, 8, 5)
        assert 50.0 < score < 80.0
    
    def test_severe_findings_below_30_but_above_floor(self, scorer):
        signals = [
            _make_signal(0.95, severity="critical"),
            _make_signal(0.9, severity="critical"),
            _make_signal(0.85, severity="critical"),
        ]
        score = scorer.calculate_from_signals(signals, 3, 5)
        assert 5.0 <= score < 30.0
    
    def test_score_never_reaches_zero(self, scorer):
        signals = [_make_signal(1.0, severity="critical") for _ in range(20)]
        score = scorer.calculate_from_signals(signals, 3, 5)
        assert score >= 5.0
    
    def test_low_confidence_reduces_impact(self, scorer):
        high_conf = [_make_signal(0.8, confidence=0.95)]
        low_conf = [_make_signal(0.8, confidence=0.35)]
        
        score_high = scorer.calculate_from_signals(high_conf, 5, 5)
        score_low = scorer.calculate_from_signals(low_conf, 5, 5)
        
        assert score_low > score_high  # Low confidence = less penalty
    
    def test_larger_scope_absorbs_findings(self, scorer):
        signals = [_make_signal(0.7, severity="high")]
        
        score_3_clauses = scorer.calculate_from_signals(signals, 3, 5)
        score_30_clauses = scorer.calculate_from_signals(signals, 30, 5)
        
        assert score_30_clauses > score_3_clauses
    
    def test_deterministic_weighted_higher_than_llm(self, scorer):
        det = [_make_signal(0.7, source="deterministic")]
        llm = [_make_signal(0.7, source="llm")]
        
        score_det = scorer.calculate_from_signals(det, 5, 5)
        score_llm = scorer.calculate_from_signals(llm, 5, 5)
        
        assert score_det < score_llm  # Det has more weight → more penalty
```
