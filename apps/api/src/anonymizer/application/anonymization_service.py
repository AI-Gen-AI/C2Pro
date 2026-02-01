
import hashlib
from enum import Enum, auto
from typing import Dict, List, Set

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

        # --- State for a single anonymization call ---
        modified_text = text
        # For pseudonymization, we need to map original values to a generated ID
        pseudonym_map: Dict[str, str] = {}
        pseudonym_counter = 1
        
        # Process detections from last to first to avoid messing up indices
        for pii in sorted(detection_result.items, key=lambda p: p.start, reverse=True):
            strategy = config.strategies.get(pii.pii_type, AnonymizationStrategy.NONE)
            
            replacement = ""
            if strategy == AnonymizationStrategy.REDACT:
                replacement = "[REDACTED]"
            
            elif strategy == AnonymizationStrategy.HASH:
                # Use a simple, deterministic SHA-256 hash
                h = hashlib.sha256()
                h.update(pii.text.encode('utf-8'))
                replacement = h.hexdigest()

            elif strategy == AnonymizationStrategy.PSEUDONYMIZE:
                if pii.text not in pseudonym_map:
                    pseudonym_map[pii.text] = f"[PERSON_{pseudonym_counter:03d}]"
                    pseudonym_counter += 1
                replacement = pseudonym_map[pii.text]

            elif strategy == AnonymizationStrategy.NONE:
                # No replacement, continue to the next item
                continue

            # Replace the original PII text with the generated replacement
            modified_text = modified_text[:pii.start] + replacement + modified_text[pii.end:]

        return modified_text
