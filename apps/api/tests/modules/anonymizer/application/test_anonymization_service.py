
import pytest
from unittest.mock import MagicMock, AsyncMock
from enum import Enum, auto
from typing import Dict, List

# These imports will fail as the modules do not exist yet.
from apps.api.src.anonymizer.domain.pii_detector_service import (
    PiiDetectorService,
    DetectedPii,
    PiiType,
    PiiDetectionResult,
)
from apps.api.src.anonymizer.application.anonymization_service import (
    AnonymizationService,
    AnonymizationStrategy,
    AnonymizationConfig,
)


# --- Test Fixtures ---
@pytest.fixture
def mock_pii_detector() -> MagicMock:
    """Fixture for a mocked PiiDetectorService."""
    return MagicMock(spec=PiiDetectorService)

@pytest.fixture
def anonymization_service(mock_pii_detector: MagicMock) -> AnonymizationService:
    """Fixture for the AnonymizationService with a mocked detector."""
    return AnonymizationService(pii_detector=mock_pii_detector)

# --- Test Cases ---
@pytest.mark.asyncio
class TestAnonymizationService:
    """Refers to Suite ID: TS-UC-SEC-ANO-002"""

    # --- Redaction Tests (test_001-004) ---
    async def test_001_redact_dni_to_redacted(self, anonymization_service, mock_pii_detector):
        text = "Client DNI is 12345678Z."
        mock_detections = [DetectedPii("12345678Z", PiiType.DNI, 16, 25)]
        mock_pii_detector.detect.return_value = PiiDetectionResult(mock_detections)
        
        config = AnonymizationConfig(strategies={PiiType.DNI: AnonymizationStrategy.REDACT})
        
        result = await anonymization_service.anonymize(text, config)
        
        assert result == "Client DNI is [REDACTED]."

    async def test_002_003_redact_email_and_phone(self, anonymization_service, mock_pii_detector):
        text = "Contact at test@example.com or call 612345678."
        mock_detections = [
            DetectedPii("test@example.com", PiiType.EMAIL, 12, 28),
            DetectedPii("612345678", PiiType.PHONE, 36, 45)
        ]
        mock_pii_detector.detect.return_value = PiiDetectionResult(mock_detections)
        
        config = AnonymizationConfig(strategies={
            PiiType.EMAIL: AnonymizationStrategy.REDACT,
            PiiType.PHONE: AnonymizationStrategy.REDACT
        })
        
        result = await anonymization_service.anonymize(text, config)
        assert result == "Contact at [REDACTED] or call [REDACTED]."

    # --- Hashing Tests (test_005-008) ---
    async def test_005_hash_dni_deterministic(self, anonymization_service, mock_pii_detector):
        text = "The user is 12345678Z."
        mock_detections = [DetectedPii("12345678Z", PiiType.DNI, 12, 21)]
        mock_pii_detector.detect.return_value = PiiDetectionResult(mock_detections)
        
        config = AnonymizationConfig(strategies={PiiType.DNI: AnonymizationStrategy.HASH})
        
        result1 = await anonymization_service.anonymize(text, config)
        result2 = await anonymization_service.anonymize(text, config)
        
        assert result1 == result2
        assert "12345678Z" not in result1
        assert result1.startswith("The user is ")

    async def test_006_007_hash_consistency(self, anonymization_service, mock_pii_detector):
        text1 = "User A: 12345678Z."
        text2 = "User B: 87654321X."
        text3 = "User C is also 12345678Z."

        # Hash of text1 and text3 should match for the DNI part
        mock_pii_detector.detect.return_value = PiiDetectionResult([DetectedPii("12345678Z", PiiType.DNI, 9, 18)])
        result1 = await anonymization_service.anonymize(text1, AnonymizationConfig({PiiType.DNI: AnonymizationStrategy.HASH}))
        
        mock_pii_detector.detect.return_value = PiiDetectionResult([DetectedPii("12345678Z", PiiType.DNI, 15, 24)])
        result3 = await anonymization_service.anonymize(text3, AnonymizationConfig({PiiType.DNI: AnonymizationStrategy.HASH}))

        hash1 = result1.split(" ")[2]
        hash3 = result3.split(" ")[3]
        assert hash1 == hash3

        # Hash of text2 should be different
        mock_pii_detector.detect.return_value = PiiDetectionResult([DetectedPii("87654321X", PiiType.DNI, 9, 18)])
        result2 = await anonymization_service.anonymize(text2, AnonymizationConfig({PiiType.DNI: AnonymizationStrategy.HASH}))
        hash2 = result2.split(" ")[2]
        assert hash1 != hash2
        
    # --- Pseudonymization Tests (test_009-012) ---
    async def test_009_010_011_pseudonymize_names(self, anonymization_service, mock_pii_detector):
        text = "Participants: John Doe and Jane Smith. John Doe is the lead."
        # We'll use EMAIL PiiType to represent a 'Name' for this test
        mock_detections = [
            DetectedPii("John Doe", PiiType.EMAIL, 14, 22),
            DetectedPii("Jane Smith", PiiType.EMAIL, 27, 37),
            DetectedPii("John Doe", PiiType.EMAIL, 39, 47)
        ]
        mock_pii_detector.detect.return_value = PiiDetectionResult(mock_detections)
        
        config = AnonymizationConfig({PiiType.EMAIL: AnonymizationStrategy.PSEUDONYMIZE})
        result = await anonymization_service.anonymize(text, config)

        assert result == "Participants: [PERSON_001] and [PERSON_002]. [PERSON_001] is the lead."

    # --- Strategy Tests (test_013-016) ---
    async def test_015_strategy_mixed_per_type(self, anonymization_service, mock_pii_detector):
        text = "Contact 12345678Z at test@example.com."
        mock_detections = [
            DetectedPii("12345678Z", PiiType.DNI, 8, 17),
            DetectedPii("test@example.com", PiiType.EMAIL, 21, 37)
        ]
        mock_pii_detector.detect.return_value = PiiDetectionResult(mock_detections)

        config = AnonymizationConfig({
            PiiType.DNI: AnonymizationStrategy.HASH,
            PiiType.EMAIL: AnonymizationStrategy.REDACT,
        })
        
        result = await anonymization_service.anonymize(text, config)
        
        assert "[REDACTED]" in result
        assert "12345678Z" not in result
        assert "test@example.com" not in result
        # Check that it contains something that looks like a hash (non-redacted part)
        assert len(result.split(" ")[1]) > 10 

    async def test_016_strategy_none_keeps_original(self, anonymization_service, mock_pii_detector):
        text = "User DNI is 12345678Z."
        mock_detections = [DetectedPii("12345678Z", PiiType.DNI, 13, 22)]
        mock_pii_detector.detect.return_value = PiiDetectionResult(mock_detections)
        
        # Test with no strategy for DNI
        config = AnonymizationConfig({PiiType.EMAIL: AnonymizationStrategy.REDACT})
        result_no_op = await anonymization_service.anonymize(text, config)
        assert result_no_op == text

        # Test with explicit NONE strategy
        config_none = AnonymizationConfig({PiiType.DNI: AnonymizationStrategy.NONE})
        result_none = await anonymization_service.anonymize(text, config_none)
        assert result_none == text

    # --- Edge Case Tests (test_edge_001-003) ---
    async def test_edge_002_overlapping_pii_positions(self, anonymization_service, mock_pii_detector):
        # A phone number is embedded inside an IBAN
        text = "Account ES612345678901234567890123"
        mock_detections = [
            # The service should prioritize the longer match if it processes smartly,
            # or handle sequential replacement correctly.
            DetectedPii("ES612345678901234567890123", PiiType.IBAN, 8, 32),
            DetectedPii("612345678", PiiType.PHONE, 10, 19),
        ]
        mock_pii_detector.detect.return_value = PiiDetectionResult(mock_detections)

        config = AnonymizationConfig({
            PiiType.IBAN: AnonymizationStrategy.REDACT,
            PiiType.PHONE: AnonymizationStrategy.HASH
        })
        
        # The expected result is that the larger PII (IBAN) is redacted, and the phone number within it is ignored.
        # This is because replacing from back-to-front, the IBAN would be replaced first.
        result = await anonymization_service.anonymize(text, config)
        assert result == "Account [REDACTED]"
        
    async def test_edge_003_empty_text_no_error(self, anonymization_service, mock_pii_detector):
        text = ""
        mock_pii_detector.detect.return_value = PiiDetectionResult([])
        
        config = AnonymizationConfig({})
        result = await anonymization_service.anonymize(text, config)
        
        assert result == ""
        mock_pii_detector.detect.assert_called_once_with("")
