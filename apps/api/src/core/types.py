"""
C2Pro - Custom SQLAlchemy Types

Tipos personalizados que funcionan tanto en PostgreSQL como SQLite.
"""

from typing import Any

from sqlalchemy import JSON, TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine.interfaces import Dialect


class JSONType(TypeDecorator[JSON]):
    """
    JSON type que usa JSONB en PostgreSQL y JSON en otros dialectos.

    Esto permite que los tests funcionen con SQLite mientras que
    en producción se usa JSONB de PostgreSQL para mejor performance.
    """

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        else:
            return dialect.type_descriptor(JSON())
