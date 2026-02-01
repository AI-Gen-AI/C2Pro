
import pytest
from enum import Enum, auto
from typing import List, NamedTuple

# This import will fail as the modules do not exist yet.
# These classes are temporarily defined below for test writing purposes.
from apps.api.src.anonymizer.domain.pii_detector_service import (
    PiiDetectorService,
    DetectedPii,
    PiiType,
    PiiDetectionResult,
)


# --- Temporary definitions for test development. Will be moved to implementation. ---
class TempPiiType(Enum):
    DNI = auto()
    EMAIL = auto()
    PHONE = auto()
    IBAN = auto()

class TempDetectedPii(NamedTuple):
    text: str
    pii_type: TempPiiType
    start: int
    end: int

class TempPiiDetectionResult:
    def __init__(self, items: List[TempDetectedPii]):
        self.items = items
    
    def __len__(self):
        return len(self.items)

    def is_empty(self) -> bool:
        return len(self.items) == 0

    @property
    def counts(self) -> dict:
        counts_dict = {pii_type: 0 for pii_type in TempPiiType}
        for item in self.items:
            counts_dict[item.pii_type] += 1
        return counts_dict

# --- Test Cases ---
@pytest.mark.asyncio
class TestPiiDetectorService:
    """Refers to Suite ID: TS-UC-SEC-ANO-001"""

    @pytest.fixture
    def pii_detector(self) -> PiiDetectorService:
        # This is a domain service with no dependencies.
        # We replace the temp classes with the real ones once they exist.
        service = PiiDetectorService()
        service.PiiType = TempPiiType
        service.DetectedPii = TempDetectedPii
        service.PiiDetectionResult = TempPiiDetectionResult
        return service

    # --- DNI Tests (test_001-006) ---
    @pytest.mark.parametrize("dni", ["12345678Z", "87654321X"])
    async def test_001_002_detect_dni_valid(self, pii_detector, dni):
        text = f"My DNI is {dni}."
        result = await pii_detector.detect(text)
        assert len(result) == 1
        detected = result.items[0]
        assert detected.pii_type == pii_detector.PiiType.DNI
        assert detected.text == dni
        assert detected.start == text.find(dni)
        assert detected.end == text.find(dni) + len(dni)

    @pytest.mark.parametrize("invalid_dni", ["123456789Z", "1234567Z", "12345678A"])
    async def test_003_004_005_detect_dni_invalid(self, pii_detector, invalid_dni):
        text = f"This is not a valid DNI: {invalid_dni}."
        result = await pii_detector.detect(text)
        assert result.is_empty()

    async def test_006_detect_multiple_dnis_in_text(self, pii_detector):
        text = "User 1: 12345678Z, User 2: 87654321X"
        result = await pii_detector.detect(text)
        assert len(result) == 2
        assert result.counts[pii_detector.PiiType.DNI] == 2
        assert result.items[0].text == "12345678Z"
        assert result.items[1].text == "87654321X"

    # --- Email Tests (test_007-011) ---
    @pytest.mark.parametrize("email", ["test@example.com", "sub.domain@example.co.uk", "user+plus@gmail.com"])
    async def test_007_008_009_detect_email_valid(self, pii_detector, email):
        text = f"Contact me at {email}."
        result = await pii_detector.detect(text)
        assert len(result) == 1
        assert result.items[0].pii_type == pii_detector.PiiType.EMAIL
        assert result.items[0].text == email

    async def test_010_detect_email_invalid_no_at(self, pii_detector):
        text = "This is not an email: test.example.com"
        result = await pii_detector.detect(text)
        assert result.is_empty()

    async def test_011_detect_multiple_emails_in_text(self, pii_detector):
        text = "Emails are info@example.com and support@company.org."
        result = await pii_detector.detect(text)
        assert len(result) == 2
        assert result.counts[pii_detector.PiiType.EMAIL] == 2

    # --- Phone Tests (test_012-016) ---
    @pytest.mark.parametrize("phone", ["612345678", "+34612345678", "34612345678", "912345678"])
    async def test_012_013_014_detect_phone_valid(self, pii_detector, phone):
        text = f"Call me on {phone}."
        result = await pii_detector.detect(text)
        assert len(result) == 1
        assert result.items[0].pii_type == pii_detector.PiiType.PHONE
        assert result.items[0].text == phone

    async def test_015_detect_phone_invalid_short(self, pii_detector):
        text = "Invalid phone 12345"
        result = await pii_detector.detect(text)
        assert result.is_empty()

    async def test_016_detect_multiple_phones_in_text(self, pii_detector):
        text = "My phones are 611223344 and 911223344."
        result = await pii_detector.detect(text)
        assert len(result) == 2
        assert result.counts[pii_detector.PiiType.PHONE] == 2

    # --- IBAN Tests (test_017-020) ---
    @pytest.mark.parametrize("iban", ["ES9121000418450200051332", "DE89370400440532013000"])
    async def test_017_018_detect_iban_valid(self, pii_detector, iban):
        text = f"My IBAN is {iban}"
        result = await pii_detector.detect(text)
        assert len(result) == 1
        assert result.items[0].pii_type == pii_detector.PiiType.IBAN
        assert result.items[0].text == iban

    @pytest.mark.parametrize("invalid_iban", ["ES9121000418450200051333", "DE8937040044053201300", "FR12345"])
    async def test_019_020_detect_iban_invalid(self, pii_detector, invalid_iban):
        text = f"This is not a valid IBAN: {invalid_iban}"
        result = await pii_detector.detect(text)
        assert result.is_empty()
    
    # --- Composite and Structure Tests (test_021-024) ---
    async def test_021_detect_all_pii_types_in_document(self, pii_detector):
        """Tests detection of all PII types in one document and validates positions and counts."""
        text = (
            "Contact Juan Pérez (DNI: 12345678Z) at test@example.com. "
            "Call 612345678 or transfer to ES9121000418450200051332."
        )
        result = await pii_detector.detect(text)

        assert len(result) == 4
        
        # Test 024: Validate counts by type
        expected_counts = {
            pii_detector.PiiType.DNI: 1,
            pii_detector.PiiType.EMAIL: 1,
            pii_detector.PiiType.PHONE: 1,
            pii_detector.PiiType.IBAN: 1,
        }
        assert result.counts == expected_counts

        # Test 023: Validate positions are returned correctly
        for item in result.items:
            assert item.start >= 0
            assert item.end > item.start
            assert text[item.start:item.end] == item.text

    async def test_022_detect_no_pii_clean_document(self, pii_detector):
        text = "This is a clean document with no personal information."
        result = await pii_detector.detect(text)
        assert result.is_empty()

    # --- Edge Case Tests ---
    async def test_edge_001_pii_in_different_languages(self, pii_detector):
        """Test with non-ASCII characters, which regex should handle."""
        text = "Contact José at señor.pablo@example.com"
        result = await pii_detector.detect(text)
        assert len(result) == 1
        assert result.items[0].text == "señor.pablo@example.com"

    async def test_edge_002_pii_with_unicode_characters(self, pii_detector):
        """Test with unicode characters in email."""
        text = "Email: test.éà@ü.com"
        result = await pii_detector.detect(text)
        assert len(result) == 1
        assert result.items[0].pii_type == pii_detector.PiiType.EMAIL
        assert result.items[0].text == "test.éà@ü.com"
