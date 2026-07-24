"""TS-UC-SEC-ANO-002: AnonymizationService branch coverage — empty detection, constructor guard."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.anonymizer.application.anonymization_service import (
    AnonymizationConfig,
    AnonymizationService,
)
from src.anonymizer.domain.pii_detector_service import (
    PiiDetectionResult,
    PiiDetectorService,
)


@pytest.fixture
def detector() -> PiiDetectorService:
    instance = PiiDetectorService()
    instance.detect = AsyncMock()
    return instance


@pytest.fixture
def service(detector: PiiDetectorService) -> AnonymizationService:
    return AnonymizationService(pii_detector=detector)


@pytest.mark.asyncio
async def test_anonymize_empty_detection_returns_original(
    service: AnonymizationService, detector: PiiDetectorService
) -> None:
    """is_empty() True → returns original text unchanged (line 62 branch)."""
    detector.detect.return_value = PiiDetectionResult([])

    result = await service.anonymize(
        "text with no pii", AnonymizationConfig()
    )

    assert result == "text with no pii"


def test_anonymizer_invalid_constructor_raises() -> None:
    """Pass non-PiiDetectorService to constructor → TypeError."""
    with pytest.raises(TypeError, match="pii_detector must be an instance of PiiDetectorService"):
        AnonymizationService(pii_detector="not a detector")  # type: ignore[arg-type]
