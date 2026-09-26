"""TS-UT-PJ01-FIXTURE-003: Contract B is a real revision of Contract A through the REAL pipeline.

PJ-01 asserts What Changed? on a real re-upload, so the expected change must be what production
code derives from the two committed PDFs, not a reviewer's hope:

- ``PDFFileParser`` + the ingestion join (as ``process_document_async``);
- ``_split_contract_into_clauses`` and ``_extract_contract_clauses`` (the persisted clauses);
- ``assess_single_document_coverage`` (six categories stay PRESENT);
- ``diff_contract_revisions`` + ``build_change_projection_event`` (the P0c change projection).

Contract B must change exactly the two declared facts, keep every heading and control fact,
and an identical re-analysis must be NO_CHANGE (change_cause null), never a business change.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import re
from pathlib import Path
from types import ModuleType
from uuid import uuid4

import pytest

from src.change_intelligence.application.structural_diff import diff_contract_revisions
from src.coherence.models import Clause as CoverageClause
from src.core.tasks.ingestion_tasks import _extract_contract_clauses, _split_contract_into_clauses
from src.documents.adapters.parsers.pdf_file_parser import PDFFileParser
from src.health.application.single_document_coverage import assess_single_document_coverage
from src.temporal.application.change_projection import build_change_projection_event

API_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = API_ROOT.parents[1]
FIXTURE_DIR = REPO_ROOT / "apps" / "web" / "src" / "tests" / "e2e" / "test-data" / "pj01"
GENERATOR_PATH = API_ROOT / "scripts" / "generate_pj01_contract_fixture.py"


def _load(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("generate_pj01_contract_fixture", GENERATOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _parsed_text(pdf_path: Path) -> str:
    blocks = asyncio.run(PDFFileParser().extract_text_and_offsets(pdf_path))
    return "\n\n".join(block.get("text", "") for block in blocks if isinstance(block.get("text"), str)).strip()


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


@pytest.fixture(scope="module")
def manifest_a() -> dict:
    return _load("contract-a.manifest.json")


@pytest.fixture(scope="module")
def manifest_b() -> dict:
    return _load("contract-b.manifest.json")


@pytest.fixture(scope="module")
def parsed_a(manifest_a: dict) -> str:
    return _parsed_text(FIXTURE_DIR / manifest_a["files"]["pdf"])


@pytest.fixture(scope="module")
def parsed_b(manifest_b: dict) -> str:
    return _parsed_text(FIXTURE_DIR / manifest_b["files"]["pdf"])


def test_b_pdf_text_is_the_committed_source_and_regenerates(manifest_b: dict, parsed_b: str) -> None:
    source = (FIXTURE_DIR / manifest_b["files"]["source_text"]).read_text(encoding="utf-8")
    assert _normalise(parsed_b) == _normalise(source)
    generator = _generator()
    committed = (FIXTURE_DIR / manifest_b["files"]["pdf"]).read_bytes()
    assert generator.text_blocks(generator.render_contract_pdf(source)) == generator.text_blocks(committed)


def test_b_only_rewords_the_declared_mutable_facts(manifest_a: dict, manifest_b: dict) -> None:
    source_a = (FIXTURE_DIR / manifest_a["files"]["source_text"]).read_text(encoding="utf-8").splitlines()
    source_b = (FIXTURE_DIR / manifest_b["files"]["source_text"]).read_text(encoding="utf-8").splitlines()
    assert len(source_a) == len(source_b)
    changed = [(a, b) for a, b in zip(source_a, source_b, strict=True) if a != b]
    declared = manifest_b["expected_revision_change"]["changed_facts"]
    assert len(changed) == len(declared)
    for (line_a, line_b), fact in zip(changed, declared, strict=True):
        assert fact["before_text"] in line_a and fact["after_text"] in line_b, fact["key"]
    mutable = set(manifest_a["revision_contract"]["mutable_fact_keys"])
    assert {fact["key"] for fact in declared} <= mutable
    controls = {fact["key"]: fact["text"] for fact in manifest_a["facts"]}
    joined_b = _normalise("\n".join(source_b))
    for key in manifest_b["expected_revision_change"]["no_change_control_fact_keys"]:
        assert controls[key] in joined_b, key


def test_b_keeps_every_heading_and_all_six_categories(manifest_a: dict, manifest_b: dict, parsed_b: str) -> None:
    segments = _split_contract_into_clauses(parsed_b)
    assert len(segments) == len(manifest_a["clauses"])
    for clause in manifest_a["clauses"]:
        assert segments[clause["ordinal"]].startswith(clause["heading"]), clause["heading"]
    coverage = assess_single_document_coverage(
        [CoverageClause(id=str(ordinal), text=text, data={}) for ordinal, text in enumerate(segments)], []
    )
    actual = {
        item.category.value: (item.state.value, [int(cid) for cid in item.evidence_clause_ids])
        for item in coverage.assessments
    }
    expected = {
        category: (expectation["state"], expectation["evidence_clause_ordinals"])
        for category, expectation in manifest_b["expected_health"]["categories"].items()
    }
    assert actual == expected


def _clauses(parsed_text: str, *, document_id, project_id, tenant_id):  # type: ignore[no-untyped-def]
    return _extract_contract_clauses(
        document_id=document_id, project_id=project_id, tenant_id=tenant_id, parsed_text=parsed_text
    )


def test_real_structural_diff_reports_exactly_the_declared_business_change(
    manifest_a: dict, manifest_b: dict, parsed_a: str, parsed_b: str
) -> None:
    document_id, project_id, tenant_id = uuid4(), uuid4(), uuid4()
    old = _clauses(parsed_a, document_id=document_id, project_id=project_id, tenant_id=tenant_id)
    new = _clauses(parsed_b, document_id=document_id, project_id=project_id, tenant_id=tenant_id)
    changeset = diff_contract_revisions(
        project_id=project_id, tenant_id=tenant_id, from_revision_id=uuid4(), to_revision_id=uuid4(),
        old_clauses=old, new_clauses=new,
    )

    expectation = manifest_b["expected_revision_change"]
    assert [change.change_type for change in changeset.changes] == ["modified"] * len(expectation["changed_facts"])
    rendered = [json.dumps({"before": change.before, "after": change.after}) for change in changeset.changes]
    for fact, change_text in zip(expectation["changed_facts"], rendered, strict=True):
        assert fact["before_text"] in change_text and fact["after_text"] in change_text, fact["key"]
    controls = {fact["key"]: fact["text"] for fact in manifest_a["facts"]}
    for key in expectation["no_change_control_fact_keys"]:
        assert all(controls[key] not in text for text in rendered), f"control {key} reported as changed"

    pdf_a = (FIXTURE_DIR / manifest_a["files"]["pdf"]).read_bytes()
    pdf_b = (FIXTURE_DIR / manifest_b["files"]["pdf"]).read_bytes()
    event = build_change_projection_event(
        changeset=changeset, document_id=document_id,
        source_blob_hash=hashlib.sha256(pdf_a).hexdigest(), target_blob_hash=hashlib.sha256(pdf_b).hexdigest(),
    )
    assert event.payload["change_cause"] == expectation["change_cause"]


def test_identical_reanalysis_is_no_change_not_a_business_change(manifest_a: dict, parsed_a: str) -> None:
    document_id, project_id, tenant_id = uuid4(), uuid4(), uuid4()
    first = _clauses(parsed_a, document_id=document_id, project_id=project_id, tenant_id=tenant_id)
    second = _clauses(parsed_a, document_id=document_id, project_id=project_id, tenant_id=tenant_id)
    changeset = diff_contract_revisions(
        project_id=project_id, tenant_id=tenant_id, from_revision_id=uuid4(), to_revision_id=uuid4(),
        old_clauses=first, new_clauses=second,
    )
    digest = hashlib.sha256((FIXTURE_DIR / manifest_a["files"]["pdf"]).read_bytes()).hexdigest()
    event = build_change_projection_event(
        changeset=changeset, document_id=document_id, source_blob_hash=digest, target_blob_hash=digest,
    )
    assert changeset.changes == []
    assert event.payload["change_cause"] is None
