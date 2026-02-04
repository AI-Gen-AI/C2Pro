"""
TS-UC-SEC-ANO-002: Anonymization strategies application service.
"""

import hashlib
from enum import Enum, auto
from typing import Dict, List

from pydantic import BaseModel, Field

# Assuming the PII detection components are available from the domain layer
from ..domain.pii_detector_service import (
    PiiDetectorService,
    PiiType,
    PiiDetectionResult,
)


class AnonymizationStrategy(Enum):
    """Enumeration of available anonymization strategies."""
    REDACT = auto()        # Replace with a fixed placeholder like '[REDACTED]'
    HASH = auto()          # Replace with a deterministic hash of the original value
    PSEUDONYMIZE = auto()  # Replace with a consistent pseudonym like '[PERSON_001]'
    NONE = auto()          # Do not anonymize, keep the original value


class AnonymizationConfig(BaseModel):
    """
    Configuration defining which anonymization strategy to apply for each PII type.
    If a PII type is not in the dictionary, it will not be anonymized.
    """
    strategies: Dict[PiiType, AnonymizationStrategy] = Field(default_factory=dict)


class AnonymizationService:
    """
    An application service that orchestrates the detection and anonymization of PII in text.
    It uses a PII detector to find sensitive information and then applies various
    anonymization strategies based on a provided configuration.
    """

    def __init__(self, pii_detector: PiiDetectorService):
        if not isinstance(pii_detector, PiiDetectorService):
            raise TypeError("pii_detector must be an instance of PiiDetectorService")
        self.pii_detector = pii_detector

    async def anonymize(self, text: str, config: AnonymizationConfig) -> str:
        """
        Detects and anonymizes PII in the given text according to the specified config.

        Args:
            text: The input string to anonymize.
            config: The configuration specifying the anonymization strategies.

        Returns:
            The anonymized string.
        """
        if not text:
            return ""

        detection_result = await self.pii_detector.detect(text)
        if detection_result.is_empty():
            return text

        actionable_items = self._select_non_overlapping_items(
            detection_result.items, config.strategies
        )
        if not actionable_items:
            return text

        replacements: dict[tuple[int, int], str] = {}
        pseudonym_map: Dict[str, str] = {}
        pseudonym_counter = 1

        # Build replacements in natural text order to keep pseudonym IDs stable.
        for pii in sorted(actionable_items, key=lambda p: p.start):
            strategy = config.strategies.get(pii.pii_type, AnonymizationStrategy.NONE)
            if strategy == AnonymizationStrategy.REDACT:
                replacements[(pii.start, pii.end)] = "[REDACTED]"
            elif strategy == AnonymizationStrategy.HASH:
                h = hashlib.sha256()
                h.update(pii.text.encode("utf-8"))
                replacements[(pii.start, pii.end)] = h.hexdigest()
            elif strategy == AnonymizationStrategy.PSEUDONYMIZE:
                if pii.text not in pseudonym_map:
                    pseudonym_map[pii.text] = f"[PERSON_{pseudonym_counter:03d}]"
                    pseudonym_counter += 1
                replacements[(pii.start, pii.end)] = pseudonym_map[pii.text]

        modified_text = text
        # Apply from right to left so original indexes remain valid.
        for pii in sorted(actionable_items, key=lambda p: p.start, reverse=True):
            replacement = replacements[(pii.start, pii.end)]
            modified_text = modified_text[:pii.start] + replacement + modified_text[pii.end:]

        return modified_text

    @staticmethod
    def _select_non_overlapping_items(
        items: List["DetectedPii"],
        strategies: Dict[PiiType, AnonymizationStrategy],
    ) -> List["DetectedPii"]:
        """
        Keep only actionable, non-overlapping detections.
        For overlaps, the longest match wins.
        """
        actionable = [
            item
            for item in items
            if strategies.get(item.pii_type, AnonymizationStrategy.NONE) != AnonymizationStrategy.NONE
        ]
        if not actionable:
            return []

        chosen: List["DetectedPii"] = []
        for candidate in sorted(
            actionable,
            key=lambda item: (-(item.end - item.start), item.start),
        ):
            overlaps = any(
                not (candidate.end <= kept.start or candidate.start >= kept.end) for kept in chosen
            )
            if not overlaps:
                chosen.append(candidate)
        return chosen
