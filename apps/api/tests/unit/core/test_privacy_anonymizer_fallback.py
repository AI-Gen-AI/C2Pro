"""TS-SEC-PII-FALLBACK-001

Regression checks for regex-based PII anonymization fallback.
"""

from __future__ import annotations

import importlib


def test_anonymizer_fallback_redacts_email_and_dni_without_presidio(monkeypatch) -> None:
    anonymizer_module = importlib.import_module("src.core.privacy.anonymizer")

    monkeypatch.setattr(anonymizer_module, "PRESIDIO_AVAILABLE", False)
    monkeypatch.setattr(anonymizer_module.PiiAnonymizerService, "_instance", None)
    monkeypatch.setattr(anonymizer_module.PiiAnonymizerService, "_initialized", False)

    anonymizer = anonymizer_module.PiiAnonymizerService()
    result = anonymizer.anonymize_document("Juan Perez <juan@empresa.com> con DNI 12345678Z")

    assert result.anonymized_text != "Juan Perez <juan@empresa.com> con DNI 12345678Z"
    assert "<EMAIL_ADDRESS_1>" in result.anonymized_text
    assert "<SPANISH_ID_1>" in result.anonymized_text
    assert result.mapping["<EMAIL_ADDRESS_1>"] == "juan@empresa.com"
    assert result.mapping["<SPANISH_ID_1>"] == "12345678Z"
