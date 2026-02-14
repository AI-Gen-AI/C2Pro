# Path: apps/api/src/coherence/tests/integration/test_i7_risk_scoring_aggregation.py
import pytest
from unittest.mock import MagicMock

# TDD: These imports will fail until the application services, DTOs, and ports are created.
try:
    from src.coherence.application.services import ScoringService
    from src.coherence.application.dtos import (
        Alert,
        AlertCategory,
        AlertSeverity,
        CoherenceResult,
        CategoryWeights,
    )
except ImportError:
    # Define dummy classes to allow the test file to be parsed before implementation
    ScoringService = type("ScoringService", (), {})
    Alert = type("Alert", (), {})
    AlertCategory = type("AlertCategory", (), {})
    AlertSeverity = type("AlertSeverity", (), {})
    CoherenceResult = type("CoherenceResult", (), {})
    CategoryWeights = type("CategoryWeights", (dict,), {})


@pytest.fixture
def mock_alerts_fixture() -> list[Alert]:
    """Provides a fixture of alerts across different categories."""
    return [
        Alert(category=AlertCategory.TIME, severity=AlertSeverity.HIGH),
        Alert(category=AlertCategory.BUDGET, severity=AlertSeverity.MEDIUM),
        Alert(category=AlertCategory.SCOPE, severity=AlertSeverity.LOW),
    ]


@pytest.fixture
def default_weights() -> CategoryWeights:
    """Default weights as per c2pro_master_flow_diagram_v2.2.1.md"""
    return CategoryWeights({
        "SCOPE": 0.20, "BUDGET": 0.20, "QUALITY": 0.15,
        "TECHNICAL": 0.15, "LEGAL": 0.15, "TIME": 0.15
    })


@pytest.fixture
def custom_weights() -> CategoryWeights:
    """A custom weight profile emphasizing budget and time."""
    return CategoryWeights({
        "SCOPE": 0.10, "BUDGET": 0.30, "QUALITY": 0.10,
        "TECHNICAL": 0.10, "LEGAL": 0.10, "TIME": 0.30
    })


@pytest.mark.integration
@pytest.mark.tdd
class TestRiskScoringAndAggregation:
    """
    Test suite for I7 - Risk Scoring + Coherence Score Aggregation.
    """

    @pytest.mark.xfail(reason="[TDD] Drives implementation of scoring logic.", strict=True)
    def test_i7_01_weighted_score_aggregation_with_defaults(
        self, mock_alerts_fixture, default_weights
    ):
        """
        [TEST-I7-01] Verifies weighted score aggregation with default weights.
        """
        # Arrange: This test expects a `ScoringService` to exist.
        scoring_service = ScoringService(default_weights=default_weights)

        # Act: This call will fail until the service and its methods are implemented.
        result: CoherenceResult = scoring_service.calculate_score(mock_alerts_fixture)

        # Assert: The score should be a deterministic, calculated value.
        # (The exact value depends on the internal severity-to-score mapping,
        # which the TDD process will force the team to define).
        assert isinstance(result, CoherenceResult)
        assert 0 <= result.global_score <= 100
        # A placeholder assertion that will be refined once the logic is written.
        assert result.global_score < 90

    @pytest.mark.xfail(reason="[TDD] Drives implementation of custom profiles.", strict=True)
    def test_i7_02_custom_weights_are_applied(
        self, mock_alerts_fixture, default_weights, custom_weights
    ):
        """
        [TEST-I7-02] Verifies custom scoring profiles are correctly applied.
        """
        # Arrange
        scoring_service = ScoringService(default_weights=default_weights)

        # Act
        default_result = scoring_service.calculate_score(mock_alerts_fixture)
        custom_result = scoring_service.calculate_score(
            mock_alerts_fixture, profile_weights=custom_weights
        )

        # Assert
        assert default_result.global_score != custom_result.global_score
        assert custom_result.weights_used == custom_weights

    def test_i7_03_coherence_result_adheres_to_contract(
        self, mock_alerts_fixture, default_weights
    ):
        """
        [TEST-I7-03] Verifies the CoherenceResult DTO adheres to the v2.2.1 contract.
        """
        # Arrange
        scoring_service = ScoringService(default_weights=default_weights)
        # Mock the calculation to return a predictable object for contract testing
        scoring_service.calculate_score = MagicMock(return_value=CoherenceResult(
            global_score=78,
            sub_scores={"SCOPE": 80, "BUDGET": 62, "QUALITY": 85, "TECHNICAL": 72, "LEGAL": 90, "TIME": 75},
            weights_used=default_weights
        ))

        # Act
        result = scoring_service.calculate_score(mock_alerts_fixture)

        # Assert
        assert isinstance(result, CoherenceResult)
        assert hasattr(result, "global_score")
        assert hasattr(result, "sub_scores") and isinstance(result.sub_scores, dict)
        assert hasattr(result, "weights_used")

        # Verify all 6 categories from the spec are present in the sub-scores
        required_categories = {"SCOPE", "BUDGET", "QUALITY", "TECHNICAL", "LEGAL", "TIME"}
        assert required_categories == set(result.sub_scores.keys())

    def test_i7_04_scoring_is_deterministic(self, mock_alerts_fixture, default_weights):
        """
        [TEST-I7-04] Verifies the scoring service is deterministic.
        """
        # Arrange
        scoring_service = ScoringService(default_weights=default_weights)

        # Act
        result1 = scoring_service.calculate_score(mock_alerts_fixture)
        result2 = scoring_service.calculate_score(mock_alerts_fixture)

        # Assert
        assert result1.global_score == result2.global_score
        assert result1.sub_scores == result2.sub_scores