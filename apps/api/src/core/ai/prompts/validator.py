"""
Prompt Template Validator & Linter

TASK-FRT-123: Validates prompt templates for correctness, best practices,
and potential issues before registration.

Usage:
    from src.core.ai.prompts.validator import validate_template, lint_template

    errors = validate_template(template)
    warnings = lint_template(template)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from jinja2 import Environment, TemplateSyntaxError, meta

from src.core.ai.prompts import PromptTemplate


@dataclass(frozen=True)
class ValidationResult:
    """Result of a single validation check."""

    level: str  # "error" | "warning" | "info"
    code: str  # e.g. "V001", "L001"
    message: str
    field: str | None = None


# Patterns that suggest hardcoded secrets
SECRET_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9\-]{20,}"),  # OpenAI keys
    re.compile(r"sk_live_[a-zA-Z0-9]+"),  # Stripe/Clerk keys
    re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*"),  # Bearer tokens
    re.compile(r"password\s*[:=]\s*['\"][^'\"]+['\"]", re.IGNORECASE),
    re.compile(r"api[_-]?key\s*[:=]\s*['\"][^'\"]+['\"]", re.IGNORECASE),
]

# Semver-like version pattern
VERSION_PATTERN = re.compile(r"^\d+\.\d+(\.\d+)?$")


def validate_template(template: PromptTemplate) -> list[ValidationResult]:
    """
    Validate a prompt template for structural correctness.

    Returns a list of errors (level="error") that must be fixed.
    """
    results: list[ValidationResult] = []

    # V001: task_name must be non-empty and snake_case
    if not template.task_name:
        results.append(
            ValidationResult("error", "V001", "task_name is required", "task_name")
        )
    elif not re.match(r"^[a-z][a-z0-9_]*$", template.task_name):
        results.append(
            ValidationResult(
                "error",
                "V002",
                f"task_name '{template.task_name}' must be snake_case (lowercase, underscores only)",
                "task_name",
            )
        )

    # V003: version must follow semver-like format
    if not template.version:
        results.append(
            ValidationResult("error", "V003", "version is required", "version")
        )
    elif not VERSION_PATTERN.match(template.version):
        results.append(
            ValidationResult(
                "error",
                "V004",
                f"version '{template.version}' must be semver-like (e.g. '1.0', '1.1', '2.0.1')",
                "version",
            )
        )

    # V005: user_prompt_template must be non-empty
    if not template.user_prompt_template:
        results.append(
            ValidationResult(
                "error", "V005", "user_prompt_template is required", "user_prompt_template"
            )
        )

    # V006: user_prompt_template must be valid Jinja2
    if template.user_prompt_template:
        try:
            env = Environment()
            env.parse(template.user_prompt_template)
        except TemplateSyntaxError as e:
            results.append(
                ValidationResult(
                    "error",
                    "V006",
                    f"Invalid Jinja2 syntax in user_prompt_template: {e}",
                    "user_prompt_template",
                )
            )

    # V007: description should be non-empty
    if not template.description:
        results.append(
            ValidationResult(
                "error", "V007", "description is required", "description"
            )
        )

    return results


def lint_template(template: PromptTemplate) -> list[ValidationResult]:
    """
    Lint a prompt template for best practices and potential issues.

    Returns warnings and info-level findings.
    """
    results: list[ValidationResult] = []

    # L001: system_prompt should be non-empty (warning, not error)
    if not template.system_prompt:
        results.append(
            ValidationResult(
                "warning",
                "L001",
                "system_prompt is empty - consider adding role/context instructions",
                "system_prompt",
            )
        )

    # L002: Check for hardcoded secrets
    full_text = f"{template.system_prompt}\n{template.user_prompt_template}"
    for pattern in SECRET_PATTERNS:
        match = pattern.search(full_text)
        if match:
            results.append(
                ValidationResult(
                    "warning",
                    "L002",
                    f"Possible hardcoded secret detected: '{match.group()[:20]}...'",
                )
            )

    # L003: Prompt should be in English for best LLM performance
    if template.system_prompt and _detect_non_english(template.system_prompt):
        results.append(
            ValidationResult(
                "warning",
                "L003",
                "system_prompt appears to contain non-English text. "
                "LLM prompts perform best in English.",
                "system_prompt",
            )
        )

    # L004: Template should define expected output format
    if template.user_prompt_template and "json" not in template.user_prompt_template.lower():
        results.append(
            ValidationResult(
                "info",
                "L004",
                "user_prompt_template does not mention JSON output format. "
                "Consider specifying expected response structure.",
                "user_prompt_template",
            )
        )

    # L005: Very long system prompts may reduce response quality
    if template.system_prompt and len(template.system_prompt) > 3000:
        results.append(
            ValidationResult(
                "warning",
                "L005",
                f"system_prompt is {len(template.system_prompt)} chars. "
                "Prompts over 3000 chars may reduce response quality.",
                "system_prompt",
            )
        )

    # L006: Metadata should include author and date
    if not template.metadata:
        results.append(
            ValidationResult(
                "info",
                "L006",
                "No metadata provided. Consider adding author, date, and changelog.",
                "metadata",
            )
        )
    else:
        if "author" not in template.metadata:
            results.append(
                ValidationResult(
                    "info", "L007", "metadata missing 'author' field", "metadata"
                )
            )
        if "date" not in template.metadata:
            results.append(
                ValidationResult(
                    "info", "L008", "metadata missing 'date' field", "metadata"
                )
            )

    # L009: Check for unused Jinja2 variables (template has vars but no {{ }})
    if template.user_prompt_template and "{{" not in template.user_prompt_template:
        results.append(
            ValidationResult(
                "info",
                "L009",
                "user_prompt_template has no Jinja2 variables. "
                "Consider using variables for dynamic content.",
                "user_prompt_template",
            )
        )

    return results


def get_template_variables(template: PromptTemplate) -> set[str]:
    """
    Extract Jinja2 variable names from a template.

    Returns set of variable names referenced in the user_prompt_template.
    """
    try:
        env = Environment()
        ast = env.parse(template.user_prompt_template)
        return meta.find_undeclared_variables(ast)
    except TemplateSyntaxError:
        return set()


def validate_and_lint(template: PromptTemplate) -> list[ValidationResult]:
    """
    Run both validation and linting on a template.

    Returns combined list of all findings, errors first.
    """
    errors = validate_template(template)
    warnings = lint_template(template)
    return sorted(errors + warnings, key=lambda r: {"error": 0, "warning": 1, "info": 2}[r.level])


def _detect_non_english(text: str) -> bool:
    """Simple heuristic to detect non-English text (Spanish/Portuguese indicators)."""
    non_english_indicators = [
        "ñ", "á", "é", "í", "ó", "ú", "ü",
        "Eres un", "Tu tarea", "Instrucciones:",
        "IMPORTANTE:", "Retorna", "Analiza",
    ]
    count = sum(1 for indicator in non_english_indicators if indicator in text)
    return count >= 3


def format_results(results: Sequence[ValidationResult]) -> str:
    """Format validation results as a human-readable report."""
    if not results:
        return "All checks passed."

    lines: list[str] = []
    error_count = sum(1 for r in results if r.level == "error")
    warn_count = sum(1 for r in results if r.level == "warning")
    info_count = sum(1 for r in results if r.level == "info")

    lines.append(f"Found {error_count} error(s), {warn_count} warning(s), {info_count} info(s):")
    lines.append("")

    for result in results:
        prefix = {"error": "ERROR", "warning": "WARN ", "info": "INFO "}[result.level]
        field_str = f" [{result.field}]" if result.field else ""
        lines.append(f"  {prefix} {result.code}{field_str}: {result.message}")

    return "\n".join(lines)
