"""Freeze-lock tests for ADR-013 typed payload contracts (TASK-V3-013-01).

Independently verifies the FROZEN contracts in src/analysis/domain/contracts.py
before downstream implementation builds on them. Asserts: drift rejection
(extra=forbid), immutability (frozen), honest-null defaults (never fabricated
0/100), bounded confidence/score, severity-from-impact normalization, and that
the current extractor dict shapes validate into the models.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.analysis.domain.contracts import (
    BudgetItem,
    Citation,
    CoherenceFinding,
    DocumentArtifact,
    RiskItem,
    Severity,
    WbsActivity,
)


class TestRiskItem:
    def test_minimal_valid_has_honest_nulls(self):
        r = RiskItem(title="T", description="D")
        assert r.category == "general"
        assert r.severity is None  # not fabricated

    def test_current_extractor_shape_validates(self):
        # Shape emitted today by DeterministicRiskRulesService / risk tool.
        r = RiskItem(
            category="LEGAL",
            title="Delay penalty exposure",
            description="penalty language linked to delay",
            impact="HIGH",
            confidence=0.82,
        )
        assert r.severity is Severity.HIGH  # normalized from impact
        assert r.impact is Severity.HIGH

    def test_explicit_severity_wins_over_impact(self):
        r = RiskItem(title="T", description="D", severity="LOW", impact="HIGH")
        assert r.severity is Severity.LOW

    def test_extra_key_rejected(self):
        with pytest.raises(ValidationError):
            RiskItem(title="T", description="D", bogus="x")

    def test_frozen(self):
        r = RiskItem(title="T", description="D")
        with pytest.raises(ValidationError):
            r.title = "X"

    def test_confidence_out_of_range_rejected(self):
        with pytest.raises(ValidationError):
            RiskItem(title="T", description="D", confidence=1.5)


class TestWbsActivity:
    def test_current_shape(self):
        w = WbsActivity(code="1.1", name="Contract scope execution", description="exec")
        assert w.code == "1.1"
        assert w.percent_complete is None

    def test_extra_rejected(self):
        with pytest.raises(ValidationError):
            WbsActivity(code="1.1", name="n", bogus=1)

    def test_percent_complete_bounds(self):
        with pytest.raises(ValidationError):
            WbsActivity(code="1", name="n", percent_complete=150)


class TestBudgetItem:
    def test_current_shape(self):
        b = BudgetItem(name="Cabling", amount=1000.0, currency="EUR", category="materials")
        assert b.currency == "EUR"

    def test_defaults(self):
        b = BudgetItem(name="x")
        assert b.amount == 0.0
        assert b.currency == "EUR"

    def test_extra_rejected(self):
        with pytest.raises(ValidationError):
            BudgetItem(name="x", bogus=1)


class TestCitation:
    def test_valid(self):
        c = Citation(type="risk", item="Delay penalty", quote="...", found_in_source=True)
        assert c.found_in_source is True

    def test_missing_required_rejected(self):
        with pytest.raises(ValidationError):
            Citation(type="risk", item="x", quote="y")  # missing found_in_source


class TestCoherenceFinding:
    def test_honest_null_score(self):
        f = CoherenceFinding(category="SCOPE", message="insufficient evidence")
        assert f.score is None  # never fabricated 0

    def test_score_out_of_range_rejected(self):
        with pytest.raises(ValidationError):
            CoherenceFinding(category="SCOPE", message="m", score=120)


class TestDocumentArtifact:
    def test_aggregates_typed_payloads(self):
        art = DocumentArtifact(
            document_id="doc-1",
            doc_type="contract",
            extracted_risks=[RiskItem(title="T", description="D", impact="HIGH")],
            bom_items=[{"name": "x", "amount": 5.0}],  # dict coerced to BudgetItem
        )
        assert art.extracted_risks[0].severity is Severity.HIGH
        assert isinstance(art.bom_items[0], BudgetItem)
        assert art.confidence_score is None  # honest null

    def test_extra_rejected(self):
        with pytest.raises(ValidationError):
            DocumentArtifact(document_id="d", doc_type="contract", bogus=1)

    def test_invalid_nested_payload_rejected(self):
        with pytest.raises(ValidationError):
            DocumentArtifact(
                document_id="d",
                doc_type="contract",
                extracted_risks=[{"title": "T"}],  # missing description
            )
