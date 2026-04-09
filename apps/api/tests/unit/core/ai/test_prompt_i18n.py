"""Tests for multi-language prompt templates (TASK-FRT-124)."""

import pytest

from src.core.ai.prompts.i18n import (
    SUPPORTED_LANGUAGES,
    LocalizedPromptManager,
    get_localized_prompt_manager,
)


class TestLocalizedPromptManager:
    def test_english_contract_extraction(self):
        manager = LocalizedPromptManager(lang="en")
        system, user, version = manager.render_prompt(
            "contract_extraction",
            {"document_text": "Sample contract text", "max_clauses": 5},
        )
        assert "legal expert" in system.lower() or "expert" in system.lower()
        assert "Sample contract text" in user
        assert version == "2.0"

    def test_spanish_contract_extraction(self):
        manager = LocalizedPromptManager(lang="es")
        system, user, version = manager.render_prompt(
            "contract_extraction",
            {"document_text": "Texto del contrato", "max_clauses": 5},
        )
        assert "experto legal" in system.lower() or "legal" in system.lower()
        assert "Texto del contrato" in user
        assert version == "1.0"

    def test_english_stakeholder_classification(self):
        manager = LocalizedPromptManager(lang="en")
        system, user, version = manager.render_prompt(
            "stakeholder_classification",
            {
                "project_description": "Building renovation",
                "stakeholders": [
                    {"name": "John Doe", "role": "Project Manager"},
                ],
            },
        )
        assert "stakeholder" in system.lower()
        assert "John Doe" in user
        assert version == "2.0"

    def test_english_coherence_check(self):
        manager = LocalizedPromptManager(lang="en")
        system, user, version = manager.render_prompt(
            "coherence_check",
            {"document_text": "Contract section A says..."},
        )
        assert "auditor" in system.lower() or "inconsistencies" in system.lower()
        assert "Contract section A says" in user
        assert version == "2.0"

    def test_unsupported_language_raises(self):
        with pytest.raises(ValueError, match="Unsupported language"):
            LocalizedPromptManager(lang="fr")

    def test_list_tasks_en(self):
        manager = LocalizedPromptManager(lang="en")
        tasks = manager.list_tasks()
        assert "contract_extraction" in tasks
        assert "stakeholder_classification" in tasks
        assert "coherence_check" in tasks

    def test_list_tasks_es(self):
        manager = LocalizedPromptManager(lang="es")
        tasks = manager.list_tasks()
        assert "contract_extraction" in tasks


class TestGetLocalizedPromptManager:
    def test_returns_same_instance(self):
        m1 = get_localized_prompt_manager("en")
        m2 = get_localized_prompt_manager("en")
        assert m1 is m2

    def test_different_languages_different_instances(self):
        m_en = get_localized_prompt_manager("en")
        m_es = get_localized_prompt_manager("es")
        assert m_en is not m_es
        assert m_en.lang == "en"
        assert m_es.lang == "es"


class TestSupportedLanguages:
    def test_en_and_es_supported(self):
        assert "en" in SUPPORTED_LANGUAGES
        assert "es" in SUPPORTED_LANGUAGES
