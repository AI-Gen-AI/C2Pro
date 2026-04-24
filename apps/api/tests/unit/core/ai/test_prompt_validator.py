"""Tests for prompt template validator and linter (TASK-FRT-123)."""


from src.core.ai.prompts import PromptTemplate
from src.core.ai.prompts.validator import (
    ValidationResult,
    format_results,
    get_template_variables,
    lint_template,
    validate_and_lint,
    validate_template,
)


def _make_template(**overrides) -> PromptTemplate:
    """Create a valid template with optional overrides."""
    defaults = {
        "task_name": "test_extraction",
        "version": "1.0",
        "system_prompt": "You are a helpful assistant.",
        "user_prompt_template": "Analyze this: {{ document_text }}",
        "description": "Test template for unit tests",
        "metadata": {"author": "Test", "date": "2026-04-09"},
    }
    defaults.update(overrides)
    return PromptTemplate(**defaults)


class TestValidateTemplate:
    def test_valid_template_passes(self):
        template = _make_template()
        results = validate_template(template)
        errors = [r for r in results if r.level == "error"]
        assert errors == []

    def test_invalid_task_name_not_snake_case(self):
        template = _make_template(task_name="MyTask")
        results = validate_template(template)
        codes = [r.code for r in results]
        assert "V002" in codes

    def test_invalid_version_format(self):
        template = _make_template(version="v1")
        results = validate_template(template)
        codes = [r.code for r in results]
        assert "V004" in codes

    def test_valid_three_part_version(self):
        template = _make_template(version="2.0.1")
        results = validate_template(template)
        errors = [r for r in results if r.level == "error"]
        assert errors == []

    def test_invalid_jinja2_syntax(self):
        template = _make_template(user_prompt_template="{{ unclosed")
        results = validate_template(template)
        codes = [r.code for r in results]
        assert "V006" in codes

    def test_missing_description(self):
        template = _make_template(description="")
        results = validate_template(template)
        codes = [r.code for r in results]
        assert "V007" in codes


class TestLintTemplate:
    def test_empty_system_prompt_warns(self):
        template = _make_template(system_prompt="")
        results = lint_template(template)
        codes = [r.code for r in results]
        assert "L001" in codes

    def test_hardcoded_secret_detected(self):
        template = _make_template(
            system_prompt="Use key sk-proj-abcdef1234567890abcdef1234567890"
        )
        results = lint_template(template)
        codes = [r.code for r in results]
        assert "L002" in codes

    def test_non_english_prompt_warns(self):
        template = _make_template(
            system_prompt="Eres un experto en análisis. Tu tarea es extraer información. IMPORTANTE: Retorna JSON."
        )
        results = lint_template(template)
        codes = [r.code for r in results]
        assert "L003" in codes

    def test_no_json_output_format_info(self):
        template = _make_template(
            user_prompt_template="Just analyze this: {{ text }}"
        )
        results = lint_template(template)
        codes = [r.code for r in results]
        assert "L004" in codes

    def test_long_system_prompt_warns(self):
        template = _make_template(system_prompt="x" * 3500)
        results = lint_template(template)
        codes = [r.code for r in results]
        assert "L005" in codes

    def test_missing_metadata_info(self):
        template = _make_template(metadata=None)
        results = lint_template(template)
        codes = [r.code for r in results]
        assert "L006" in codes

    def test_missing_author_info(self):
        template = _make_template(metadata={"date": "2026-04-09"})
        results = lint_template(template)
        codes = [r.code for r in results]
        assert "L007" in codes

    def test_no_variables_info(self):
        template = _make_template(
            user_prompt_template="Static prompt with no variables. Return json."
        )
        results = lint_template(template)
        codes = [r.code for r in results]
        assert "L009" in codes

    def test_clean_template_no_warnings(self):
        template = _make_template()
        results = lint_template(template)
        # Should have no warnings (only possibly info)
        warnings = [r for r in results if r.level == "warning"]
        assert warnings == []


class TestGetTemplateVariables:
    def test_extracts_simple_variables(self):
        template = _make_template(
            user_prompt_template="Hello {{ name }}, your doc is {{ document_text }}"
        )
        variables = get_template_variables(template)
        assert variables == {"name", "document_text"}

    def test_extracts_loop_variables(self):
        template = _make_template(
            user_prompt_template="{% for item in items %}{{ item.name }}{% endfor %}"
        )
        variables = get_template_variables(template)
        assert "items" in variables

    def test_invalid_template_returns_empty(self):
        template = _make_template(user_prompt_template="{{ unclosed")
        variables = get_template_variables(template)
        assert variables == set()


class TestValidateAndLint:
    def test_combined_results_sorted(self):
        template = _make_template(
            task_name="BadName",
            system_prompt="",
            metadata=None,
        )
        results = validate_and_lint(template)
        # Errors should come first
        levels = [r.level for r in results]
        error_indices = [i for i, l in enumerate(levels) if l == "error"]
        non_error_indices = [i for i, l in enumerate(levels) if l != "error"]
        if error_indices and non_error_indices:
            assert max(error_indices) < min(non_error_indices)


class TestFormatResults:
    def test_empty_results(self):
        output = format_results([])
        assert "All checks passed" in output

    def test_formats_findings(self):
        results = [
            ValidationResult("error", "V001", "task_name is required", "task_name"),
            ValidationResult("warning", "L001", "system_prompt empty", "system_prompt"),
        ]
        output = format_results(results)
        assert "1 error(s)" in output
        assert "1 warning(s)" in output
        assert "V001" in output
        assert "L001" in output
