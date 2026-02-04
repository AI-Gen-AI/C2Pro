"""
TS-UC-SEC-ANO-002: Anonymizer strategies tests.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.anonymizer.application.anonymization_service import (
    AnonymizationConfig,
    AnonymizationService,
    AnonymizationStrategy,
)
from src.anonymizer.domain.pii_detector_service import (
    DetectedPii,
    PiiDetectionResult,
    PiiDetectorService,
    PiiType,
)


@pytest.fixture
def detector() -> PiiDetectorService:
    """Refers to Suite ID: TS-UC-SEC-ANO-002."""
    instance = PiiDetectorService()
    instance.detect = AsyncMock()  # type: ignore[method-assign]
    return instance


@pytest.fixture
def service(detector: PiiDetectorService) -> AnonymizationService:
    """Refers to Suite ID: TS-UC-SEC-ANO-002."""
    return AnonymizationService(pii_detector=detector)


@pytest.mark.asyncio
class TestAnonymizationStrategies:
    """Refers to Suite ID: TS-UC-SEC-ANO-002."""

    async def test_001_redact_dni_to_redacted(
        self, service: AnonymizationService, detector: PiiDetectorService
    ) -> None:
        text = "Client DNI is 12345678Z."
        detector.detect.return_value = PiiDetectionResult(
            [DetectedPii("12345678Z", PiiType.DNI, 14, 23)]
        )
        result = await service.anonymize(
            text, AnonymizationConfig(strategies={PiiType.DNI: AnonymizationStrategy.REDACT})
        )
        assert result == "Client DNI is [REDACTED]."

    async def test_002_redact_email_to_redacted(
        self, service: AnonymizationService, detector: PiiDetectorService
    ) -> None:
        text = "Contact test@example.com now."
        detector.detect.return_value = PiiDetectionResult(
            [DetectedPii("test@example.com", PiiType.EMAIL, 8, 24)]
        )
        result = await service.anonymize(
            text, AnonymizationConfig(strategies={PiiType.EMAIL: AnonymizationStrategy.REDACT})
        )
        assert result == "Contact [REDACTED] now."

    async def test_003_redact_phone_to_redacted(
        self, service: AnonymizationService, detector: PiiDetectorService
    ) -> None:
        text = "Phone 612345678"
        detector.detect.return_value = PiiDetectionResult(
            [DetectedPii("612345678", PiiType.PHONE, 6, 15)]
        )
        result = await service.anonymize(
            text, AnonymizationConfig(strategies={PiiType.PHONE: AnonymizationStrategy.REDACT})
        )
        assert result == "Phone [REDACTED]"

    async def test_004_redact_multiple_pii_all_redacted(
        self, service: AnonymizationService, detector: PiiDetectorService
    ) -> None:
        text = "DNI 12345678Z email test@example.com"
        detector.detect.return_value = PiiDetectionResult(
            [
                DetectedPii("12345678Z", PiiType.DNI, 4, 13),
                DetectedPii("test@example.com", PiiType.EMAIL, 20, 36),
            ]
        )
        result = await service.anonymize(
            text,
            AnonymizationConfig(
                strategies={
                    PiiType.DNI: AnonymizationStrategy.REDACT,
                    PiiType.EMAIL: AnonymizationStrategy.REDACT,
                }
            ),
        )
        assert result == "DNI [REDACTED] email [REDACTED]"

    async def test_005_hash_dni_deterministic(
        self, service: AnonymizationService, detector: PiiDetectorService
    ) -> None:
        text = "DNI 12345678Z"
        detector.detect.return_value = PiiDetectionResult(
            [DetectedPii("12345678Z", PiiType.DNI, 4, 13)]
        )
        cfg = AnonymizationConfig(strategies={PiiType.DNI: AnonymizationStrategy.HASH})
        r1 = await service.anonymize(text, cfg)
        r2 = await service.anonymize(text, cfg)
        assert r1 == r2
        assert "12345678Z" not in r1

    async def test_006_hash_same_value_same_hash(
        self, service: AnonymizationService, detector: PiiDetectorService
    ) -> None:
        detector.detect.return_value = PiiDetectionResult(
            [DetectedPii("12345678Z", PiiType.DNI, 4, 13)]
        )
        cfg = AnonymizationConfig(strategies={PiiType.DNI: AnonymizationStrategy.HASH})
        a = await service.anonymize("DNI 12345678Z", cfg)
        b = await service.anonymize("ID: 12345678Z", cfg)
        assert a.split(" ", 1)[1] == b.split(" ", 1)[1]

    async def test_007_hash_different_values_different_hash(
        self, service: AnonymizationService, detector: PiiDetectorService
    ) -> None:
        cfg = AnonymizationConfig(strategies={PiiType.DNI: AnonymizationStrategy.HASH})
        detector.detect.return_value = PiiDetectionResult(
            [DetectedPii("12345678Z", PiiType.DNI, 4, 13)]
        )
        a = await service.anonymize("DNI 12345678Z", cfg)
        detector.detect.return_value = PiiDetectionResult(
            [DetectedPii("87654321X", PiiType.DNI, 4, 13)]
        )
        b = await service.anonymize("DNI 87654321X", cfg)
        assert a != b

    async def test_008_hash_irreversible_validation(
        self, service: AnonymizationService, detector: PiiDetectorService
    ) -> None:
        detector.detect.return_value = PiiDetectionResult(
            [DetectedPii("test@example.com", PiiType.EMAIL, 6, 22)]
        )
        result = await service.anonymize(
            "Email test@example.com",
            AnonymizationConfig(strategies={PiiType.EMAIL: AnonymizationStrategy.HASH}),
        )
        assert "test@example.com" not in result
        assert len(result.split(" ", 1)[1]) == 64

    async def test_009_pseudonymize_name_to_persona_001(
        self, service: AnonymizationService, detector: PiiDetectorService
    ) -> None:
        text = "Actor John Doe"
        detector.detect.return_value = PiiDetectionResult(
            [DetectedPii("John Doe", PiiType.EMAIL, 6, 14)]
        )
        result = await service.anonymize(
            text, AnonymizationConfig(strategies={PiiType.EMAIL: AnonymizationStrategy.PSEUDONYMIZE})
        )
        assert result == "Actor [PERSON_001]"

    async def test_010_pseudonymize_consistent_same_name(
        self, service: AnonymizationService, detector: PiiDetectorService
    ) -> None:
        text = "John Doe meets John Doe"
        detector.detect.return_value = PiiDetectionResult(
            [
                DetectedPii("John Doe", PiiType.EMAIL, 0, 8),
                DetectedPii("John Doe", PiiType.EMAIL, 15, 23),
            ]
        )
        result = await service.anonymize(
            text, AnonymizationConfig(strategies={PiiType.EMAIL: AnonymizationStrategy.PSEUDONYMIZE})
        )
        assert result == "[PERSON_001] meets [PERSON_001]"

    async def test_011_pseudonymize_different_names_different_ids(
        self, service: AnonymizationService, detector: PiiDetectorService
    ) -> None:
        text = "John Doe and Jane Smith"
        detector.detect.return_value = PiiDetectionResult(
            [
                DetectedPii("John Doe", PiiType.EMAIL, 0, 8),
                DetectedPii("Jane Smith", PiiType.EMAIL, 13, 23),
            ]
        )
        result = await service.anonymize(
            text, AnonymizationConfig(strategies={PiiType.EMAIL: AnonymizationStrategy.PSEUDONYMIZE})
        )
        assert result == "[PERSON_001] and [PERSON_002]"

    async def test_012_pseudonymize_in_context_preserved(
        self, service: AnonymizationService, detector: PiiDetectorService
    ) -> None:
        text = "Owner John Doe approved budget."
        detector.detect.return_value = PiiDetectionResult(
            [DetectedPii("John Doe", PiiType.EMAIL, 6, 14)]
        )
        result = await service.anonymize(
            text, AnonymizationConfig(strategies={PiiType.EMAIL: AnonymizationStrategy.PSEUDONYMIZE})
        )
        assert result == "Owner [PERSON_001] approved budget."

    async def test_013_strategy_by_pii_type_default(
        self, service: AnonymizationService, detector: PiiDetectorService
    ) -> None:
        text = "DNI 12345678Z"
        detector.detect.return_value = PiiDetectionResult(
            [DetectedPii("12345678Z", PiiType.DNI, 4, 13)]
        )
        result = await service.anonymize(text, AnonymizationConfig())
        assert result == text

    async def test_014_strategy_by_tenant_config(
        self, service: AnonymizationService, detector: PiiDetectorService
    ) -> None:
        text = "Email test@example.com"
        detector.detect.return_value = PiiDetectionResult(
            [DetectedPii("test@example.com", PiiType.EMAIL, 6, 22)]
        )
        tenant_cfg = AnonymizationConfig(strategies={PiiType.EMAIL: AnonymizationStrategy.HASH})
        result = await service.anonymize(text, tenant_cfg)
        assert result.startswith("Email ")
        assert "test@example.com" not in result

    async def test_015_strategy_mixed_per_type(
        self, service: AnonymizationService, detector: PiiDetectorService
    ) -> None:
        text = "DNI 12345678Z email test@example.com"
        detector.detect.return_value = PiiDetectionResult(
            [
                DetectedPii("12345678Z", PiiType.DNI, 4, 13),
                DetectedPii("test@example.com", PiiType.EMAIL, 20, 36),
            ]
        )
        result = await service.anonymize(
            text,
            AnonymizationConfig(
                strategies={
                    PiiType.DNI: AnonymizationStrategy.HASH,
                    PiiType.EMAIL: AnonymizationStrategy.REDACT,
                }
            ),
        )
        assert "[REDACTED]" in result
        assert "12345678Z" not in result
        assert "test@example.com" not in result

    async def test_016_strategy_none_keeps_original(
        self, service: AnonymizationService, detector: PiiDetectorService
    ) -> None:
        text = "DNI 12345678Z"
        detector.detect.return_value = PiiDetectionResult(
            [DetectedPii("12345678Z", PiiType.DNI, 4, 13)]
        )
        result = await service.anonymize(
            text, AnonymizationConfig(strategies={PiiType.DNI: AnonymizationStrategy.NONE})
        )
        assert result == text

    async def test_edge_001_nested_pii_in_pii(
        self, service: AnonymizationService, detector: PiiDetectorService
    ) -> None:
        text = "Outer test@example.com and inner example.com"
        detector.detect.return_value = PiiDetectionResult(
            [
                DetectedPii("test@example.com", PiiType.EMAIL, 6, 22),
                DetectedPii("example.com", PiiType.EMAIL, 11, 22),
            ]
        )
        result = await service.anonymize(
            text, AnonymizationConfig(strategies={PiiType.EMAIL: AnonymizationStrategy.REDACT})
        )
        assert result == "Outer [REDACTED] and inner example.com"

    async def test_edge_002_overlapping_pii_positions(
        self, service: AnonymizationService, detector: PiiDetectorService
    ) -> None:
        text = "Account ES612345678901234567890123"
        detector.detect.return_value = PiiDetectionResult(
            [
                DetectedPii("612345678", PiiType.PHONE, 10, 19),
                DetectedPii("ES612345678901234567890123", PiiType.IBAN, 8, 34),
            ]
        )
        result = await service.anonymize(
            text,
            AnonymizationConfig(
                strategies={
                    PiiType.PHONE: AnonymizationStrategy.HASH,
                    PiiType.IBAN: AnonymizationStrategy.REDACT,
                }
            ),
        )
        assert result == "Account [REDACTED]"

    async def test_edge_003_empty_text_no_error(
        self, service: AnonymizationService, detector: PiiDetectorService
    ) -> None:
        detector.detect.return_value = PiiDetectionResult([])
        result = await service.anonymize("", AnonymizationConfig())
        assert result == ""
        detector.detect.assert_not_called()
