"""
TS-UC-SEC-ANO-001: Anonymizer PII detection tests.
"""

from __future__ import annotations

import pytest

from src.anonymizer.domain.pii_detector_service import PiiDetectorService, PiiType


@pytest.fixture
def pii_detector() -> PiiDetectorService:
    """Refers to Suite ID: TS-UC-SEC-ANO-001."""
    return PiiDetectorService()


@pytest.mark.asyncio
class TestPiiDetectorService:
    """Refers to Suite ID: TS-UC-SEC-ANO-001."""

    @pytest.mark.parametrize("dni", ["12345678Z", "87654321X"])
    async def test_001_002_detect_dni_valid(self, pii_detector: PiiDetectorService, dni: str) -> None:
        text = f"My DNI is {dni}."
        result = await pii_detector.detect(text)
        assert len(result) == 1
        detected = result.items[0]
        assert detected.pii_type is PiiType.DNI
        assert detected.text == dni
        assert detected.start == text.find(dni)
        assert detected.end == text.find(dni) + len(dni)

    @pytest.mark.parametrize("invalid_dni", ["123456789Z", "1234567Z", "12345678A"])
    async def test_003_004_005_detect_dni_invalid(
        self, pii_detector: PiiDetectorService, invalid_dni: str
    ) -> None:
        text = f"This is not a valid DNI: {invalid_dni}."
        result = await pii_detector.detect(text)
        assert result.is_empty()

    async def test_006_detect_multiple_dnis_in_text(self, pii_detector: PiiDetectorService) -> None:
        text = "User 1: 12345678Z, User 2: 87654321X"
        result = await pii_detector.detect(text)
        assert len(result) == 2
        assert result.counts[PiiType.DNI] == 2

    @pytest.mark.parametrize(
        "email",
        ["test@example.com", "sub.domain@example.co.uk", "user+plus@gmail.com"],
    )
    async def test_007_008_009_detect_email_valid(
        self, pii_detector: PiiDetectorService, email: str
    ) -> None:
        text = f"Contact me at {email}."
        result = await pii_detector.detect(text)
        assert len(result) == 1
        assert result.items[0].pii_type is PiiType.EMAIL
        assert result.items[0].text == email

    async def test_010_detect_email_invalid_no_at(self, pii_detector: PiiDetectorService) -> None:
        text = "This is not an email: test.example.com"
        result = await pii_detector.detect(text)
        assert result.is_empty()

    async def test_011_detect_multiple_emails_in_text(self, pii_detector: PiiDetectorService) -> None:
        text = "Emails are info@example.com and support@company.org."
        result = await pii_detector.detect(text)
        assert len(result) == 2
        assert result.counts[PiiType.EMAIL] == 2

    @pytest.mark.parametrize("phone", ["612345678", "+34612345678", "34612345678", "912345678"])
    async def test_012_013_014_detect_phone_valid(
        self, pii_detector: PiiDetectorService, phone: str
    ) -> None:
        text = f"Call me on {phone}."
        result = await pii_detector.detect(text)
        assert len(result) == 1
        assert result.items[0].pii_type is PiiType.PHONE
        assert result.items[0].text == phone

    async def test_015_detect_phone_invalid_short(self, pii_detector: PiiDetectorService) -> None:
        text = "Invalid phone 12345"
        result = await pii_detector.detect(text)
        assert result.is_empty()

    async def test_016_detect_multiple_phones_in_text(self, pii_detector: PiiDetectorService) -> None:
        text = "My phones are 611223344 and 911223344."
        result = await pii_detector.detect(text)
        assert len(result) == 2
        assert result.counts[PiiType.PHONE] == 2

    @pytest.mark.parametrize("iban", ["ES9121000418450200051332", "DE89370400440532013000"])
    async def test_017_018_detect_iban_valid(self, pii_detector: PiiDetectorService, iban: str) -> None:
        text = f"My IBAN is {iban}"
        result = await pii_detector.detect(text)
        assert len(result) == 1
        assert result.items[0].pii_type is PiiType.IBAN
        assert result.items[0].text == iban

    @pytest.mark.parametrize("invalid_iban", ["ES9121000418450200051333", "DE8937040044053201300", "FR12345"])
    async def test_019_020_detect_iban_invalid(
        self, pii_detector: PiiDetectorService, invalid_iban: str
    ) -> None:
        text = f"This is not a valid IBAN: {invalid_iban}"
        result = await pii_detector.detect(text)
        assert result.is_empty()

    async def test_021_detect_all_pii_types_in_document(self, pii_detector: PiiDetectorService) -> None:
        text = (
            "Contact Juan Perez (DNI: 12345678Z) at test@example.com. "
            "Call 612345678 or transfer to ES9121000418450200051332."
        )
        result = await pii_detector.detect(text)
        assert len(result) == 4
        assert result.counts[PiiType.DNI] == 1
        assert result.counts[PiiType.EMAIL] == 1
        assert result.counts[PiiType.PHONE] == 1
        assert result.counts[PiiType.IBAN] == 1

    async def test_022_detect_no_pii_clean_document(self, pii_detector: PiiDetectorService) -> None:
        text = "This is a clean document with no personal information."
        result = await pii_detector.detect(text)
        assert result.is_empty()

    async def test_023_detect_pii_positions_returned(self, pii_detector: PiiDetectorService) -> None:
        text = "DNI 12345678Z, email foo@example.com and phone 612345678."
        result = await pii_detector.detect(text)
        assert len(result) == 3
        for item in result.items:
            assert item.start >= 0
            assert item.end > item.start
            assert text[item.start:item.end] == item.text

    async def test_024_detect_pii_counts_by_type(self, pii_detector: PiiDetectorService) -> None:
        text = "A 12345678Z B 87654321X C a@b.com D 611223344"
        result = await pii_detector.detect(text)
        assert result.counts[PiiType.DNI] == 2
        assert result.counts[PiiType.EMAIL] == 1
        assert result.counts[PiiType.PHONE] == 1

    async def test_edge_001_pii_in_different_languages(self, pii_detector: PiiDetectorService) -> None:
        text = "Contacto: senor.pablo@example.com y movil 612345678"
        result = await pii_detector.detect(text)
        assert result.counts[PiiType.EMAIL] == 1
        assert result.counts[PiiType.PHONE] == 1

    async def test_edge_002_pii_with_unicode_characters(self, pii_detector: PiiDetectorService) -> None:
        text = "Email: test.ea@u.com"
        result = await pii_detector.detect(text)
        assert len(result) == 1
        assert result.items[0].pii_type is PiiType.EMAIL

    async def test_edge_003_pii_in_html_escaped_text(self, pii_detector: PiiDetectorService) -> None:
        text = "Correo: test@example.com &amp; DNI: 12345678Z"
        result = await pii_detector.detect(text)
        assert result.counts[PiiType.EMAIL] == 1
        assert result.counts[PiiType.DNI] == 1
