"""
C2Pro - PII Anonymizer Service

This module provides functionalities to detect and anonymize Personally Identifiable Information (PII)
from text, ensuring data privacy before processing by external services or AI models.
It focuses on Spanish DNI, email addresses, phone numbers, and IBANs.
"""

import re


class AnonymizerError(Exception):
    """Custom exception for anonymizer service errors."""

    pass


def _hash_pii(pii_type: str) -> str:
    """Hashes a piece of PII and returns a type-prefixed placeholder."""
    # Using SHA256 for hashing, but actual hashing strategy might vary
    # For a placeholder, a simple type prefix is sufficient.
    return f"[{pii_type.upper()}_HASH]"


def detect_dni(text: str) -> list[tuple[str, str]]:
    """Detects Spanish DNI/NIE patterns in text. Returns (found_text, pii_type)."""
    # Spanish DNI/NIE pattern: 8 digits + 1 letter, or X/Y/Z + 7 digits + 1 letter
    # This regex is a simplification; real DNI validation includes checksum logic.
    patterns = [
        re.compile(r"\b(\d{8}[A-Z])\b", re.IGNORECASE),  # DNI (8 digits + 1 letter)
        re.compile(r"\b([XYZ]\d{7}[A-Z])\b", re.IGNORECASE),  # NIE (X/Y/Z + 7 digits + 1 letter)
    ]
    found_pii = []
    for pattern in patterns:
        for match in pattern.finditer(text):
            found_pii.append((match.group(0), "DNI"))
    return found_pii


def detect_email(text: str) -> list[tuple[str, str]]:
    """Detects email addresses in text. Returns (found_text, pii_type)."""
    # Standard email regex pattern
    pattern = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
    found_pii = []
    for match in pattern.finditer(text):
        found_pii.append((match.group(0), "EMAIL"))
    return found_pii


def detect_phone(text: str) -> list[tuple[str, str]]:
    """Detects Spanish phone numbers in text. Returns (found_text, pii_type)."""
    # Spanish phone numbers typically start with 6, 7, 8, 9 and have 9 digits.
    # Also considering international format +34.
    patterns = [
        re.compile(r"\b(?:\+34|0034)?(?:6|7|8|9)\d{8}\b"),  # +34 or 0034 optional, 9 digits
        re.compile(r"\b(?:\d{3}[-\s]?\d{2}[-\s]?\d{2}[-\s]?\d{2})\b"),  # 9 digits with separators
    ]
    found_pii = []
    for pattern in patterns:
        for match in pattern.finditer(text):
            # Basic filtering to avoid common numbers like years
            if len(match.group(0).replace("-", "").replace(" ", "")) >= 9:
                found_pii.append((match.group(0), "PHONE"))
    return found_pii


def detect_iban(text: str) -> list[tuple[str, str]]:
    """Detects IBANs (International Bank Account Numbers) in text. Returns (found_text, pii_type)."""
    # IBAN pattern: 2 letters (country code) + 2 digits (checksum) + up to 30 alphanumeric characters
    # This regex is simplified and might capture false positives or miss some edge cases.
    pattern = re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[0-9A-Z]{4}){4,7}(?:[ ]?[0-9A-Z]{1,2})?\b")
    found_pii = []
    for match in pattern.finditer(text):
        found_pii.append((match.group(0), "IBAN"))
    return found_pii


def anonymize_text(text: str) -> str:
    """
    Detects and anonymizes PII (DNI, email, phone, IBAN) in the given text.

    Args:
        text: The input text potentially containing PII.

    Returns:
        The text with detected PII replaced by hashed placeholders.
    """
    anonymized_text = text

    # Store detected PII and their types to process them
    all_pii_detections: list[tuple[str, str]] = []

    all_pii_detections.extend(detect_dni(anonymized_text))
    all_pii_detections.extend(detect_email(anonymized_text))
    all_pii_detections.extend(detect_phone(anonymized_text))
    all_pii_detections.extend(detect_iban(anonymized_text))

    # Sort matches by their starting position to avoid issues with overlapping replacements
    # (though current regexes are designed to avoid this for distinct PII types)
    # This step is crucial if patterns can overlap. For simple regexes, order might not matter as much.

    # Replace PII from longest match to shortest to prevent partial replacements
    # For now, given simple distinct regexes, just iterating and replacing is fine.
    # To avoid regex issues and ensure each instance is replaced, we can iterate and replace
    # while keeping track of replaced segments. However, a simpler direct replace can work
    # if regexes are well-behaved.

    # A more robust way would be to get start/end indices for each match and build the
    # anonymized string part by part. For simplicity and given the task context,
    # we'll use re.sub directly for each PII type.

    # Replace DNI
    for pii_text, pii_type in detect_dni(anonymized_text):
        anonymized_text = anonymized_text.replace(pii_text, _hash_pii(pii_text, pii_type))

    # Replace Email
    for pii_text, pii_type in detect_email(anonymized_text):
        anonymized_text = anonymized_text.replace(pii_text, _hash_pii(pii_text, pii_type))

    # Replace Phone
    for pii_text, pii_type in detect_phone(anonymized_text):
        anonymized_text = anonymized_text.replace(pii_text, _hash_pii(pii_text, pii_type))

    # Replace IBAN
    for pii_text, pii_type in detect_iban(anonymized_text):
        anonymized_text = anonymized_text.replace(pii_text, _hash_pii(pii_text, pii_type))

    return anonymized_text


# Example Usage (for testing purposes, if run directly)
if __name__ == "__main__":
    test_text_1 = "El DNI de Juan es 12345678A y su email es juan.perez@example.com. Su teléfono es +34612345678. También tiene el IBAN ES00 0000 0000 0000 0000 0000."
    test_text_2 = "Otro ejemplo con NIE Y1234567B y email test@mail.co.uk. Teléfono: 912 34 56 78 y IBAN ES123456789012345678901234."
    test_text_3 = "No PII here, just some normal text. The year is 2026."
    test_text_4 = (
        "Multiple emails: one@example.com, two@example.org. Multiple phones: 600112233, 931234567."
    )
    test_text_5 = "DNI 12345678A y telefono 666778899"

    print("---" + " Anonymizer Service PII Tests " + "---")

    print("\nOriginal Text 1:")
    print(test_text_1)
    print("Anonymized Text 1:")
    print(anonymize_text(test_text_1))

    print("\nOriginal Text 2:")
    print(test_text_2)
    print("Anonymized Text 2:")
    print(anonymize_text(test_text_2))

    print("\nOriginal Text 3:")
    print(test_text_3)
    print("Anonymized Text 3:")
    print(anonymize_text(test_text_3))

    print("\nOriginal Text 4:")
    print(test_text_4)
    print("Anonymized Text 4:")
    print(anonymize_text(test_text_4))

    print("\nOriginal Text 5:")
    print(test_text_5)
    print("Anonymized Text 5:")
    print(anonymize_text(test_text_5))
