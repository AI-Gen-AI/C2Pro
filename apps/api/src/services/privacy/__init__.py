"""
C2Pro - Privacy Services Package

This package provides services for handling sensitive data in compliance
with GDPR and other privacy regulations.

Services:
- PiiAnonymizerService: Anonymizes personally identifiable information
"""

from .anonymizer import (
    PiiAnonymizerService,
    get_anonymizer,
    AnonymizedResult,
    anonymize_text_simple,
    deanonymize_text_simple,
)

__all__ = [
    "PiiAnonymizerService",
    "get_anonymizer",
    "AnonymizedResult",
    "anonymize_text_simple",
    "deanonymize_text_simple",
]
