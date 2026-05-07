"""Test Suite ID: TASK-OPS-DOCFLOW-004.

Validate the sanitized real-document corpus manifest used by the real document
operability gate.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CORPUS_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "documents" / "real"
MANIFEST_PATH = CORPUS_DIR / "manifest.yaml"
REQUIRED_MANIFEST_FIELDS = {
    "document_id",
    "filename",
    "document_type",
    "language",
    "expected_upload",
    "expected_min_text_chars",
    "expected_clause_categories",
    "expected_risk_categories",
    "expected_score_range",
    "expected_alerts",
    "pii_expectations",
}
REQUIRED_DOCUMENT_TYPES = {
    "construction_contract",
    "budget_scope",
    "schedule_program",
    "contradiction_heavy",
    "unsupported",
}
ALLOWED_SUFFIXES = {".pdf", ".docx", ".txt", ".bin"}


def _load_manifest() -> list[dict[str, Any]]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_real_document_corpus_manifest_defines_required_inventory() -> None:
    manifest = _load_manifest()

    assert len(manifest) >= 5
    assert {entry["document_type"] for entry in manifest} >= REQUIRED_DOCUMENT_TYPES

    for entry in manifest:
        assert set(entry) >= REQUIRED_MANIFEST_FIELDS
        assert entry["document_id"].startswith("real-doc-")
        assert entry["language"] in {"en", "es"}
        assert entry["expected_min_text_chars"] >= 100
        assert entry["expected_clause_categories"]
        assert isinstance(entry["expected_risk_categories"], list)
        assert len(entry["expected_score_range"]) == 2
        assert entry["expected_score_range"][0] <= entry["expected_score_range"][1]
        assert isinstance(entry["expected_alerts"], list)
        assert isinstance(entry["pii_expectations"], dict)


def test_real_document_corpus_files_are_real_artifacts_not_inline_text() -> None:
    manifest = _load_manifest()

    for entry in manifest:
        fixture_path = CORPUS_DIR / entry["filename"]

        assert fixture_path.exists()
        assert fixture_path.suffix.lower() in ALLOWED_SUFFIXES
        assert fixture_path.stat().st_size > 32

        content = fixture_path.read_bytes()
        if fixture_path.suffix.lower() == ".pdf":
            assert content.startswith(b"%PDF-")
            assert b"%%EOF" in content
        elif fixture_path.suffix.lower() == ".docx":
            assert content.startswith(b"PK")
            assert b"word/document.xml" in content
        elif fixture_path.suffix.lower() == ".txt":
            assert len(content.decode("utf-8").split()) >= 20
