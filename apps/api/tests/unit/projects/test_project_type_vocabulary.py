"""IR-6: one project-type vocabulary across the database, ORM, domain and HTTP layer.

20260808_0001 extended the ``projecttype`` enum with the values the project creation wizard
offers (epc, civil, ...) and the HTTP validator accepted them, but the ORM column and the domain
``ProjectType`` kept only the five legacy values. A project created from the wizard was
therefore written successfully and then failed to load (``LookupError`` in the ORM,
``ValueError`` in ``ProjectType(...)``), breaking project lists, detail, reporting and health.
"""

from __future__ import annotations

import re
from pathlib import Path

import sqlalchemy as sa

from src.projects.adapters.http.router import VALID_PROJECT_TYPES
from src.projects.adapters.persistence.models import ProjectORM
from src.projects.domain.models import ProjectType

VERSIONS = Path(__file__).resolve().parents[3] / "alembic" / "versions"
LEGACY = {"construction", "engineering", "industrial", "infrastructure", "other"}


def _extension_migration_values() -> set[str]:
    source = (VERSIONS / "20260808_0001_extend_projecttype_enum.py").read_text(encoding="utf-8")
    block = re.search(r"_NEW_VALUES = \[(.*?)\]", source, re.DOTALL)
    assert block, "projecttype extension values not found"
    return set(re.findall(r'"([a-z_]+)"', block.group(1)))


def test_domain_vocabulary_is_every_database_label() -> None:
    assert {member.value for member in ProjectType} == LEGACY | _extension_migration_values()


def test_orm_column_accepts_exactly_the_domain_vocabulary() -> None:
    column_type = ProjectORM.__table__.c.project_type.type
    assert isinstance(column_type, sa.Enum)
    assert column_type.name == "projecttype"
    assert set(column_type.enums) == {member.value for member in ProjectType}


def test_http_validation_uses_the_same_vocabulary() -> None:
    assert set(VALID_PROJECT_TYPES) == {member.value for member in ProjectType}


def test_an_extended_type_loads_through_the_orm_result_processor() -> None:
    process = ProjectORM.__table__.c.project_type.type.result_processor(sa.dialects.postgresql.dialect(), None)
    value = "oil_gas"
    assert (process(value) if process else value) == "oil_gas"
    assert ProjectType("oil_gas").value == "oil_gas"
