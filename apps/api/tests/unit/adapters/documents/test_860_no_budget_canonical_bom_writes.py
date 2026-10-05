"""#860 -- automated document ingestion may OBSERVE a budget, never write canonical BOM.

TS-UT-860-BUDGET-BOM-GUARD-001. A static guard over the automated document
ingestion layers (parsers, entity extraction, RAG, the documents application use
cases, the ingestion worker and the documents router's extraction wiring): none
of them may reference canonical BOM write machinery, construct a BOM row, or pass
``bom_items`` to a persistence call. The coherence budget clause builder may not
read the BOM table as budget truth.

A budget line is not a canonical BOM item, and ``procurement_bom_items`` is a
mixed legacy object. Explicit human / procurement BOM APIs (the procurement
router and use cases) are outside this guard on purpose: the rule is automated
document ingestion -> no canonical BOM write, not "all BOM writes forbidden".
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from src.documents.adapters.extraction.documents_entity_extraction_service import (
    DocumentsEntityExtractionService,
)
from src.procurement.adapters.persistence.bom_repository import SQLAlchemyBOMRepository
from src.procurement.application.use_cases.bom_use_cases import CreateBOMItemUseCase
from src.procurement.ports.bom_repository import IBOMRepository

API_ROOT = Path(__file__).resolve().parents[4]
GUARDED_PACKAGES = (
    "src/documents/adapters/extraction",
    "src/documents/adapters/parsers",
    "src/documents/adapters/rag",
    "src/documents/application",
)
GUARDED_FILES = (
    "src/core/tasks/ingestion_tasks.py",
    "src/documents/adapters/http/router.py",
)
# Canonical BOM write machinery: use cases, repositories, DTOs and ORM rows.
FORBIDDEN_NAMES = frozenset(
    {
        "CreateBOMItemUseCase",
        "SQLAlchemyBOMRepository",
        "IBOMRepository",
        "BOMItemCreate",
        "BOMItemORM",
        "bom_use_case_factory",
    }
)
FORBIDDEN_CALLS = frozenset(
    {
        "replace_for_source_document",
        "bulk_create",
        "create_bom_item",
        "delete_bom_item",
        "persist_wbs_bom_items",
        "save_bom_items",
    }
)
FORBIDDEN_MODULE_PREFIXES = (
    "src.procurement.application.use_cases.bom_use_cases",
    "src.procurement.adapters.persistence.bom_repository",
)


def _guarded_modules() -> list[Path]:
    files: list[Path] = []
    for package in GUARDED_PACKAGES:
        files.extend(sorted((API_ROOT / package).rglob("*.py")))
    files.extend(API_ROOT / name for name in GUARDED_FILES)
    return files


def _violations(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and (
            node.module.startswith(FORBIDDEN_MODULE_PREFIXES)
        ):
            found.append(f"{path.name}:{node.lineno} imports {node.module}")
        elif isinstance(node, ast.alias) and node.name in FORBIDDEN_NAMES:
            found.append(f"{path.name}:{node.lineno} references {node.name}")
        elif isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            found.append(f"{path.name}:{node.lineno} references {node.id}")
        elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_NAMES:
            found.append(f"{path.name}:{node.lineno} references {node.attr}")
        elif isinstance(node, ast.arg) and node.arg in FORBIDDEN_NAMES:
            found.append(f"{path.name}:{node.lineno} accepts {node.arg}")
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if name in FORBIDDEN_CALLS:
                found.append(f"{path.name}:{node.lineno} calls {name}()")
            if any(keyword.arg == "bom_items" for keyword in node.keywords):
                found.append(f"{path.name}:{node.lineno} persists bom_items")
    return sorted(set(found))


def test_guard_scans_the_real_ingestion_layers() -> None:
    modules = {path.name for path in _guarded_modules()}
    assert {
        "documents_entity_extraction_service.py",
        "ingestion_tasks.py",
        "router.py",
        "parse_document_use_case.py",
        "composite_file_parser.py",
        "excel_file_parser.py",
        "sqlalchemy_rag_ingestion_service.py",
    } <= modules


@pytest.mark.parametrize("path", _guarded_modules(), ids=lambda p: str(p.relative_to(API_ROOT)))
def test_document_ingestion_never_writes_canonical_bom(path: Path) -> None:
    assert _violations(path) == []


def test_extraction_service_cannot_be_handed_a_bom_writer() -> None:
    parameters = inspect.signature(DocumentsEntityExtractionService.__init__).parameters
    assert not [name for name in parameters if "bom" in name.lower()]


def test_the_source_document_bom_sweep_no_longer_exists() -> None:
    """The delete-by-source + NULL-source "orphan sweep" is gone at every layer."""
    for owner in (SQLAlchemyBOMRepository, CreateBOMItemUseCase, IBOMRepository):
        assert not hasattr(owner, "replace_for_source_document"), owner.__name__


_BOM_TRUTH_TOKENS = frozenset(
    {"procurement_bom_items", "procurement_bom", "BOMItemORM", "SQLAlchemyBOMRepository",
     "IBOMRepository"}
)


def _bom_truth_references(path: Path) -> list[str]:
    """Any BOM table / BOM persistence reference, as SQL text, name or import."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            found |= {f"{path.name}:{node.lineno} {t}" for t in _BOM_TRUTH_TOKENS
                      if t in node.value}
        elif isinstance(node, ast.Name) and node.id in _BOM_TRUTH_TOKENS:
            found.add(f"{path.name}:{node.lineno} {node.id}")
        elif isinstance(node, ast.alias) and node.name in _BOM_TRUTH_TOKENS:
            found.add(f"{path.name}:{node.lineno} {node.name}")
        elif isinstance(node, ast.ImportFrom) and node.module and "bom_repository" in node.module:
            found.add(f"{path.name}:{node.lineno} {node.module}")
    return sorted(found)


def _coherence_modules() -> list[Path]:
    return sorted((API_ROOT / "src/coherence").rglob("*.py"))


@pytest.mark.parametrize("path", _coherence_modules(), ids=lambda p: str(p.relative_to(API_ROOT)))
def test_coherence_never_sources_budget_truth_from_bom(path: Path) -> None:
    """No coherence module -- whatever its name -- reads the mixed BOM table."""
    assert _bom_truth_references(path) == []


def test_the_coherence_guard_detects_the_removed_bom_budget_source(tmp_path: Path) -> None:
    sample = tmp_path / "anything.py"
    sample.write_text(
        "from sqlalchemy import text\n"
        "STMT = text(\"SELECT b.total_price FROM procurement_bom_items b\")\n"
        "DATA = {\"source\": \"procurement_bom\"}\n",
        encoding="utf-8",
    )
    assert _bom_truth_references(sample) == [
        "anything.py:2 procurement_bom", "anything.py:2 procurement_bom_items",
        "anything.py:3 procurement_bom",
    ]


def test_the_guard_detects_the_removed_budget_write(tmp_path: Path) -> None:
    """The exact pre-#860 budget path is a violation (the guard is not vacuous)."""
    sample = tmp_path / "documents_entity_extraction_service.py"
    sample.write_text(
        "from src.procurement.application.dtos import BOMItemCreate\n"
        "class S:\n"
        "    def __init__(self, bom_use_case_factory):\n"
        "        self._bom_use_case_factory = bom_use_case_factory\n"
        "    async def _extract_bom_items(self, document, payloads, tenant_id):\n"
        "        use_case = self._bom_use_case_factory()\n"
        "        item = BOMItemCreate(project_id=document.project_id)\n"
        "        return await use_case.replace_for_source_document(\n"
        "            project_id=document.project_id, bom_items=payloads, tenant_id=tenant_id)\n",
        encoding="utf-8",
    )
    assert _violations(sample) == [
        "documents_entity_extraction_service.py:1 references BOMItemCreate",
        "documents_entity_extraction_service.py:3 accepts bom_use_case_factory",
        "documents_entity_extraction_service.py:4 references bom_use_case_factory",
        "documents_entity_extraction_service.py:7 references BOMItemCreate",
        "documents_entity_extraction_service.py:8 calls replace_for_source_document()",
        "documents_entity_extraction_service.py:8 persists bom_items",
    ]
