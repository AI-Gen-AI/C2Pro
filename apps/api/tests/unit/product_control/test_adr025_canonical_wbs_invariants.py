"""ADR-025 / MASTER `project_controls.invariant = one_project_one_canonical_hierarchical_wbs`.

The project WBS is owned by Project Controls and persisted in ``wbs_nodes`` (the nested-set
hierarchy ADR-025 names as the backbone). Procurement, RACI, schedule/coherence and reporting
consume that WBS; they must not persist, read or reference a parallel hierarchy
(``procurement_wbs_items``, legacy ``wbs_items`` or an in-memory store).
"""

from __future__ import annotations

import ast
import importlib.util
import re
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa

SRC = Path(__file__).resolve().parents[3] / "src"
CANONICAL_TABLE = "wbs_nodes"
PARALLEL_TABLES = ("procurement_wbs_items", "wbs_items")

# The only modules allowed to name the parallel tables: their (legacy, write-blocked) ORM mapping.
LEGACY_MAPPING_MODULES = {
    "procurement/adapters/persistence/models.py",
}
_SQL_TABLE_REF = re.compile(
    r"\b(?:FROM|JOIN|INTO|UPDATE|TABLE)\s+(?:public\.)?(procurement_wbs_items|wbs_items)\b", re.IGNORECASE
)


def _python_sources() -> list[Path]:
    return [path for path in SRC.rglob("*.py") if "__pycache__" not in path.parts]


def _relative(path: Path) -> str:
    return path.relative_to(SRC).as_posix()


def test_no_runtime_sql_reads_or_writes_a_parallel_wbs_table() -> None:
    offenders = []
    for path in _python_sources():
        if _relative(path) in LEGACY_MAPPING_MODULES:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and _SQL_TABLE_REF.search(node.value):
                offenders.append(f"{_relative(path)}:{node.lineno}")
    assert offenders == []


def test_no_runtime_code_uses_the_legacy_procurement_wbs_mapping() -> None:
    offenders = []
    for path in _python_sources():
        if _relative(path) in LEGACY_MAPPING_MODULES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == "WBSItemORM":
                offenders.append(f"{_relative(path)}:{node.lineno}")
            elif isinstance(node, ast.alias) and node.name == "WBSItemORM":
                offenders.append(f"{_relative(path)}:import")
    assert sorted(set(offenders)) == []


def test_canonical_wbs_repository_is_backed_by_the_project_controls_wbs() -> None:
    from src.procurement.adapters.persistence import wbs_repository
    from src.wbs.adapters.persistence.models import WBSNodeORM

    assert WBSNodeORM.__tablename__ == CANONICAL_TABLE
    referenced = {
        node.id for node in ast.walk(ast.parse(Path(wbs_repository.__file__).read_text(encoding="utf-8")))
        if isinstance(node, ast.Name)
    }
    assert "WBSNodeORM" in referenced
    assert "WBSItemORM" not in referenced


@pytest.mark.parametrize(
    ("module", "orm_name"),
    [
        ("src.stakeholders.adapters.persistence.models", "StakeholderWBSRaciORM"),
        ("src.procurement.adapters.persistence.models", "BOMItemORM"),
    ],
)
def test_work_references_point_at_the_canonical_wbs(module: str, orm_name: str) -> None:
    orm = getattr(importlib.import_module(module), orm_name)
    foreign_keys = list(orm.__table__.c.wbs_item_id.foreign_keys)
    assert [fk.column.table.name for fk in foreign_keys] == [CANONICAL_TABLE]


class _RecordingSession:
    def __init__(self) -> None:
        self.statements: list[str] = []

    async def execute(self, statement, params=None):  # noqa: ANN001 - SQLAlchemy-compatible fake
        self.statements.append(str(statement))

        class _Result:
            def fetchall(self_inner):  # noqa: N805
                return []

        return _Result()


async def test_schedule_clauses_read_only_the_canonical_wbs() -> None:
    from src.coherence.schedule_clause_builder import build_schedule_clauses

    session = _RecordingSession()
    clauses = await build_schedule_clauses(session, uuid4(), uuid4())  # type: ignore[arg-type]

    assert clauses == []
    assert session.statements, "the schedule builder must query the canonical WBS"
    for statement in session.statements:
        assert re.search(rf"\bFROM\s+{CANONICAL_TABLE}\b", statement)
        assert not any(re.search(rf"\b{table}\b", statement) for table in PARALLEL_TABLES)


async def test_procurement_spend_is_derived_from_the_canonical_wbs() -> None:
    from src.procurement.adapters.persistence.budget_repository import SQLAlchemyBudgetRepository

    captured: list[str] = []

    class _Session:
        async def execute(self, statement, params=None):  # noqa: ANN001
            captured.append(str(statement.compile(dialect=sa.dialects.postgresql.dialect())))

            class _Result:
                def scalar(self_inner):  # noqa: N805
                    return 0

                def scalar_one_or_none(self_inner):  # noqa: N805
                    return 0

            return _Result()

    await SQLAlchemyBudgetRepository(_Session()).get_total_spent_by_project(uuid4(), uuid4())  # type: ignore[arg-type]

    assert captured and all(CANONICAL_TABLE in sql for sql in captured)
    assert not any(re.search(r"\bprocurement_wbs_items\b", sql) for sql in captured)


def test_no_shadow_wbs_implementation_remains() -> None:
    for module in (
        "src.wbs.adapters.persistence.in_memory_repository",
        "src.wbs.adapters.http.router",
    ):
        assert importlib.util.find_spec(module) is None, f"{module} is a shadow WBS implementation"


def test_every_mounted_wbs_route_persists_through_the_canonical_store() -> None:
    from fastapi.routing import APIRoute, iter_route_contexts

    from src.main import create_application

    allowed_handlers = {"src.projects.adapters.http.router", "src.procurement.adapters.http.router"}
    wbs_routes = {}
    for context in iter_route_contexts(create_application().routes):
        route = context.original_route
        if isinstance(route, APIRoute) and context.path_format and "wbs" in context.path_format.lower():
            wbs_routes[(tuple(sorted(context.methods or ())), context.path_format)] = route.endpoint.__module__
    assert wbs_routes, "the canonical WBS must be served"
    assert set(wbs_routes.values()) <= allowed_handlers
