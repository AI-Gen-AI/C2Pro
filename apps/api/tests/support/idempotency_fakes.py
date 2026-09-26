"""Shared async-session fakes for procurement repository idempotency tests.

Both the BOM and WBS ``replace_for_source_document`` tests exercise the same
repository shape (execute/add/add_all/flush/refresh), so the fake lives here in
a single place instead of being copied per test module.
"""

from __future__ import annotations

from uuid import uuid4


class ScalarResult:
    """Minimal stand-in for a SQLAlchemy ``Result`` scalar accessor."""

    def __init__(self, value: object) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object:
        return self._value


class FakeSession:
    """In-memory async session double that records statements and ORMs."""

    def __init__(self) -> None:
        self.statements: list[object] = []
        self.added: list[object] = []
        self.flushed = 0
        self.refreshed: list[object] = []

    async def execute(self, statement: object) -> ScalarResult:
        self.statements.append(statement)
        return ScalarResult(uuid4())

    def add(self, orm: object) -> None:
        self.added.append(orm)

    def add_all(self, orms: list[object]) -> None:
        self.added.extend(orms)

    async def flush(self) -> None:
        self.flushed += 1

    async def refresh(self, orm: object) -> None:
        self.refreshed.append(orm)
