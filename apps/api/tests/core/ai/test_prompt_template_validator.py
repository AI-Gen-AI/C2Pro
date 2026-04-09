"""
Prompt template validator tests.
TS-CORE-AI-TPL-001
"""

from __future__ import annotations

from src.core.ai.prompts import PROMPT_REGISTRY
from src.core.ai.validators import PromptTemplateValidator


def test_validate_reports_jinja_syntax_errors() -> None:
    """Validator should fail fast on malformed Jinja syntax."""
    validator = PromptTemplateValidator()

    result = validator.validate(
        "{% if document_text %}{{ document_text }",
        required_vars=["document_text"],
    )

    assert result["valid"] is False
    assert result["syntax_valid"] is False
    assert "syntax error" in result["errors"][0]


def test_validate_reports_missing_required_and_unknown_variables() -> None:
    """Validator should identify missing required variables and out-of-contract declarations."""
    validator = PromptTemplateValidator()

    result = validator.validate(
        "Contrato: {{ contract_body }} {% if max_clauses %}{{ max_clauses }}{% endif %}",
        required_vars=["document_text"],
        allowed_vars=["document_text", "max_clauses"],
    )

    assert result["valid"] is False
    assert result["missing_required_variables"] == ["document_text"]
    assert result["unknown_variables"] == ["contract_body"]


def test_validate_supports_one_of_variable_groups() -> None:
    """Validator should allow templates that satisfy at least one variable from a one-of group."""
    validator = PromptTemplateValidator()

    ok_result = validator.validate(
        "{{ document_pairs }}",
        required_vars=[],
        allowed_vars=["document_text", "document_pairs"],
        one_of_groups=[["document_text", "document_pairs"]],
    )
    missing_result = validator.validate(
        "{{ check_types }}",
        required_vars=[],
        allowed_vars=["check_types", "document_text", "document_pairs"],
        one_of_groups=[["document_text", "document_pairs"]],
    )

    assert ok_result["valid"] is True
    assert missing_result["valid"] is False
    assert missing_result["missing_one_of_groups"] == [["document_pairs", "document_text"]]


def test_lint_registered_templates_passes_for_current_prompt_registry() -> None:
    """Validator should lint the currently registered prompt templates against the documented contract."""
    assert PROMPT_REGISTRY

    result = PromptTemplateValidator().lint_registered_templates()

    assert result["valid"] is True
    assert result["template_count"] >= 3
    assert all(item["valid"] for item in result["results"])
