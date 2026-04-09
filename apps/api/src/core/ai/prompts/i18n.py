"""
Multi-language prompt template support (TASK-FRT-124).

Provides English and Spanish versions of prompt templates with a
language-aware wrapper around PromptManager.

Usage:
    from src.core.ai.prompts.i18n import get_localized_prompt_manager

    manager = get_localized_prompt_manager(lang="en")
    system, user, version = manager.render_prompt(
        task_name="contract_extraction",
        context={"document_text": "..."},
    )

Supported languages: "en" (English, default), "es" (Spanish)
"""

from __future__ import annotations

from typing import Any

import structlog

from src.core.ai.prompts import (
    PromptManager,
    PromptTemplate,
    register_template,
)

logger = structlog.get_logger()

SUPPORTED_LANGUAGES = ("en", "es")

# ---------------------------------------------------------------------------
# English templates (v2.0 series - English-first for best LLM performance)
# ---------------------------------------------------------------------------

CONTRACT_EXTRACTION_EN_V2_0 = PromptTemplate(
    task_name="contract_extraction_en",
    version="2.0",
    description="Extract clauses, dates, amounts, and metadata from contracts (English)",
    system_prompt=(
        "You are a legal expert specializing in construction and public works contract analysis.\n\n"
        "Your task is to extract structured information from contractual documents.\n\n"
        "Instructions:\n"
        "1. Extract ONLY information that explicitly appears in the text\n"
        "2. If information is not present, indicate 'Not specified'\n"
        "3. For amounts, extract the numeric value and currency (CLP, USD, UF)\n"
        "4. For dates, use ISO 8601 format (YYYY-MM-DD)\n"
        "5. Identify the contract type (construction, services, supply, etc.)\n\n"
        "IMPORTANT:\n"
        "- Do NOT invent information\n"
        "- Do NOT make assumptions\n"
        "- Be precise with figures and dates\n"
        "- Keep the exact names of the parties"
    ),
    user_prompt_template=(
        "Analyze the following contractual document and extract the requested information.\n\n"
        "DOCUMENT:\n```\n{{ document_text }}\n```\n\n"
        "{% if max_clauses %}\nLIMIT: Extract a maximum of {{ max_clauses }} main clauses.\n{% endif %}\n\n"
        "Return the information in the following JSON format:\n\n"
        "{\n"
        '  "parties": {\n'
        '    "client": "Official name",\n'
        '    "contractor": "Official name"\n'
        "  },\n"
        '  "subject": "Brief description of the contract subject",\n'
        '  "contract_type": "construction|services|supply|other",\n'
        '  "total_amount": {\n'
        '    "value": 0.00,\n'
        '    "currency": "CLP|USD|UF"\n'
        "  },\n"
        '  "dates": {\n'
        '    "signing": "YYYY-MM-DD",\n'
        '    "start": "YYYY-MM-DD",\n'
        '    "end": "YYYY-MM-DD"\n'
        "  },\n"
        '  "main_clauses": [\n'
        "    {\n"
        '      "number": "X.Y",\n'
        '      "title": "Clause title",\n'
        '      "content": "Clause summary"\n'
        "    }\n"
        "  ],\n"
        '  "guarantees": [\n'
        "    {\n"
        '      "type": "performance|advance|quality",\n'
        '      "amount_percentage": 0.0\n'
        "    }\n"
        "  ]\n"
        "}"
    ),
    metadata={
        "author": "C2Pro Team",
        "date": "2026-04-09",
        "changelog": "English translation of v1.0 contract extraction",
        "language": "en",
    },
)

STAKEHOLDER_CLASSIFICATION_EN_V2_0 = PromptTemplate(
    task_name="stakeholder_classification_en",
    version="2.0",
    description="Classify stakeholders by power-interest level (English)",
    system_prompt=(
        "You are a stakeholder analyst expert in construction and public works projects.\n\n"
        "Your task is to classify stakeholders using the Power-Interest matrix:\n"
        "- POWER: Ability to influence the project (High/Medium/Low)\n"
        "- INTEREST: Level of impact or interest in the project (High/Medium/Low)\n\n"
        "Classification criteria:\n"
        "- HIGH POWER: Authorities, financiers, project managers, regulators\n"
        "- MEDIUM POWER: Department heads, supervisors, main suppliers\n"
        "- LOW POWER: Neighbors, local community, minor suppliers\n\n"
        "- HIGH INTEREST: Directly affected by the project (positively or negatively)\n"
        "- MEDIUM INTEREST: Indirect or moderate impact\n"
        "- LOW INTEREST: Minimal or tangential impact\n\n"
        "IMPORTANT:\n"
        "- Use the project context for classification\n"
        "- Be objective in evaluation"
    ),
    user_prompt_template=(
        "Classify the following project stakeholders.\n\n"
        "PROJECT CONTEXT:\n{{ project_description }}\n\n"
        "STAKEHOLDERS TO CLASSIFY:\n"
        "{% for stakeholder in stakeholders %}\n"
        "- {{ stakeholder.name }}{% if stakeholder.role %} ({{ stakeholder.role }}){% endif %}\n"
        "{% endfor %}\n\n"
        "Return the analysis in JSON format:\n\n"
        "{\n"
        '  "classifications": [\n'
        "    {\n"
        '      "stakeholder": "Name",\n'
        '      "power": "high|medium|low",\n'
        '      "interest": "high|medium|low",\n'
        '      "quadrant": "manage_closely|keep_satisfied|keep_informed|monitor",\n'
        '      "justification": "Brief explanation",\n'
        '      "recommended_strategy": "How to manage this relationship"\n'
        "    }\n"
        "  ]\n"
        "}"
    ),
    metadata={
        "author": "C2Pro Team",
        "date": "2026-04-09",
        "changelog": "English translation of v1.0 stakeholder classification",
        "language": "en",
    },
)

COHERENCE_CHECK_EN_V2_0 = PromptTemplate(
    task_name="coherence_check_en",
    version="2.0",
    description="Detect contradictions between dates, amounts, and commitments (English)",
    system_prompt=(
        "You are an expert auditor in detecting inconsistencies and contradictions "
        "in project documentation.\n\n"
        "Your task is to identify:\n"
        "1. DATE contradictions (incompatible deadlines, illogical sequences)\n"
        "2. AMOUNT contradictions (incorrect sums, duplicated or inconsistent values)\n"
        "3. COMMITMENT contradictions (conflicting obligations)\n\n"
        "Types of inconsistencies to detect:\n"
        "- End dates before start dates\n"
        "- Milestones with dates outside the total project timeline\n"
        "- Partial amounts that don't add up to the declared total\n"
        "- Same concept with different amounts in different sections\n"
        "- Mutually exclusive commitments\n"
        "- References to non-existent documents\n\n"
        "IMPORTANT:\n"
        "- Report ONLY verifiable contradictions\n"
        "- Include exact references (sections, paragraphs)\n"
        "- Indicate severity level (critical/moderate/minor)\n"
        "- Suggest corrections when the error is obvious"
    ),
    user_prompt_template=(
        "Analyze the following documents to detect contradictions.\n\n"
        "{% if document_pairs %}\n"
        "DOCUMENTS TO COMPARE:\n"
        "{% for doc in document_pairs %}\n"
        "### Document {{ loop.index }}: {{ doc.name }}\n"
        "```\n{{ doc.content }}\n```\n"
        "{% endfor %}\n"
        "{% else %}\n"
        "DOCUMENT TO ANALYZE:\n"
        "```\n{{ document_text }}\n```\n"
        "{% endif %}\n\n"
        "{% if check_types %}\n"
        "VERIFICATION TYPES REQUESTED:\n"
        "{% for check_type in check_types %}\n"
        "- {{ check_type }}\n"
        "{% endfor %}\n"
        "{% endif %}\n\n"
        "Return the analysis in JSON format:\n\n"
        "{\n"
        '  "overall_coherence": {\n'
        '    "score": 0.85,\n'
        '    "is_coherent": true,\n'
        '    "summary": "General coherence status description"\n'
        "  },\n"
        '  "contradictions": [\n'
        "    {\n"
        '      "type": "date|amount|commitment|other",\n'
        '      "severity": "critical|moderate|minor",\n'
        '      "description": "Clear contradiction description",\n'
        '      "locations": [\n'
        "        {\n"
        '          "document": "document_name",\n'
        '          "section": "Section 3.2",\n'
        '          "relevant_text": "Fragment showing the contradiction"\n'
        "        }\n"
        "      ],\n"
        '      "impact": "Impact explanation",\n'
        '      "correction_suggestion": "How it could be resolved"\n'
        "    }\n"
        "  ],\n"
        '  "warnings": [\n'
        "    {\n"
        '      "type": "upcoming_date|ambiguous_amount|confusing_term",\n'
        '      "description": "Warning about potential issues",\n'
        '      "location": "Where it was found"\n'
        "    }\n"
        "  ]\n"
        "}"
    ),
    metadata={
        "author": "C2Pro Team",
        "date": "2026-04-09",
        "changelog": "English translation of v1.0 coherence check",
        "language": "en",
    },
)

# ---------------------------------------------------------------------------
# Register English templates
# ---------------------------------------------------------------------------
register_template(CONTRACT_EXTRACTION_EN_V2_0)
register_template(STAKEHOLDER_CLASSIFICATION_EN_V2_0)
register_template(COHERENCE_CHECK_EN_V2_0)


# ---------------------------------------------------------------------------
# Language-to-task mapping
# ---------------------------------------------------------------------------

# Maps (base_task, language) -> actual task_name in registry
_LANGUAGE_MAP: dict[tuple[str, str], str] = {
    ("contract_extraction", "es"): "contract_extraction",
    ("contract_extraction", "en"): "contract_extraction_en",
    ("stakeholder_classification", "es"): "stakeholder_classification",
    ("stakeholder_classification", "en"): "stakeholder_classification_en",
    ("coherence_check", "es"): "coherence_check",
    ("coherence_check", "en"): "coherence_check_en",
}


class LocalizedPromptManager:
    """
    Language-aware wrapper around PromptManager.

    Resolves task names to their language-specific variants.
    Falls back to the base (Spanish) task if no translation exists.
    """

    def __init__(self, lang: str = "en") -> None:
        if lang not in SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Unsupported language '{lang}'. Supported: {SUPPORTED_LANGUAGES}"
            )
        self.lang = lang
        self._manager = PromptManager()
        logger.info("localized_prompt_manager_init", language=lang)

    def render_prompt(
        self,
        task_name: str,
        context: dict[str, Any],
        version: str = "latest",
    ) -> tuple[str, str, str]:
        """
        Render a prompt using the language-specific template.

        Falls back to the base task if no localized version exists.
        """
        resolved_task = _LANGUAGE_MAP.get((task_name, self.lang), task_name)

        logger.debug(
            "localized_prompt_resolve",
            original_task=task_name,
            language=self.lang,
            resolved_task=resolved_task,
        )

        return self._manager.render_prompt(resolved_task, context, version)

    def list_tasks(self) -> list[str]:
        """List all base task names available for the current language."""
        return [
            base_task
            for (base_task, lang) in _LANGUAGE_MAP
            if lang == self.lang
        ]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_instances: dict[str, LocalizedPromptManager] = {}


def get_localized_prompt_manager(lang: str = "en") -> LocalizedPromptManager:
    """Get a singleton LocalizedPromptManager for the given language."""
    if lang not in _instances:
        _instances[lang] = LocalizedPromptManager(lang)
    return _instances[lang]
