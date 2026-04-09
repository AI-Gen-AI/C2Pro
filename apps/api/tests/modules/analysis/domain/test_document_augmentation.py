"""Tests for document augmentation and risk conversion domain services.

TASK-IMPL-010.2: Pure domain logic, no framework dependencies.
"""

from __future__ import annotations

from src.analysis.domain.document_augmentation import (
    DocumentAugmentationService,
    RiskItemConverter,
)


class TestDocumentAugmentationService:
    def setup_method(self):
        self.service = DocumentAugmentationService()

    def test_augment_with_both_critique_and_feedback(self):
        result = self.service.augment(
            text="Base text",
            critique_notes="Fix citations",
            human_feedback="Approved with changes",
        )
        assert "Base text" in result
        assert "NOTAS_CRITICAS: Fix citations" in result
        assert "FEEDBACK_HUMANO: Approved with changes" in result

    def test_augment_with_only_critique(self):
        result = self.service.augment(
            text="Base text",
            critique_notes="Missing references",
            human_feedback="",
        )
        assert "NOTAS_CRITICAS: Missing references" in result
        assert "FEEDBACK_HUMANO" not in result

    def test_augment_with_only_feedback(self):
        result = self.service.augment(
            text="Base text",
            critique_notes="",
            human_feedback="Looks good",
        )
        assert "NOTAS_CRITICAS" not in result
        assert "FEEDBACK_HUMANO: Looks good" in result

    def test_augment_with_neither(self):
        result = self.service.augment(
            text="Base text",
            critique_notes="",
            human_feedback="",
        )
        assert result == "Base text"

    def test_augment_preserves_original_text(self):
        original = "Important document content here"
        result = self.service.augment(original, "note", "")
        assert result.startswith(original)


class TestRiskItemConverter:
    def setup_method(self):
        self.converter = RiskItemConverter()

    def test_converts_all_fields(self):
        """Test conversion of a risk object with all attributes."""

        class MockRisk:
            category = type("Cat", (), {"value": "LEGAL"})()
            title = "Contract risk"
            summary = "Risk summary"
            description = "Full description"
            probability = type("Prob", (), {"value": "HIGH"})()
            impact = type("Imp", (), {"value": "CRITICAL"})()
            mitigation_suggestion = "Review clause"
            source_quote = "Section 5.1"
            source_text_snippet = "The contractor shall..."
            risk_score = 85
            immediate_alert = True

        result = self.converter.to_dict(MockRisk())
        assert result["category"] == "LEGAL"
        assert result["title"] == "Contract risk"
        assert result["probability"] == "HIGH"
        assert result["impact"] == "CRITICAL"
        assert result["risk_score"] == 85
        assert result["immediate_alert"] is True

    def test_handles_none_enum_fields(self):
        """Test that None category/probability/impact are handled."""

        class MockRisk:
            category = None
            title = "Risk"
            summary = None
            description = None
            probability = None
            impact = None
            mitigation_suggestion = None
            source_quote = None
            source_text_snippet = None
            risk_score = 0
            immediate_alert = False

        result = self.converter.to_dict(MockRisk())
        assert result["category"] is None
        assert result["probability"] is None
        assert result["impact"] is None
        assert result["risk_score"] == 0

    def test_handles_missing_attributes(self):
        """Test that missing attributes use defaults via getattr."""

        class MinimalRisk:
            pass

        result = self.converter.to_dict(MinimalRisk())
        assert result["category"] is None
        assert result["title"] is None
        assert result["risk_score"] == 0
        assert result["immediate_alert"] is False
