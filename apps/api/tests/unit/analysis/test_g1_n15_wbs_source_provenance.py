"""G1/N15 source-provenance negatives for WBS proposals.

An extraction may be PROPOSED, but must not pass citation validation unless
EVERY claimed WBS has a verbatim passage from its source document.
"""

from src.analysis.adapters.ai.tools.wbs_extraction_tool import WBSExtractionInput, WBSExtractionTool, WBSItemOutput
from src.analysis.adapters.graph.nodes import _wbs_contract_payload
from src.analysis.domain.citation_validation import CitationValidatorService
from src.analysis.domain.contracts import WbsActivity

SPEC = (
    "SYN EPC 2026 - Technical Specification 6.1 Equipment Technical requirements "
    "for transformer, substation, electrical installation and commissioning. "
    "6.3 Factory Acceptance Test 6.3 Factory acceptance testing shall be completed "
    "no later than 2027-06-10 before dispatch. The FAT protocol and result must "
    "be traceable. 6.4 Handover Final commissioning and handover must be "
    "documented, reviewed and signed. SYNTHETIC TEST DOCUMENT - no commercial validity."
)


def test_existing_spec_v2_six_wbs_without_quotes_cannot_pass_n15() -> None:
    codes = ("1", "1.1", "1.2", "1.2.1", "1.3", "1.3.1")
    items = [{"code": code, "name": "Technical deliverable", "description": "A generated technical activity"} for code in codes]
    result = CitationValidatorService().validate(SPEC, [], items)
    assert result.total_count == 6
    assert result.validated_count == 0
    assert all(not c.found_in_source for c in result.citations)
    assert result.validation_passed is False


def test_wbs_made_up_quote_fails_even_when_risk_citation_is_valid() -> None:
    risk = {"title": "FAT delay", "source_quote": "no later than 2027-06-10"}
    invented = {"code": "1.2.1", "name": "FAT calibration", "source_quote": "Calibrate digital equipment to 500 MPa"}
    result = CitationValidatorService().validate(SPEC, [risk], [invented])
    assert result.validated_count == 1
    assert result.total_count == 2
    assert result.validation_passed is False


def test_one_unsupported_wbs_blocks_even_above_sixty_percent_aggregate() -> None:
    quotes = [
        "Equipment Technical requirements",
        "Factory acceptance testing shall be completed",
        "The FAT protocol and result must be traceable.",
        "Final commissioning and handover must be documented",
    ]
    items = [
        {"code": f"1.{index}", "name": "Proposal", "source_quote": quote}
        for index, quote in enumerate(quotes, 1)
    ]
    items.append({"code": "1.5", "name": "Fabricated deliverable", "source_quote": "unmentioned special substation certificate"})
    result = CitationValidatorService().validate(SPEC, [], items)
    assert result.validated_count == 4
    assert result.total_count == 5
    assert result.validation_passed is False


def test_exact_source_quote_allows_cited_wbs_without_autoapproving_it() -> None:
    result = CitationValidatorService().validate(
        SPEC, [], [{"code": "1.2", "name": "Factory Acceptance Test", "source_quote": "Factory acceptance testing shall be completed no later than 2027-06-10"}]
    )
    assert result.validation_passed is True
    assert result.citations[0].found_in_source is True
    # N15 citation validity is NOT a human approval, a signed WBS association or TRUSTED.



def test_case_modified_wbs_quote_is_not_literal_evidence() -> None:
    # The source contains capitalized FAT. Lowercasing the model quote is NOT
    # verbatim preservation and must not pass the transactional citation gate.
    quote = "factory acceptance testing shall be completed no later than 2027-06-10"
    result = CitationValidatorService().validate(
        SPEC, [], [{"code": "1.2", "name": "FAT", "source_quote": quote}]
    )
    assert result.citations[0].found_in_source is False
    assert result.validation_passed is False


def test_no_extractions_keep_existing_empty_pass_semantics() -> None:
    result = CitationValidatorService().validate(SPEC, [], [])
    assert result.validation_passed is True
    assert result.total_count == 0


def test_wbs_models_preserve_verbatim_quote_end_to_end() -> None:
    quote = "The FAT protocol and result must be traceable."
    dto = WBSItemOutput(code="1.2", name="FAT", item_type="work_package", source_quote=quote)
    artifact_item = WbsActivity.model_validate(_wbs_contract_payload(dto.model_dump()))
    assert artifact_item.source_quote == quote


def test_wbs_prompt_requires_literal_quote_and_omits_unsupported_items() -> None:
    _, prompt = WBSExtractionTool()._build_default_prompt(
        WBSExtractionInput(document_text=SPEC), is_retry=False
    )
    assert "source_quote literal" in prompt
    assert "NO generes el elemento" in prompt
