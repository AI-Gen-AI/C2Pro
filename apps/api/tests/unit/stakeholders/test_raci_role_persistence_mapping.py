"""RACI role persistence must speak the migrated schema's labels (IR-3).

The Alembic (and Supabase CLI) migrations create ``racirole AS ENUM ('R', 'A', 'C', 'I')``.
If the ORM column persists the Python member *names* instead, every stored RACI row fails
to load on a migrated database (``LookupError: 'A' is not among the defined enum values``)
and ``GET /projects/{id}/raci`` returns 500. The pytest ``db`` fixture builds its schema
from ORM metadata, so repository tests cannot see this drift; these tests pin the ORM to
the migration DDL instead.
"""

from __future__ import annotations

import enum
import re
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from src.core.database import Base
from src.stakeholders.adapters.persistence.models import StakeholderWBSRaciORM
from src.stakeholders.domain.models import RACIRole

API_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = API_ROOT.parents[1]
ALEMBIC_MIGRATION = API_ROOT / "alembic" / "versions" / "20260318_0001_add_stakeholders_tables.py"
SUPABASE_MIGRATION = REPO_ROOT / "supabase" / "migrations" / "20260318000100_add_stakeholders_tables.sql"

_CREATE_TYPE = re.compile(r"CREATE TYPE racirole AS ENUM \(([^)]*)\)")


def _ddl_labels(path: Path) -> list[str]:
    match = _CREATE_TYPE.search(path.read_text(encoding="utf-8"))
    assert match, f"racirole DDL not found in {path}"
    return re.findall(r"'([^']*)'", match.group(1))


def _raci_role_type() -> sa.Enum:
    column_type = StakeholderWBSRaciORM.__table__.c.raci_role.type
    assert isinstance(column_type, sa.Enum)
    return column_type


@pytest.mark.parametrize("migration", [ALEMBIC_MIGRATION, SUPABASE_MIGRATION], ids=["alembic", "supabase"])
def test_orm_raci_role_labels_match_migration_ddl(migration: Path) -> None:
    assert _ddl_labels(migration) == ["R", "A", "C", "I"]
    assert list(_raci_role_type().enums) == _ddl_labels(migration)
    assert _raci_role_type().name == "racirole"


def test_stored_label_loads_as_domain_role() -> None:
    process = _raci_role_type().result_processor(postgresql.dialect(), None)
    assert process is not None
    assert [process(label) for label in ("R", "A", "C", "I")] == [
        RACIRole.RESPONSIBLE,
        RACIRole.ACCOUNTABLE,
        RACIRole.CONSULTED,
        RACIRole.INFORMED,
    ]


def test_domain_role_is_written_as_stored_label() -> None:
    process = _raci_role_type().bind_processor(postgresql.dialect())
    assert process is not None
    assert process(RACIRole.ACCOUNTABLE) == "A"
    assert process(RACIRole.INFORMED) == "I"


def test_invalid_stored_label_is_not_silently_mapped() -> None:
    process = _raci_role_type().result_processor(postgresql.dialect(), None)
    assert process is not None
    with pytest.raises(LookupError):
        process("RESPONSIBLE")


def test_no_orm_enum_persists_member_names_when_values_differ() -> None:
    """Structural guard for the IR-3 defect class across every mapped table."""
    offenders = []
    for table in Base.metadata.tables.values():
        for column in table.columns:
            column_type = column.type
            if not isinstance(column_type, sa.Enum) or column_type.enum_class is None:
                continue
            members = list(column_type.enum_class)
            if not all(isinstance(member, enum.Enum) for member in members):
                continue
            names = [member.name for member in members]
            values = [str(member.value) for member in members]
            if names != values and list(column_type.enums) == names:
                offenders.append(f"{table.name}.{column.name}")
    assert offenders == []
