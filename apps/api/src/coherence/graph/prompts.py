"""
prompts.py — Optimized LLM Prompt Templates for Coherence Engine v0.3

Provides structured prompts for:
- Single rule evaluation with continuous scoring
- Batch evaluation (multiple rules per clause)
- Cross-clause analysis

All prompts request continuous impact_score (0.0-1.0) instead of binary pass/fail.

Location: apps/api/src/coherence/graph/prompts.py
"""

from __future__ import annotations

from typing import Any

# =============================================================================
# SYSTEM PROMPT
# =============================================================================

COHERENCE_SYSTEM_PROMPT = """You are an expert contract coherence analyzer for C2Pro.

Your role is to evaluate contract clauses against specific coherence rules and
provide CONTINUOUS IMPACT SCORES (0.0 to 1.0) instead of binary pass/fail judgments.

SCORING GUIDELINES:
- 0.0: No issue detected - clause fully complies with the rule
- 0.1-0.3: Minor issue - cosmetic or stylistic concern, low risk
- 0.4-0.6: Moderate issue - should be addressed, potential for misunderstanding
- 0.7-0.8: Significant issue - high risk, could cause disputes
- 0.9-1.0: Critical issue - severe violation, likely to cause legal/financial harm

CONFIDENCE GUIDELINES:
- 1.0: Absolutely certain (clear textual evidence)
- 0.8-0.9: Very confident (strong indicators present)
- 0.6-0.7: Moderately confident (some ambiguity)
- 0.4-0.5: Low confidence (significant uncertainty)
- <0.4: Very uncertain (insufficient information)

OUTPUT FORMAT: Always respond with valid JSON only. No markdown, no explanations outside JSON.
"""

# =============================================================================
# SINGLE RULE EVALUATION PROMPT
# =============================================================================

RULE_EVALUATION_PROMPT = """Evaluate the following clause against the specified rule.

RULE: {rule_name}
RULE ID: {rule_id}
CATEGORY: {category}
DESCRIPTION: {rule_description}

DETECTION LOGIC:
{detection_logic}

CLAUSE TO EVALUATE:
ID: {clause_id}
TEXT:
\"\"\"
{clause_text}
\"\"\"

{structured_data}

Analyze and respond with JSON:
```json
{{
    "impact_score": <float 0.0-1.0>,
    "confidence": <float 0.0-1.0>,
    "rule_violated": <boolean>,
    "evidence": {{
        "quote": "<exact text from clause that triggers the finding>",
        "explanation": "<why this constitutes a violation or concern>"
    }},
    "recommendation": "<specific action to remediate, if applicable>"
}}
```

IMPORTANT:
- impact_score should reflect SEVERITY, not just presence of issue
- Provide the exact quote from the clause text as evidence
- Be conservative: only flag clear violations with high impact_score
"""

# =============================================================================
# BATCH EVALUATION PROMPT (Multiple Rules)
# =============================================================================

BATCH_EVALUATION_PROMPT = """Evaluate the following clause against ALL specified rules in a single pass.

CLAUSE TO EVALUATE:
ID: {clause_id}
TEXT:
\"\"\"
{clause_text}
\"\"\"

{structured_data}

RULES TO CHECK:
{rules_list}

Respond with a JSON array containing one object per rule that has findings.
Only include rules where impact_score > 0:

```json
{{
    "findings": [
        {{
            "rule_id": "<rule ID>",
            "impact_score": <float 0.0-1.0>,
            "confidence": <float 0.0-1.0>,
            "evidence": {{
                "quote": "<exact text>",
                "explanation": "<reason>"
            }},
            "recommendation": "<fix>"
        }}
    ],
    "clause_id": "{clause_id}",
    "rules_checked": <number of rules evaluated>
}}
```

If no issues found, return: {{"findings": [], "clause_id": "{clause_id}", "rules_checked": <n>}}
"""

# =============================================================================
# CROSS-CLAUSE ANALYSIS PROMPT
# =============================================================================

CROSS_CLAUSE_PROMPT = """Analyze the relationship between the following clauses for coherence issues.

This is a CROSS-CLAUSE analysis looking for:
- Contradictions between clauses
- Inconsistent terminology or definitions
- Conflicting obligations or timelines
- Missing cross-references
- Scope gaps between related clauses

CLAUSE A:
ID: {clause_a_id}
CATEGORY: {clause_a_category}
TEXT:
\"\"\"
{clause_a_text}
\"\"\"

CLAUSE B:
ID: {clause_b_id}
CATEGORY: {clause_b_category}
TEXT:
\"\"\"
{clause_b_text}
\"\"\"

CONTEXT: {cross_context}

Respond with JSON:
```json
{{
    "cross_findings": [
        {{
            "rule_id": "CROSS-<type>",
            "impact_score": <float 0.0-1.0>,
            "confidence": <float 0.0-1.0>,
            "affected_clauses": ["{clause_a_id}", "{clause_b_id}"],
            "issue_type": "<contradiction|inconsistency|gap|missing_reference>",
            "evidence": {{
                "quote_a": "<relevant text from clause A>",
                "quote_b": "<relevant text from clause B>",
                "explanation": "<why these are incoherent>"
            }},
            "recommendation": "<how to resolve>"
        }}
    ]
}}
```

If clauses are coherent, return: {{"cross_findings": []}}
"""

# =============================================================================
# FEW-SHOT EXAMPLES FOR CALIBRATION
# =============================================================================

FEW_SHOT_EXAMPLES: dict[str, dict[str, Any]] = {
    "scope_ambiguity": {
        "clause": """The Contractor shall perform all work necessary to complete the project
as described herein, including any additional work that may be required.""",
        "rule": "Scope Clarity Check",
        "expected_response": {
            "impact_score": 0.75,
            "confidence": 0.90,
            "rule_violated": True,
            "evidence": {
                "quote": "including any additional work that may be required",
                "explanation": "Open-ended scope creates risk of disputes over what is included"
            },
            "recommendation": "Define specific deliverables and establish change order process"
        }
    },
    "payment_terms_clear": {
        "clause": """Payment of $50,000 USD shall be made within 30 calendar days of invoice
receipt, via wire transfer to the account specified in Exhibit B.""",
        "rule": "Payment Terms Clarity",
        "expected_response": {
            "impact_score": 0.0,
            "confidence": 0.95,
            "rule_violated": False,
            "evidence": {
                "quote": "",
                "explanation": "Payment amount, timeline, currency, and method are all clearly specified"
            },
            "recommendation": ""
        }
    },
    "budget_overrun_severe": {
        "clause": """Current project expenditure: $2,450,000. Approved budget: $1,500,000.
Variance: $950,000 (63% overrun).""",
        "rule": "Budget Overrun Detection",
        "expected_response": {
            "impact_score": 0.95,
            "confidence": 1.0,
            "rule_violated": True,
            "evidence": {
                "quote": "Variance: $950,000 (63% overrun)",
                "explanation": "63% budget overrun far exceeds acceptable thresholds"
            },
            "recommendation": "Immediate executive review required; implement cost controls"
        }
    },
    "schedule_minor_delay": {
        "clause": """Task: Foundation Work. Planned completion: 2024-03-15.
Actual completion: 2024-03-18. Status: Completed (3 days late).""",
        "rule": "Schedule Adherence",
        "expected_response": {
            "impact_score": 0.25,
            "confidence": 0.95,
            "rule_violated": True,
            "evidence": {
                "quote": "3 days late",
                "explanation": "Minor delay of 3 days; evaluate impact on dependent tasks"
            },
            "recommendation": "Review schedule for downstream impact; adjust if needed"
        }
    },
    "legal_notice_missing": {
        "clause": """Either party may terminate this agreement for convenience upon
written notice to the other party.""",
        "rule": "Notice Period Requirements",
        "expected_response": {
            "impact_score": 0.70,
            "confidence": 0.85,
            "rule_violated": True,
            "evidence": {
                "quote": "upon written notice",
                "explanation": "No specific notice period defined; could allow immediate termination"
            },
            "recommendation": "Specify notice period (e.g., '30 calendar days prior written notice')"
        }
    }
}

# =============================================================================
# PROMPT BUILDERS
# =============================================================================


def build_evaluation_prompt(
    rule_id: str,
    rule_name: str,
    rule_description: str,
    detection_logic: str,
    category: str,
    clause_id: str,
    clause_text: str,
    clause_data: dict[str, Any] | None = None,
) -> str:
    """
    Build a complete evaluation prompt from components.

    Args:
        rule_id: Unique rule identifier
        rule_name: Human-readable rule name
        rule_description: What the rule checks
        detection_logic: How to detect violations
        category: Rule category (BUDGET, TIME, LEGAL, etc.)
        clause_id: ID of clause being evaluated
        clause_text: Text content of the clause
        clause_data: Optional structured data dict

    Returns:
        Formatted prompt string
    """
    structured_data = ""
    if clause_data:
        import json
        structured_data = f"\nSTRUCTURED DATA:\n{json.dumps(clause_data, indent=2, ensure_ascii=False)}"

    return RULE_EVALUATION_PROMPT.format(
        rule_id=rule_id,
        rule_name=rule_name,
        rule_description=rule_description,
        detection_logic=detection_logic,
        category=category,
        clause_id=clause_id,
        clause_text=clause_text,
        structured_data=structured_data,
    )


def build_batch_prompt(
    clause_id: str,
    clause_text: str,
    rules: list[dict[str, Any]],
    clause_data: dict[str, Any] | None = None,
) -> str:
    """
    Build a batch evaluation prompt for multiple rules.

    Args:
        clause_id: ID of clause being evaluated
        clause_text: Text content of the clause
        rules: List of rule dicts with id, name, description, detection_logic
        clause_data: Optional structured data dict

    Returns:
        Formatted batch prompt string
    """
    structured_data = ""
    if clause_data:
        import json
        structured_data = f"\nSTRUCTURED DATA:\n{json.dumps(clause_data, indent=2, ensure_ascii=False)}"

    rules_list = "\n".join([
        f"- [{r['id']}] {r['name']}: {r['description']}"
        for r in rules
    ])

    return BATCH_EVALUATION_PROMPT.format(
        clause_id=clause_id,
        clause_text=clause_text,
        structured_data=structured_data,
        rules_list=rules_list,
    )


def build_cross_clause_prompt(
    clause_a_id: str,
    clause_a_text: str,
    clause_a_category: str,
    clause_b_id: str,
    clause_b_text: str,
    clause_b_category: str,
    context: str = "",
) -> str:
    """
    Build a cross-clause analysis prompt.

    Args:
        clause_a_id: ID of first clause
        clause_a_text: Text of first clause
        clause_a_category: Category of first clause
        clause_b_id: ID of second clause
        clause_b_text: Text of second clause
        clause_b_category: Category of second clause
        context: Optional context about why these clauses are being compared

    Returns:
        Formatted cross-clause prompt string
    """
    return CROSS_CLAUSE_PROMPT.format(
        clause_a_id=clause_a_id,
        clause_a_text=clause_a_text,
        clause_a_category=clause_a_category,
        clause_b_id=clause_b_id,
        clause_b_text=clause_b_text,
        clause_b_category=clause_b_category,
        cross_context=context or "General coherence check",
    )


def get_few_shot_example(example_key: str) -> dict[str, Any] | None:
    """
    Get a specific few-shot example for prompt calibration.

    Args:
        example_key: Key from FEW_SHOT_EXAMPLES dict

    Returns:
        Example dict or None if not found
    """
    return FEW_SHOT_EXAMPLES.get(example_key)


def format_few_shot_for_prompt(example_key: str) -> str:
    """
    Format a few-shot example for inclusion in a prompt.

    Args:
        example_key: Key from FEW_SHOT_EXAMPLES dict

    Returns:
        Formatted example string for prompt inclusion
    """
    import json

    example = FEW_SHOT_EXAMPLES.get(example_key)
    if not example:
        return ""

    return f"""EXAMPLE ({example['rule']}):
Clause: "{example['clause'][:100]}..."
Expected Response:
{json.dumps(example['expected_response'], indent=2)}
"""
