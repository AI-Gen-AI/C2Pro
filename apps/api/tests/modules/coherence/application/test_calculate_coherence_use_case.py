"""
Calculate Coherence Use Case Tests (TDD).

Refers to Suite ID: TS-UA-COH-UC-001.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.coherence.application.dtos import CalculateCoherenceCommand
from src.coherence.application.use_cases import CalculateCoherenceUseCase
from src.coherence.domain.category_weights import CoherenceCategory


class TestCalculateCoherenceUseCase:
    """Refers to Suite ID: TS-UA-COH-UC-001"""

    def test_001_execute_with_perfect_project_returns_100_score(self) -> None:
        """Perfect project with all conditions met returns global score 100."""
        command = CalculateCoherenceCommand(
            project_id=uuid4(),
            contract_price=1000.0,
            bom_items=[
                {"amount": 600.0, "budget_line_assigned": True},
                {"amount": 400.0, "budget_line_assigned": True},
            ],
            scope_defined=True,
            schedule_within_contract=True,
            technical_consistent=True,
            legal_compliant=True,
            quality_standard_met=True,
        )

        use_case = CalculateCoherenceUseCase()
        result = use_case.execute(command)

        assert result.global_score == 100
        assert result.project_id == command.project_id

    def test_002_execute_returns_category_scores(self) -> None:
        """Result includes all 6 category scores."""
        command = CalculateCoherenceCommand(
            project_id=uuid4(),
            contract_price=1000.0,
            bom_items=[{"amount": 1000.0, "budget_line_assigned": True}],
        )

        use_case = CalculateCoherenceUseCase()
        result = use_case.execute(command)

        assert len(result.category_scores) == 6
        assert CoherenceCategory.SCOPE in result.category_scores
        assert CoherenceCategory.BUDGET in result.category_scores
        assert CoherenceCategory.TIME in result.category_scores

    def test_003_scope_violation_lowers_scope_score(self) -> None:
        """When scope_defined=False, SCOPE score is 70."""
        command = CalculateCoherenceCommand(
            project_id=uuid4(),
            scope_defined=False,
        )

        use_case = CalculateCoherenceUseCase()
        result = use_case.execute(command)

        assert result.category_scores[CoherenceCategory.SCOPE] == 70
        assert result.global_score < 100

    def test_004_budget_violation_lowers_budget_score(self) -> None:
        """Budget deviation >= 10% triggers R6 violation."""
        command = CalculateCoherenceCommand(
            project_id=uuid4(),
            contract_price=1000.0,
            bom_items=[{"amount": 1200.0, "budget_line_assigned": True}],
        )

        use_case = CalculateCoherenceUseCase()
        result = use_case.execute(command)

        assert result.category_scores[CoherenceCategory.BUDGET] == 0
        assert "R6" in [alert.rule_id for alert in result.alerts]

    def test_005_multiple_violations_generate_multiple_alerts(self) -> None:
        """Multiple violations generate corresponding alerts."""
        command = CalculateCoherenceCommand(
            project_id=uuid4(),
            scope_defined=False,
            legal_compliant=False,
            quality_standard_met=False,
        )

        use_case = CalculateCoherenceUseCase()
        result = use_case.execute(command)

        assert len(result.alerts) >= 3
        rule_ids = {alert.rule_id for alert in result.alerts}
        assert "R11" in rule_ids  # SCOPE
        assert "R1" in rule_ids   # LEGAL
        assert "R17" in rule_ids  # QUALITY

    def test_006_category_details_include_violations(self) -> None:
        """Category details include violation rule IDs."""
        command = CalculateCoherenceCommand(
            project_id=uuid4(),
            scope_defined=False,
        )

        use_case = CalculateCoherenceUseCase()
        result = use_case.execute(command)

        scope_detail = next(
            d for d in result.category_details if d.category == CoherenceCategory.SCOPE
        )
        assert "R11" in scope_detail.violations

    def test_007_custom_weights_affect_global_score(self) -> None:
        """Custom weights change the global score calculation."""
        command = CalculateCoherenceCommand(
            project_id=uuid4(),
            scope_defined=False,  # SCOPE = 70
            custom_weights={
                CoherenceCategory.SCOPE: 0.50,  # High weight on violated category
                CoherenceCategory.BUDGET: 0.10,
                CoherenceCategory.QUALITY: 0.10,
                CoherenceCategory.TECHNICAL: 0.10,
                CoherenceCategory.LEGAL: 0.10,
                CoherenceCategory.TIME: 0.10,
            },
        )

        use_case = CalculateCoherenceUseCase()
        result = use_case.execute(command)

        # With 50% weight on SCOPE (70) and 50% on others (100), score should be ~85
        assert result.global_score < 90

    def test_008_default_weights_used_when_no_custom_weights(self) -> None:
        """When no custom weights provided, use default equal weights."""
        command = CalculateCoherenceCommand(
            project_id=uuid4(),
            custom_weights=None,
        )

        use_case = CalculateCoherenceUseCase()
        result = use_case.execute(command)

        # Default weights should result in score 100 for perfect project
        assert result.global_score == 100

    def test_009_gaming_detection_for_high_score_few_docs(self) -> None:
        """Gaming detected when score >= 90 with <= 5 documents."""
        command = CalculateCoherenceCommand(
            project_id=uuid4(),
            document_count=3,  # Few documents
        )

        use_case = CalculateCoherenceUseCase()
        result = use_case.execute(command)

        # Perfect score (100) with only 3 docs triggers gaming detection
        assert result.is_gaming_detected is True
        assert "suspicious_high_score" in result.gaming_violations

    def test_010_no_gaming_detection_for_high_score_many_docs(self) -> None:
        """No gaming detected when score high with many documents."""
        command = CalculateCoherenceCommand(
            project_id=uuid4(),
            document_count=50,  # Many documents
        )

        use_case = CalculateCoherenceUseCase()
        result = use_case.execute(command)

        # Perfect score (100) with 50 docs is legitimate
        assert result.is_gaming_detected is False

    def test_011_penalty_points_calculated_for_gaming(self) -> None:
        """Penalty points assigned when gaming detected."""
        command = CalculateCoherenceCommand(
            project_id=uuid4(),
            document_count=2,
        )

        use_case = CalculateCoherenceUseCase()
        result = use_case.execute(command)

        if result.is_gaming_detected:
            assert result.penalty_points > 0

    def test_012_all_categories_have_score_details(self) -> None:
        """All 6 categories included in category_details."""
        command = CalculateCoherenceCommand(project_id=uuid4())

        use_case = CalculateCoherenceUseCase()
        result = use_case.execute(command)

        assert len(result.category_details) == 6
        categories = {detail.category for detail in result.category_details}
        assert categories == set(CoherenceCategory)

    def test_013_time_violation_lowers_time_score(self) -> None:
        """When schedule_within_contract=False, TIME score is 70."""
        command = CalculateCoherenceCommand(
            project_id=uuid4(),
            schedule_within_contract=False,
        )

        use_case = CalculateCoherenceUseCase()
        result = use_case.execute(command)

        assert result.category_scores[CoherenceCategory.TIME] == 70

    def test_014_technical_violation_lowers_technical_score(self) -> None:
        """When technical_consistent=False, TECHNICAL score is 70."""
        command = CalculateCoherenceCommand(
            project_id=uuid4(),
            technical_consistent=False,
        )

        use_case = CalculateCoherenceUseCase()
        result = use_case.execute(command)

        assert result.category_scores[CoherenceCategory.TECHNICAL] == 70

    def test_015_legal_violation_lowers_legal_score(self) -> None:
        """When legal_compliant=False, LEGAL score is 70."""
        command = CalculateCoherenceCommand(
            project_id=uuid4(),
            legal_compliant=False,
        )

        use_case = CalculateCoherenceUseCase()
        result = use_case.execute(command)

        assert result.category_scores[CoherenceCategory.LEGAL] == 70

    def test_016_quality_violation_lowers_quality_score(self) -> None:
        """When quality_standard_met=False, QUALITY score is 70."""
        command = CalculateCoherenceCommand(
            project_id=uuid4(),
            quality_standard_met=False,
        )

        use_case = CalculateCoherenceUseCase()
        result = use_case.execute(command)

        assert result.category_scores[CoherenceCategory.QUALITY] == 70
