"""Tests for analysis domain prompt templates registry.

TASK-IMPL-010.1: All prompts centralized, English, no framework imports.
"""

from __future__ import annotations

from src.analysis.domain.prompts import (
    BUDGET_EXTRACTION_PROMPT,
    CRITIQUE_SYSTEM_PROMPT,
    DOC_TYPES,
    RACI_GENERATION_PROMPT,
    ROUTER_SYSTEM_PROMPT,
    SCHEDULE_EXTRACTION_PROMPT,
)


class TestDocTypes:
    def test_contains_four_core_types(self):
        assert "contract" in DOC_TYPES
        assert "technical_spec" in DOC_TYPES
        assert "budget" in DOC_TYPES
        assert "schedule" in DOC_TYPES

    def test_is_tuple(self):
        assert isinstance(DOC_TYPES, tuple)
        assert len(DOC_TYPES) == 4


class TestRouterPrompt:
    def test_is_non_empty_string(self):
        assert isinstance(ROUTER_SYSTEM_PROMPT, str)
        assert len(ROUTER_SYSTEM_PROMPT) > 0

    def test_contains_all_doc_types(self):
        for doc_type in DOC_TYPES:
            assert doc_type in ROUTER_SYSTEM_PROMPT

    def test_is_in_english(self):
        assert "Classify" in ROUTER_SYSTEM_PROMPT or "classify" in ROUTER_SYSTEM_PROMPT


class TestCritiquePrompt:
    def test_is_non_empty_string(self):
        assert isinstance(CRITIQUE_SYSTEM_PROMPT, str)
        assert len(CRITIQUE_SYSTEM_PROMPT) > 0

    def test_contains_status_options(self):
        assert "OK" in CRITIQUE_SYSTEM_PROMPT
        assert "RETRY" in CRITIQUE_SYSTEM_PROMPT

    def test_is_in_english(self):
        assert "quality" in CRITIQUE_SYSTEM_PROMPT.lower()


class TestRaciPrompt:
    def test_is_non_empty_string(self):
        assert isinstance(RACI_GENERATION_PROMPT, str)
        assert len(RACI_GENERATION_PROMPT) > 0

    def test_contains_raci_roles(self):
        for role in ("Responsible", "Accountable", "Consulted", "Informed"):
            assert role in RACI_GENERATION_PROMPT


class TestBudgetPrompt:
    def test_is_non_empty_string(self):
        assert isinstance(BUDGET_EXTRACTION_PROMPT, str)
        assert len(BUDGET_EXTRACTION_PROMPT) > 0

    def test_contains_budget_keywords(self):
        assert "amount" in BUDGET_EXTRACTION_PROMPT


class TestSchedulePrompt:
    def test_is_non_empty_string(self):
        assert isinstance(SCHEDULE_EXTRACTION_PROMPT, str)
        assert len(SCHEDULE_EXTRACTION_PROMPT) > 0

    def test_contains_schedule_keywords(self):
        assert "milestone" in SCHEDULE_EXTRACTION_PROMPT.lower()
        assert "critical" in SCHEDULE_EXTRACTION_PROMPT.lower()

    def test_contains_date_fields(self):
        assert "start_date" in SCHEDULE_EXTRACTION_PROMPT
        assert "end_date" in SCHEDULE_EXTRACTION_PROMPT
