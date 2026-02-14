# Path: apps/api/src/governance/tests/integration/test_i14_safety_hardening.py
import pytest
from unittest.mock import MagicMock
from uuid import uuid4

# TDD: These imports will fail until the application services, DTOs, and ports are created.
try:
    from src.governance.application.services import SafetyPolicyEngine
    from src.governance.application.errors import PolicyViolationError
    # Import example artifacts that the engine will check
    from src.projects.application.dtos import WBSNode
    from src.coherence.application.dtos import Alert
    from src.orchestration.application.dtos import DecisionPackage
    from src.workflows.application.dtos import ReviewStatus
except ImportError:
    # Define dummy classes to allow the test file to be parsed before implementation
    SafetyPolicyEngine = type("SafetyPolicyEngine", (), {})
    PolicyViolationError = type("PolicyViolationError", (Exception,), {})
    WBSNode = type("WBSNode", (), {})
    Alert = type("Alert", (), {})
    DecisionPackage = type("DecisionPackage", (), {})
    ReviewStatus = type("ReviewStatus", (), {})


@pytest.fixture
def safety_engine() -> SafetyPolicyEngine:
    """
    TDD: This fixture expects a `SafetyPolicyEngine` service that enforces
    all governance rules. The service itself does not exist yet.
    """
    # The engine is configured with central thresholds
    return SafetyPolicyEngine(
        min_confidence_threshold=0.7,
        required_disclaimer="C2Pro provides AI-assisted project intelligence for operational decision support. It does not provide legal advice. All legal, contractual, and commercial conclusions require qualified human review and approval."
    )


@pytest.mark.integration
@pytest.mark.critical
@pytest.mark.tdd
class TestGovernanceAndSafetyHardening:
    """
    Test suite for I14 - Governance & Safety Hardening.
    These tests are non-negotiable for production readiness.
    """

    def test_i14_01_engine_blocks_artifact_without_evidence_link(
        self, safety_engine: SafetyPolicyEngine
    ):
        """
        [TEST-I14-01] Verifies the engine blocks artifacts lacking a source citation.
        """
        # Arrange: A generated WBS node with no link back to a source clause.
        hallucinated_item = WBSNode(
            id=uuid4(), name="Potentially Hallucinated Task", evidence_clause_id=None
        )

        # Act & Assert
        with pytest.raises(PolicyViolationError) as excinfo:
            # This call will fail until the engine's `validate` method is implemented.
            safety_engine.validate(hallucinated_item)
        assert "Missing evidence link" in str(excinfo.value)

    def test_i14_02_engine_blocks_low_confidence_artifact(
        self, safety_engine: SafetyPolicyEngine
    ):
        """
        [TEST-I14-02] Verifies the engine blocks artifacts below the confidence threshold.
        """
        # Arrange: A generated alert with a confidence score below the engine's threshold.
        low_confidence_alert = Alert(
            id=uuid4(), message="A low-quality alert", confidence=0.55, evidence_clause_id=uuid4()
        )

        # Act & Assert
        with pytest.raises(PolicyViolationError) as excinfo:
            safety_engine.validate(low_confidence_alert)
        assert "Confidence score below threshold" in str(excinfo.value)

    @pytest.mark.xfail(reason="[TDD] Drives implementation of mandatory human approval gate.", strict=True)
    def test_i14_03_engine_blocks_unapproved_high_impact_artifact(
        self, safety_engine: SafetyPolicyEngine
    ):
        """
        [TEST-I14-03] Verifies the engine blocks high-impact items that are not approved.
        """
        # Arrange: A legal interpretation that is still pending review.
        unapproved_legal_item = WBSNode(
            id=uuid4(),
            name="Legal Interpretation of Clause 5",
            evidence_clause_id=uuid4(),
            confidence=0.99,
            impact_level="HIGH",
            review_status=ReviewStatus.PENDING_REVIEW,
        )

        # Act & Assert
        with pytest.raises(PolicyViolationError) as excinfo:
            safety_engine.validate(unapproved_legal_item)
        assert "Requires human approval" in str(excinfo.value)
        assert False, "Remove this line once the approval check is implemented."

    @pytest.mark.xfail(reason="[TDD] Drives implementation of mandatory legal disclaimer.", strict=True)
    def test_i14_04_final_payload_must_contain_legal_disclaimer(
        self, safety_engine: SafetyPolicyEngine
    ):
        """
        [TEST-I14-04] Verifies the final API payload contract includes the legal disclaimer.
        """
        # Arrange: A final decision package with a missing or incorrect disclaimer.
        package_with_no_disclaimer = DecisionPackage(
            document_id=uuid4(),
            disclaimer=None, # This should be blocked
        )
        package_with_wrong_disclaimer = DecisionPackage(
            document_id=uuid4(),
            disclaimer="This is AI-generated.", # This should also be blocked
        )

        # Act & Assert for missing disclaimer
        with pytest.raises(PolicyViolationError) as excinfo_missing:
            safety_engine.validate(package_with_no_disclaimer)
        assert "Missing or invalid legal disclaimer" in str(excinfo_missing.value)

        # Act & Assert for incorrect disclaimer
        with pytest.raises(PolicyViolationError) as excinfo_wrong:
            safety_engine.validate(package_with_wrong_disclaimer)
        assert "Missing or invalid legal disclaimer" in str(excinfo_wrong.value)

        assert False, "Remove this line once the disclaimer check is implemented."