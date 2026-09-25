"""TS-UT-PJ01-FIXTURE-002: the PJ-01 Contract A fixture is predictable through the REAL pipeline.

PJ-01 asserts six-category Health on a real upload, so the fixture's expectations must be
what production code actually derives, not what a reviewer hopes it derives. This test feeds
the committed PDF through the same deterministic steps ingestion and Health use:

- ``PDFFileParser.extract_text_and_offsets`` (the parser the Celery task uses);
- text blocks joined with blank lines, exactly as ``process_document_async`` builds
  ``parsed_text``;
- ``_split_contract_into_clauses`` (one persisted clause per segment);
- ``assess_single_document_coverage`` with the real ``CategoryRouter``.

It also guards fixture drift: the PDF text must be the committed source text, and the
generator must reproduce the committed PDF byte for byte.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import re
from pathlib import Path
from types import ModuleType

import pytest

from src.coherence.models import Clause
from src.core.tasks.ingestion_tasks import _build_contract_clause_data, _split_contract_into_clauses
from src.documents.adapters.parsers.pdf_file_parser import PDFFileParser
from src.health.application.single_document_coverage import assess_single_document_coverage

API_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = API_ROOT.parents[1]
FIXTURE_DIR = REPO_ROOT / "apps" / "web" / "src" / "tests" / "e2e" / "test-data" / "pj01"
MANIFEST_PATH = FIXTURE_DIR / "contract-a.manifest.json"
GENERATOR_PATH = API_ROOT / "scripts" / "generate_pj01_contract_fixture.py"

CANONICAL_CATEGORIES = {"SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY"}


def _manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("generate_pj01_contract_fixture", GENERATOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _parsed_text(pdf_path: Path) -> str:
    blocks = asyncio.run(PDFFileParser().extract_text_and_offsets(pdf_path))
    # Same join as src/core/tasks/ingestion_tasks.py (process_document_async).
    return "\n\n".join(block.get("text", "") for block in blocks if isinstance(block.get("text"), str)).strip()


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


@pytest.fixture(scope="module")
def manifest() -> dict:
    return _manifest()


@pytest.fixture(scope="module")
def segments(manifest: dict) -> list[str]:
    return _split_contract_into_clauses(_parsed_text(FIXTURE_DIR / manifest["files"]["pdf"]))


def test_pdf_text_is_the_committed_source_text(manifest: dict) -> None:
    source = (FIXTURE_DIR / manifest["files"]["source_text"]).read_text(encoding="utf-8")
    assert _normalise(_parsed_text(FIXTURE_DIR / manifest["files"]["pdf"])) == _normalise(source)


def test_generator_reproduces_the_committed_pdf_structure(manifest: dict) -> None:
    source = (FIXTURE_DIR / manifest["files"]["source_text"]).read_text(encoding="utf-8")
    committed = (FIXTURE_DIR / manifest["files"]["pdf"]).read_bytes()
    generator = _generator()
    # Parser-visible structure (page + text block), so only real fixture drift fails.
    assert generator.text_blocks(generator.render_contract_pdf(source)) == generator.text_blocks(committed)


def test_ingestion_segments_one_clause_per_manifest_clause(manifest: dict, segments: list[str]) -> None:
    assert len(segments) == len(manifest["clauses"])
    for clause in manifest["clauses"]:
        assert segments[clause["ordinal"]].startswith(clause["heading"]), clause["heading"]


def test_real_health_coverage_matches_the_manifest(manifest: dict, segments: list[str]) -> None:
    clauses = [Clause(id=str(ordinal), text=text, data={}) for ordinal, text in enumerate(segments)]
    coverage = assess_single_document_coverage(clauses, [])

    actual = {
        assessment.category.value: (assessment.state.value, [int(clause_id) for clause_id in assessment.evidence_clause_ids])
        for assessment in coverage.assessments
    }
    expected = {
        category: (expectation["state"], expectation["evidence_clause_ordinals"])
        for category, expectation in manifest["expected_health"]["categories"].items()
    }
    assert set(expected) == CANONICAL_CATEGORIES
    assert actual == expected


def test_every_fact_and_anchor_is_in_its_clause(manifest: dict, segments: list[str]) -> None:
    for clause in manifest["clauses"]:
        anchor = clause.get("evidence_anchor")
        if anchor:
            assert anchor in _normalise(segments[clause["ordinal"]]), anchor
    for fact in manifest["facts"]:
        assert fact["text"] in _normalise(segments[fact["clause_ordinal"]]), fact["key"]


def test_deterministic_contract_totals_are_extracted(manifest: dict, segments: list[str]) -> None:
    parsed = "\n\n".join(segments)
    price = next(fact for fact in manifest["facts"] if fact["key"] == "contract_price")
    data = _build_contract_clause_data(segments[price["clause_ordinal"]], parsed)
    assert data.get("currency") == price["value"]["currency"]
    assert data.get("total_amount") == price["value"]["amount"]
