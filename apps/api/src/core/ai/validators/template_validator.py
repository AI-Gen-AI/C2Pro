"""
Prompt template validator and linter.
TS-CORE-AI-TPL-001
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jinja2 import Environment, meta
from jinja2.exceptions import TemplateSyntaxError

from src.core.ai.prompts import PROMPT_REGISTRY, PromptTemplate


@dataclass(frozen=True)
class PromptTemplateVariableSpec:
    """Expected variable contract for a registered prompt template."""

    required: frozenset[str]
    optional: frozenset[str] = frozenset()
    one_of: tuple[frozenset[str], ...] = ()

    @property
    def allowed(self) -> frozenset[str]:
        allowed = set(self.required) | set(self.optional)
        for group in self.one_of:
            allowed.update(group)
        return frozenset(allowed)


PROMPT_TEMPLATE_VARIABLE_SPECS: dict[str, PromptTemplateVariableSpec] = {
    "contract_extraction": PromptTemplateVariableSpec(
        required=frozenset({"document_text"}),
        optional=frozenset({"max_clauses"}),
    ),
    "stakeholder_classification": PromptTemplateVariableSpec(
        required=frozenset({"project_description", "stakeholders"}),
    ),
    "coherence_check": PromptTemplateVariableSpec(
        required=frozenset(),
        optional=frozenset({"check_types"}),
        one_of=(frozenset({"document_text", "document_pairs"}),),
    ),
}


class PromptTemplateValidator:
    """Validates Jinja2 prompt templates for syntax and variable-contract drift."""

    def __init__(self) -> None:
        self._env = Environment(trim_blocks=True, lstrip_blocks=True)

    def validate(
        self,
        template_str: str,
        required_vars: list[str],
        *,
        allowed_vars: list[str] | None = None,
        one_of_groups: list[list[str]] | None = None,
    ) -> dict[str, Any]:
        """
        Validate a Jinja2 template string against a variable contract.

        Returns a dict with syntax status, discovered variables, and warning/error lists.
        """
        errors: list[str] = []
        warnings: list[str] = []

        try:
            parsed = self._env.parse(template_str)
        except TemplateSyntaxError as exc:
            return {
                "valid": False,
                "syntax_valid": False,
                "errors": [f"syntax error at line {exc.lineno}: {exc.message}"],
                "warnings": [],
                "declared_variables": [],
                "missing_required_variables": sorted(required_vars),
                "unused_required_variables": [],
                "unknown_variables": [],
                "missing_one_of_groups": one_of_groups or [],
            }

        declared_variables = sorted(meta.find_undeclared_variables(parsed))
        declared_set = set(declared_variables)
        required_set = set(required_vars)
        allowed_set = set(allowed_vars or required_vars)
        one_of_groups = one_of_groups or []

        missing_required_variables = sorted(required_set - declared_set)
        if missing_required_variables:
            errors.append(
                "missing required variables: " + ", ".join(missing_required_variables)
            )

        missing_one_of_groups: list[list[str]] = []
        for group in one_of_groups:
            if declared_set.isdisjoint(group):
                missing_one_of_groups.append(sorted(group))
        if missing_one_of_groups:
            errors.extend(
                "template must declare at least one of: " + ", ".join(group)
                for group in missing_one_of_groups
            )

        unused_required_variables = sorted(required_set - declared_set)
        if unused_required_variables:
            warnings.append(
                "declared contract includes unused required variables: "
                + ", ".join(unused_required_variables)
            )

        unknown_variables = sorted(declared_set - allowed_set)
        if unknown_variables:
            warnings.append(
                "template declares variables outside the known contract: "
                + ", ".join(unknown_variables)
            )

        return {
            "valid": not errors,
            "syntax_valid": True,
            "errors": errors,
            "warnings": warnings,
            "declared_variables": declared_variables,
            "missing_required_variables": missing_required_variables,
            "unused_required_variables": unused_required_variables,
            "unknown_variables": unknown_variables,
            "missing_one_of_groups": missing_one_of_groups,
        }

    def validate_prompt_template(
        self,
        template: PromptTemplate,
        *,
        required_vars: list[str],
        allowed_vars: list[str] | None = None,
        one_of_groups: list[list[str]] | None = None,
    ) -> dict[str, Any]:
        """Validate a registered PromptTemplate object."""
        result = self.validate(
            template.user_prompt_template,
            required_vars=required_vars,
            allowed_vars=allowed_vars,
            one_of_groups=one_of_groups,
        )
        result["task_name"] = template.task_name
        result["version"] = template.version
        return result

    def lint_registered_templates(self) -> dict[str, Any]:
        """Lint the templates currently registered in PROMPT_REGISTRY."""
        results: list[dict[str, Any]] = []

        for task_name, versions in PROMPT_REGISTRY.items():
            spec = PROMPT_TEMPLATE_VARIABLE_SPECS.get(task_name)
            if spec is None:
                results.append(
                    {
                        "task_name": task_name,
                        "version": None,
                        "valid": False,
                        "syntax_valid": True,
                        "errors": [f"missing variable spec for registered task '{task_name}'"],
                        "warnings": [],
                        "declared_variables": [],
                        "missing_required_variables": [],
                        "unused_required_variables": [],
                        "unknown_variables": [],
                        "missing_one_of_groups": [],
                    }
                )
                continue

            for version, template in versions.items():
                result = self.validate_prompt_template(
                    template,
                    required_vars=sorted(spec.required),
                    allowed_vars=sorted(spec.allowed),
                    one_of_groups=[sorted(group) for group in spec.one_of],
                )
                result["version"] = version
                results.append(result)

        return {
            "valid": all(result["valid"] for result in results),
            "template_count": len(results),
            "results": results,
        }
