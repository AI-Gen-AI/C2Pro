"""#852 -- automated document ingestion may OBSERVE a schedule, never write canonical WBS.

TS-UT-852-SCHEDULE-WBS-GUARD-001. A static guard over the automated document
ingestion layers (parsers, entity extraction, RAG, the documents application
use cases, the ingestion worker and the documents router's extraction wiring):
none of them may reference canonical WBS write machinery, construct a canonical
WBS row, or pass ``wbs_items`` to a persistence call. BUDGET -> BOM writes are
guarded separately by the #860 guard (test_860_no_budget_canonical_bom_writes).

A schedule activity is not a WBS node; the governed WBS baseline authority is
PC-1 / PC-2. Explicit human WBS editing APIs (WBS / procurement / projects
routers) are outside this guard on purpose.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from src.documents.adapters.extraction.documents_entity_extraction_service import (
    DocumentsEntityExtractionService,
)

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
# Canonical WBS write machinery: use cases, repositories, DTOs and ORM rows.
FORBIDDEN_NAMES = frozenset(
    {
        "CreateWBSItemUseCase",
        "SQLAlchemyWBSRepository",
        "IWBSRepository",
        "WBSItemCreate",
        "WBSNodeORM",
        "WBSItemORM",
        "wbs_use_case_factory",
    }
)
FORBIDDEN_CALLS = frozenset(
    {
        "bulk_create_from_dicts",
        "persist_wbs_bom_items",
        "save_wbs_items",
        "create_wbs_item",
        "delete_wbs_item",
    }
)
FORBIDDEN_MODULE_PREFIXES = (
    "src.procurement.application.use_cases.wbs_use_cases",
    "src.procurement.adapters.persistence.wbs_repository",
    "src.wbs.",
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
            if any(keyword.arg == "wbs_items" for keyword in node.keywords):
                found.append(f"{path.name}:{node.lineno} persists wbs_items")
    return sorted(set(found))


def test_guard_scans_the_real_ingestion_layers() -> None:
    modules = {path.name for path in _guarded_modules()}
    assert {
        "documents_entity_extraction_service.py",
        "ingestion_tasks.py",
        "router.py",
        "parse_document_use_case.py",
        "composite_file_parser.py",
        "sqlalchemy_rag_ingestion_service.py",
    } <= modules


@pytest.mark.parametrize("path", _guarded_modules(), ids=lambda p: str(p.relative_to(API_ROOT)))
def test_document_ingestion_never_writes_canonical_wbs(path: Path) -> None:
    assert _violations(path) == []


def test_extraction_service_cannot_be_handed_a_wbs_writer() -> None:
    parameters = inspect.signature(DocumentsEntityExtractionService.__init__).parameters
    assert not [name for name in parameters if "wbs" in name.lower()]


def test_the_guard_detects_the_removed_schedule_write(tmp_path: Path) -> None:
    """The exact pre-#852 schedule path is a violation (the guard is not vacuous)."""
    sample = tmp_path / "documents_entity_extraction_service.py"
    sample.write_text(
        "from src.procurement.application.dtos import BOMItemCreate, WBSItemCreate\n"
        "class S:\n"
        "    def __init__(self, wbs_use_case_factory):\n"
        "        self._wbs_use_case_factory = wbs_use_case_factory\n"
        "    async def _extract_wbs_items(self, document, payloads, tenant_id):\n"
        "        use_case = self._wbs_use_case_factory()\n"
        "        item = WBSItemCreate(project_id=document.project_id)\n"
        "        return await use_case.replace_for_source_document(\n"
        "            project_id=document.project_id, wbs_items=payloads, tenant_id=tenant_id)\n"
        "    async def _extract_bom_items(self, document, payloads, tenant_id):\n"
        "        return await self.bom.replace_for_source_document(bom_items=payloads)\n",
        encoding="utf-8",
    )
    assert _violations(sample) == [
        "documents_entity_extraction_service.py:1 references WBSItemCreate",
        "documents_entity_extraction_service.py:3 accepts wbs_use_case_factory",
        "documents_entity_extraction_service.py:4 references wbs_use_case_factory",
        "documents_entity_extraction_service.py:7 references WBSItemCreate",
        "documents_entity_extraction_service.py:8 persists wbs_items",
    ]
