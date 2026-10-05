"""#830 -- the AI analysis layers may PROPOSE a WBS, never write the canonical one.

TS-UT-830-WBS-GUARD-001. A static guard over the analysis application, graph and
AI-adapter modules: none of them may call a canonical WBS write API, construct a
canonical WBS row, or delete canonical WBS rows. Until the governed WBS baseline
authority exists (PC-1 / PC-2), an extracted WBS stays in the analysis result /
approved artifact as a proposal qualified ``WBS_GOVERNANCE_REQUIRED``.

Explicit human WBS editing (the WBS / procurement / projects HTTP APIs) is out of
this guard's scope on purpose: the rule is AI/automated analysis -> propose only,
not "all WBS writes forbidden".
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parents[3]
GUARDED_PACKAGES = (
    "src/analysis/application",
    "src/analysis/adapters/graph",
    "src/analysis/adapters/ai",
)
# Canonical WBS write APIs (procurement/wbs repositories, coherence/wbs_bom ports).
FORBIDDEN_CALLS = frozenset(
    {
        "bulk_create_from_dicts",
        "bulk_create",
        "replace_for_source_document",
        "persist_wbs_bom_items",
        "save_wbs_items",
        "create_wbs_item",
        "delete_wbs_item",
    }
)
CANONICAL_WBS_MODELS = frozenset({"WBSNodeORM", "WBSItemORM"})


def _guarded_modules() -> list[Path]:
    files: list[Path] = []
    for package in GUARDED_PACKAGES:
        files.extend(sorted((API_ROOT / package).rglob("*.py")))
    return files


def _violations(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        if name in FORBIDDEN_CALLS:
            found.append(f"{path.name}:{node.lineno} calls {name}()")
        if name in CANONICAL_WBS_MODELS:
            found.append(f"{path.name}:{node.lineno} constructs {name}")
        if name == "delete" and any(
            isinstance(arg, ast.Name) and arg.id in CANONICAL_WBS_MODELS for arg in node.args
        ):
            found.append(f"{path.name}:{node.lineno} deletes canonical WBS rows")
    return sorted(found)


def test_guard_scans_the_real_analysis_layers() -> None:
    modules = {path.name for path in _guarded_modules()}
    # The N17 persistence path and the graph nodes are in scope.
    assert {"persist_analysis_use_case.py", "nodes.py", "trusted_materialization.py"} <= modules


@pytest.mark.parametrize("path", _guarded_modules(), ids=lambda p: str(p.relative_to(API_ROOT)))
def test_analysis_layer_never_writes_canonical_wbs(path: Path) -> None:
    assert _violations(path) == []


def test_the_guard_detects_the_removed_830_bypass(tmp_path: Path) -> None:
    """The exact pre-#830 N17 code is a violation (the guard is not vacuous)."""
    sample = tmp_path / "persist_analysis_use_case.py"
    sample.write_text(
        "async def execute(self, command):\n"
        "    await self._session.execute(delete(WBSNodeORM).where(WBSNodeORM.project_id == 1))\n"
        "    await self._wbs_repo.bulk_create_from_dicts(command.project_id, command.extracted_wbs)\n",
        encoding="utf-8",
    )
    assert _violations(sample) == [
        "persist_analysis_use_case.py:2 deletes canonical WBS rows",
        "persist_analysis_use_case.py:3 calls bulk_create_from_dicts()",
    ]
