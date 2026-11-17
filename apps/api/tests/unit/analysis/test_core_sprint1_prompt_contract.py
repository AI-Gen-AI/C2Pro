"""P0 regression checks for source fidelity and schema contracts in EPC extraction."""

import json
import re

from src.analysis.adapters.ai.tools.risk_extraction_tool import (
    RiskExtractionInput,
    RiskExtractionTool,
)
from src.analysis.domain.prompts import CRITIQUE_SYSTEM_PROMPT


def test_n4_prompt_classifies_by_context_not_fixed_clause_rules() -> None:
    user_prompt, system_prompt = RiskExtractionTool._build_default_prompt(
        None,
        RiskExtractionInput(document_text="Synthetic contract clause."),
        is_retry=False,
    )
    assert "Synthetic contract clause." in user_prompt
    assert "software" in system_prompt and "manufacturing" in system_prompt
    assert "unfamiliar sectors" in system_prompt
    assert "fixed catalog of expected risks" in system_prompt
    assert "codes are METADATA, NOT discovery rules" in system_prompt
    assert "No named clause type" in system_prompt
    assert "primary category is LEGAL, not SCHEDULE" not in system_prompt
    assert "remain LEGAL, not BUDGET" not in system_prompt


def test_n4_prompt_demands_literal_quote_with_exceptions() -> None:
    _, prompt = RiskExtractionTool._build_default_prompt(
        None,
        RiskExtractionInput(document_text="A contract provision about exclusions."),
        is_retry=False,
    )
    assert "character-for-character substring" in prompt
    assert "Never paraphrase, rewrite, merge non-adjacent text" in prompt
    assert "operative exception" in prompt
    assert "do not stop after an arbitrary number" in prompt


def test_n12_prompt_uses_exact_status_enum_without_human_approval() -> None:
    prompt = CRITIQUE_SYSTEM_PROMPT
    assert '"status": "RETRY"' in prompt
    assert 'output "RETRY" for one or more source-supported findings' in prompt
    assert 'or "OK" for none' in prompt
    assert "NEEDS_REVIEW, FLAGGED, UNASSESSED" in prompt
    assert "Return ONLY ONE syntactically valid JSON object" in prompt
    assert "human review" in prompt.lower()


def test_n12_prompt_examples_are_both_valid_json_and_mutually_exclusive() -> None:
    """The old prompt showed an invalid JSON union and only a RETRY example."""
    blocks = re.findall(r"(?ms)^\{.*?^\}", CRITIQUE_SYSTEM_PROMPT)
    assert len(blocks) == 2, "Both RETRY and OK examples must be JSON, not pseudo-schema"
    retry, ok = (json.loads(block) for block in blocks)
    assert list(retry) == ["status", "notes", "findings"]
    assert list(ok) == ["status", "notes", "findings"]
    assert retry["status"] == "RETRY"
    assert retry["findings"][0]["issue_type"] in ("omission", "contradiction")
    assert retry["findings"][0]["source_quote"]
    assert ok == {"status": "OK", "notes": "No issues found.", "findings": []}
    assert '"omission" | "contradiction"' not in CRITIQUE_SYSTEM_PROMPT


def test_n12_prompt_requires_sourced_findings_not_hidden_ok_caveats() -> None:
    prompt = CRITIQUE_SYSTEM_PROMPT
    assert "FINAL SELF-CHECK" in prompt
    assert "RETRY MUST have one or more actual source-quoted" in prompt
    assert 'the exactly neutral notes "No issues found."' in prompt
    assert "Never append a substantive clause-specific comment" in prompt
    assert "runtime handles absent/truncated source as unassessed with hitl" in prompt.lower()
    assert "mark it UNASSESSED in notes" not in prompt
    assert "make the verification uncertainty explicit" not in prompt


def test_n4_held_out_industry_and_short_substantive_clause_are_not_excluded() -> None:
    """Guard against turning editorial examples into restrictive discovery rules."""
    from src.analysis.domain.risk_provenance import VERIFIED, classify_quote

    short_clause = "Service credits apply after 3 days."
    user_prompt, system_prompt = RiskExtractionTool()._build_default_prompt(
        RiskExtractionInput(
            document_text=(
                "Software support agreement. " + short_clause
                + " An additional unusual risk is not named in any standard catalog."
            )
        ),
        is_retry=False,
    )
    assert "Software support agreement" in user_prompt
    assert "unfamiliar sectors" in system_prompt
    assert "fixed catalog of expected risks" in system_prompt
    assert "arbitrary length" in system_prompt
    assert "at least 80" not in system_prompt
    assert "≥80 characters" not in system_prompt
    assert classify_quote(short_clause, short_clause) == (short_clause, VERIFIED)


def test_n4_supports_exact_alphanumeric_source_locator_without_inference() -> None:
    source = "SLA-A: Provider will deliver incident reports within four hours."
    _, instructions = RiskExtractionTool()._build_default_prompt(
        RiskExtractionInput(document_text=source),
        is_retry=False,
    )
    assert "numeric or alphanumeric" in instructions
    assert "SLA-A" in instructions
    assert "never infer a clause number or invent any locator" in instructions

    candidate = RiskExtractionTool()._coerce_risk({
        "title": "Service reporting exposure",
        "category": "SCHEDULE",
        "summary": "A four-hour response window may be operationally demanding.",
        "description": "The provider must report incidents within the agreed time.",
        "probability": "MEDIUM",
        "impact": "HIGH",
        "source_quote": source,
        "clause_ref": "SLA-A",
    })
    assert candidate is not None
    assert candidate.clause_ref == "SLA-A"
