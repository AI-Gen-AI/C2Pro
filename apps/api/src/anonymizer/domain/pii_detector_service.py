"""
TS-UC-SEC-ANO-001: PII detector domain service.
"""

import re
from enum import Enum, auto
from typing import List, NamedTuple, Dict

class PiiType(Enum):
    """Enumeration of detectable Personally Identifiable Information (PII) types."""
    DNI = auto()
    EMAIL = auto()
    PHONE = auto()
    IBAN = auto()

class DetectedPii(NamedTuple):
    """Represents a single piece of detected PII."""
    text: str
    pii_type: PiiType
    start: int
    end: int

class PiiDetectionResult:
    """Represents the outcome of a PII detection scan."""
    def __init__(self, items: List[DetectedPii]):
        self.items = items
    
    def __len__(self) -> int:
        return len(self.items)

    def is_empty(self) -> bool:
        """Checks if any PII was detected."""
        return len(self.items) == 0

    @property
    def counts(self) -> Dict[PiiType, int]:
        """Returns a dictionary with the count of each detected PII type."""
        counts_dict = {pii_type: 0 for pii_type in PiiType}
        for item in self.items:
            counts_dict[item.pii_type] += 1
        return counts_dict

class PiiDetectorService:
    """
    A domain service to detect Personally Identifiable Information (PII) in text.
    This service uses regular expressions and validation logic to find and classify PII.
    """
    
    # --- Regular Expressions for PII Detection ---
    _DNI_REGEX = re.compile(r'\b\d{8}[A-Z]\b')
    # A more comprehensive email regex that supports unicode and plus notation
    _EMAIL_REGEX = re.compile(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b', re.UNICODE)
    # Spanish phone numbers (9 digits), with optional country code (+34 or 34)
    _PHONE_REGEX = re.compile(r'(?<!\w)(?:\+34|34)?[6789]\d{8}\b')
    # General IBAN format (Country code + 2 check digits + up to 30 alphanumeric chars)
    _IBAN_REGEX = re.compile(r'\b[A-Z]{2}\d{2}[a-zA-Z0-9]{1,30}\b')

    # --- Checksum validation tables ---
    _DNI_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"
    
    def _is_valid_dni(self, dni: str) -> bool:
        """Validates a Spanish DNI based on its checksum letter."""
        if len(dni) != 9:
            return False
        number_part = dni[:8]
        letter_part = dni[8].upper()
        if not number_part.isdigit():
            return False
        return self._DNI_LETTERS[int(number_part) % 23] == letter_part

    def _is_valid_iban(self, iban: str) -> bool:
        """Validates IBAN using MOD-97-10 checksum."""
        normalized = iban.replace(" ", "").upper()
        if len(normalized) < 15 or len(normalized) > 34:
            return False
        if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]+", normalized):
            return False

        rearranged = normalized[4:] + normalized[:4]
        numeric = ""
        for char in rearranged:
            if char.isdigit():
                numeric += char
            else:
                numeric += str(ord(char) - 55)  # A=10, B=11, ..., Z=35

        remainder = 0
        for digit in numeric:
            remainder = (remainder * 10 + int(digit)) % 97
        return remainder == 1

    async def detect(self, text: str) -> PiiDetectionResult:
        """
        Detects all supported PII types in the given text.

        Args:
            text: The input string to scan.

        Returns:
            A PiiDetectionResult object containing all found PII.
        """
        detected_items = []

        # Find DNI
        for match in self._DNI_REGEX.finditer(text):
            if self._is_valid_dni(match.group(0)):
                detected_items.append(DetectedPii(
                    text=match.group(0),
                    pii_type=PiiType.DNI,
                    start=match.start(),
                    end=match.end()
                ))

        # Find Email
        for match in self._EMAIL_REGEX.finditer(text):
            detected_items.append(DetectedPii(
                text=match.group(0),
                pii_type=PiiType.EMAIL,
                start=match.start(),
                end=match.end()
            ))

        # Find Phone
        for match in self._PHONE_REGEX.finditer(text):
            detected_items.append(DetectedPii(
                text=match.group(0),
                pii_type=PiiType.PHONE,
                start=match.start(),
                end=match.end()
            ))
        
        # Find IBAN
        for match in self._IBAN_REGEX.finditer(text):
            if self._is_valid_iban(match.group(0)):
                 detected_items.append(DetectedPii(
                    text=match.group(0),
                    pii_type=PiiType.IBAN,
                    start=match.start(),
                    end=match.end()
                ))

        # Sort by appearance order
        detected_items.sort(key=lambda item: item.start)

        return PiiDetectionResult(items=detected_items)
