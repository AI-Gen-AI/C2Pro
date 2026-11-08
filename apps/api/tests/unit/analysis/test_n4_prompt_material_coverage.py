"""N4 prompt coverage contract: risk completeness without manufactured risks.

The real EPC golden evaluation 42507347031 extracted 8/9 material risks.
Prior system instructions preferred 3-8 risks, even when more independent
source-backed obligations were present. These are deterministic prompt tests;
no provider calls and no claims about model recall.
"""

from src.analysis.adapters.ai.tools.risk_extraction_tool import (
    RiskExtractionInput,
    RiskExtractionTool,
)


def test_n4_prompt_requires_whole_contract_review_without_eight_item_ceiling() -> None:
    source = (
        "Clause 1. The Contractor must comply with the agreed programme.\n"
        "Clause 2. The Contractor must notify the Client before requesting relief."
    )
    user_prompt, system_prompt = RiskExtractionTool()._build_default_prompt(
        RiskExtractionInput(document_text=source, max_risks=20), is_retry=False
    )
    assert user_prompt is not None and source in user_prompt
    assert system_prompt is not None
    assert "Review ALL substantive contract clauses" in system_prompt
    assert "do not stop after an arbitrary number of items" in system_prompt
    assert "never omit an independently supported material risk" in system_prompt
    assert "do not invent a risk merely to represent every clause" in system_prompt.lower()
    assert "3-8" not in system_prompt
    assert "source_quote must be ≥80 characters" in system_prompt
    assert "ONLY a JSON object" in system_prompt


def test_n4_prompt_requires_contract_exclusions_and_distinct_citations() -> None:
    _, system = RiskExtractionTool()._build_default_prompt(
        RiskExtractionInput(
            document_text="Force Majeure excludes market conditions but requires notice."
        ),
        is_retry=False,
    )
    assert system is not None
    for concept in (
        "force majeure",
        "carve-outs",
        "exclusions",
        "conditions for relief",
        "NOT available",
        "verbatim source quote",
    ):
        assert concept.casefold() in system.casefold()
