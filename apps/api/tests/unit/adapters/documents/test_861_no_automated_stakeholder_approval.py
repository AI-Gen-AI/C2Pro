"""#861 -- automated document ingestion may OBSERVE a stakeholder, never approve one.

TS-UT-861-STAKEHOLDER-APPROVAL-GUARD-001. A static guard over the automated
document ingestion layers (parsers, entity extraction, RAG, the documents
application use cases, the ingestion worker and the documents router's extraction
wiring): none of them may set an approval status or reviewer provenance
(``ApprovalStatus``, ``approval_status``, ``reviewed_by``, ``reviewed_at``,
``review_comment``), and the stakeholder extraction may not hand a user id to the
stakeholder writer (it would let the uploader be recorded as reviewer).

The explicit human review use case (``ReviewStakeholderApprovalUseCase``) and the
manual stakeholder API live outside this scope on purpose: a human approving a
stakeholder is the legitimate path.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

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
STAKEHOLDER_EXTRACTION = "src/documents/adapters/extraction/documents_entity_extraction_service.py"
APPROVAL_TOKENS = frozenset(
    {"ApprovalStatus", "approval_status", "reviewed_by", "reviewed_at", "review_comment"}
)
HUMAN_STAKEHOLDER_WRITES = frozenset({"execute"})


def _guarded_modules() -> list[Path]:
    files: list[Path] = []
    for package in GUARDED_PACKAGES:
        files.extend(sorted((API_ROOT / package).rglob("*.py")))
    files.extend(API_ROOT / name for name in GUARDED_FILES)
    return files


def _approval_violations(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        name = None
        if isinstance(node, ast.Name):
            name = node.id
        elif isinstance(node, ast.Attribute):
            name = node.attr
        elif isinstance(node, ast.alias):
            name = node.name
        elif isinstance(node, ast.keyword):
            name = node.arg
        if name in APPROVAL_TOKENS:
            found.add(f"{path.name}:{getattr(node, 'lineno', 0)} {name}")
    return sorted(found)


def _stakeholder_writer_violations(path: Path) -> list[str]:
    """The extraction may call only the observation seam, without any user id."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        keywords = {keyword.arg for keyword in node.keywords}
        if "payload" not in keywords:
            continue  # not a stakeholder write
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        if name in HUMAN_STAKEHOLDER_WRITES:
            found.append(f"{path.name}:{node.lineno} calls human create {name}()")
        if "user_id" in keywords:
            found.append(f"{path.name}:{node.lineno} hands user_id to the stakeholder writer")
    return found


def test_guard_scans_the_real_ingestion_layers() -> None:
    names = {path.name for path in _guarded_modules()}
    assert {"documents_entity_extraction_service.py", "ingestion_tasks.py", "router.py",
            "parse_document_use_case.py"} <= names


@pytest.mark.parametrize("path", _guarded_modules(), ids=lambda p: str(p.relative_to(API_ROOT)))
def test_document_ingestion_never_sets_approval_or_reviewer(path: Path) -> None:
    assert _approval_violations(path) == []


def test_stakeholder_extraction_only_records_observations() -> None:
    assert _stakeholder_writer_violations(API_ROOT / STAKEHOLDER_EXTRACTION) == []


def test_the_guard_detects_the_pre_861_auto_approval(tmp_path: Path) -> None:
    """The exact pre-#861 shapes are violations (the guard is not vacuous)."""
    sample = tmp_path / "extraction.py"
    sample.write_text(
        "from src.core.approval import ApprovalStatus\n"
        "async def extract(use_case, document, payload, tenant_id, user_id):\n"
        "    await use_case.execute(project_id=document.project_id, user_id=user_id,\n"
        "                           payload=payload, tenant_id=tenant_id)\n"
        "    return dict(approval_status=ApprovalStatus.APPROVED.value, reviewed_by=user_id)\n",
        encoding="utf-8",
    )
    assert _approval_violations(sample) == [
        "extraction.py:1 ApprovalStatus",
        "extraction.py:5 ApprovalStatus",
        "extraction.py:5 approval_status",
        "extraction.py:5 reviewed_by",
    ]
    assert _stakeholder_writer_violations(sample) == [
        "extraction.py:3 calls human create execute()",
        "extraction.py:3 hands user_id to the stakeholder writer",
    ]


def test_the_human_review_path_is_outside_the_guard() -> None:
    """The guard must not forbid a human approving a stakeholder."""
    review = API_ROOT / "src/stakeholders/application/review_stakeholder_approval_use_case.py"
    assert review not in _guarded_modules()
    assert _approval_violations(review)  # it legitimately writes reviewer provenance
