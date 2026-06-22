"""Traceability tests for LEGAL pilot claim extraction.

Refers to Suite ID: TS-UD-EVI-LEGAL-001.
"""
from __future__ import annotations

import inspect

import src.evidence.legal as legal_module
import src.evidence.legal.adapter as adapter_module
import src.evidence.legal.schemas as schemas_module


def test_legal_pilot_modules_declare_suite_id() -> None:
    expected_suite_id = "TS-UD-EVI-LEGAL-001"

    assert expected_suite_id in (inspect.getdoc(legal_module) or "")
    assert expected_suite_id in (inspect.getdoc(schemas_module) or "")
    assert expected_suite_id in (inspect.getdoc(adapter_module) or "")
