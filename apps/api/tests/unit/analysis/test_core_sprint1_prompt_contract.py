"""P0 regression checks for source fidelity and schema contracts in EPC extraction."""

import json
import re

from src.analysis.adapters.ai.tools.risk_extraction_tool import RiskExtractionInput, RiskExtractionTool
from src.analysis.domain.prompts import CRITIQUE_SYSTEM_PROMPT


def test_n4_prompt_uses_dominant_legal_vs_schedule_or_budget_category() -> None:
    user_prompt, system_prompt = RiskExtractionTool._build_default_prompt(
        None,
        RiskExtractionInput(document_text="Synthetic contract clause."),
        is_retry=False,
    )
    assert "Synthetic contract clause." in user_prompt
    assert "PRIMARY CATEGORY SELECTION" in system_prompt
    assert "force majeure relief" in system_prompt
    assert "liability caps and carve-outs" in system_prompt
    assert "termination rights" in system_prompt
    assert "late-completion liquidated damages" in system_prompt
    assert "standalone payment" in system_prompt
    assert "primary category is LEGAL, not SCHEDULE" in system_prompt
    assert "remain LEGAL, not BUDGET" in system_prompt


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
