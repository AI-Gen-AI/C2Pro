#!/usr/bin/env python3
"""
Prompt template validator CLI — TASK-AI-039

Scans all registered Jinja2 prompt templates in src/core/ai/prompts/,
validates naming conventions, required metadata, and Jinja2 syntax.

Usage (from apps/api/):
    python scripts/validate_prompt_templates.py
    python scripts/validate_prompt_templates.py --strict   # warnings become errors

Exit codes:
    0  All checks passed
    1  One or more errors found
    2  Warnings found (only when --strict is set)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running from apps/api/ or from the repo root
_API_DIR = Path(__file__).resolve().parent.parent
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))


def _import_modules():
    """Import validator modules after path is configured."""
    # Trigger template registration by importing the prompts package
    import src.core.ai.prompts  # noqa: F401 — registers all templates as side-effect

    from src.core.ai.prompts import PROMPT_REGISTRY
    from src.core.ai.prompts.validator import (
        ValidationResult,
        format_results,
        validate_and_lint,
    )
    from src.core.ai.validators.template_validator import PromptTemplateValidator

    return PROMPT_REGISTRY, validate_and_lint, format_results, ValidationResult, PromptTemplateValidator


def _run(strict: bool) -> int:
    try:
        PROMPT_REGISTRY, validate_and_lint, format_results, ValidationResult, PromptTemplateValidator = _import_modules()
    except ImportError as exc:
        print(f"ERROR: Could not import prompt modules: {exc}", file=sys.stderr)
        print("Run this script from apps/api/ with the virtualenv activated.", file=sys.stderr)
        return 1

    if not PROMPT_REGISTRY:
        print("WARNING: PROMPT_REGISTRY is empty — no templates registered.", file=sys.stderr)
        return 0

    all_errors: list[str] = []
    all_warnings: list[str] = []
    total_templates = 0

    print("=" * 60)
    print("C2Pro Prompt Template Validator")
    print("=" * 60)

    # ── Pass 1: structural + lint checks via prompts/validator.py ────────────
    print("\n[Pass 1] Structural & lint checks")
    for task_name, versions in PROMPT_REGISTRY.items():
        for version, template in versions.items():
            total_templates += 1
            label = f"{task_name} v{version}"
            results = validate_and_lint(template)
            errors = [r for r in results if r.level == "error"]
            warnings = [r for r in results if r.level == "warning"]

            if errors:
                print(f"  FAIL  {label}")
                for r in errors:
                    msg = f"        [{r.code}] {r.message}"
                    print(msg)
                    all_errors.append(f"{label}: {r.message}")
            elif warnings:
                print(f"  WARN  {label}")
                for r in warnings:
                    msg = f"        [{r.code}] {r.message}"
                    print(msg)
                    all_warnings.append(f"{label}: {r.message}")
            else:
                print(f"  OK    {label}")

    # ── Pass 2: variable contract drift via validators/template_validator.py ─
    print("\n[Pass 2] Variable contract checks")
    validator = PromptTemplateValidator()
    contract_report = validator.lint_registered_templates()
    for result in contract_report.get("results", []):
        task = result.get("task_name", "?")
        ver = result.get("version", "?")
        label = f"{task} v{ver}"
        if result.get("errors"):
            for err in result["errors"]:
                print(f"  FAIL  {label}: {err}")
                all_errors.append(f"{label} [contract]: {err}")
        elif result.get("warnings"):
            for warn in result["warnings"]:
                print(f"  WARN  {label}: {warn}")
                all_warnings.append(f"{label} [contract]: {warn}")
        else:
            if result.get("task_name"):
                print(f"  OK    {label}")

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"Templates scanned : {total_templates}")
    print(f"Errors            : {len(all_errors)}")
    print(f"Warnings          : {len(all_warnings)}")
    print("=" * 60)

    if all_errors:
        print("\nFAILED — fix the errors above before merging.", file=sys.stderr)
        return 1

    if strict and all_warnings:
        print("\nFAILED (--strict) — warnings are treated as errors.", file=sys.stderr)
        return 2

    print("\nAll checks passed.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate C2Pro Jinja2 prompt templates",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors (exit 2 if warnings present)",
    )
    args = parser.parse_args()
    sys.exit(_run(strict=args.strict))


if __name__ == "__main__":
    main()
