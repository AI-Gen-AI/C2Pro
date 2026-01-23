"""
C2Pro - Database Unit Tests

Covers core database helpers and RLS session handling.
"""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.core import database as database_module


class DummySession:
    """Minimal async session stub for database helper tests."""

    def __init__(self) -> None:
        self.executed: list[str] = []
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, statement):
        self.executed.append(str(statement))

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


class DummySessionFactory:
    """Callable factory that records created sessions."""

    def __init__(self) -> None:
        self.sessions: list[DummySession] = []

    def __call__(self) -> DummySession:
        session = DummySession()
        self.sessions.append(session)
        return session


@pytest.mark.asyncio
async def test_get_session_requires_init(monkeypatch):
    """get_session should raise if init_db was not called."""
    monkeypatch.setattr(database_module, "_session_factory", None)

    request = SimpleNamespace(state=SimpleNamespace())

    with pytest.raises(RuntimeError, match="Database not initialized"):
        gen = database_module.get_session(request)
        await gen.__anext__()


@pytest.mark.asyncio
async def test_get_session_without_tenant_commits(monkeypatch):
    """get_session should commit without issuing tenant RLS statements."""
    factory = DummySessionFactory()
    monkeypatch.setattr(database_module, "_session_factory", factory)

    request = SimpleNamespace(state=SimpleNamespace())

    gen = database_module.get_session(request)
    session = await gen.__anext__()

    with pytest.raises(StopAsyncIteration):
        await gen.__anext__()

    assert session is factory.sessions[0]
    assert session.committed is True
    assert session.rolled_back is False
    assert session.executed == []


@pytest.mark.asyncio
async def test_get_session_sets_and_resets_tenant(monkeypatch):
    """get_session should set and reset tenant context when tenant_id is present."""
    factory = DummySessionFactory()
    monkeypatch.setattr(database_module, "_session_factory", factory)

    tenant_id = uuid4()
    request = SimpleNamespace(state=SimpleNamespace(tenant_id=tenant_id))

    gen = database_module.get_session(request)
    session = await gen.__anext__()

    with pytest.raises(StopAsyncIteration):
        await gen.__anext__()

    assert any("SET LOCAL app.current_tenant" in stmt for stmt in session.executed)
    assert any("RESET app.current_tenant" in stmt for stmt in session.executed)


@pytest.mark.asyncio
async def test_get_session_rolls_back_and_resets(monkeypatch):
    """get_session should rollback and reset tenant context on exceptions."""
    factory = DummySessionFactory()
    monkeypatch.setattr(database_module, "_session_factory", factory)

    tenant_id = uuid4()
    request = SimpleNamespace(state=SimpleNamespace(tenant_id=tenant_id))

    gen = database_module.get_session(request)
    session = await gen.__anext__()

    with pytest.raises(RuntimeError, match="boom"):
        await gen.athrow(RuntimeError("boom"))

    assert session.rolled_back is True
    assert any("RESET app.current_tenant" in stmt for stmt in session.executed)


@pytest.mark.asyncio
async def test_get_session_with_tenant_sets_and_resets(monkeypatch):
    """get_session_with_tenant should set and reset tenant context."""
    factory = DummySessionFactory()
    monkeypatch.setattr(database_module, "_session_factory", factory)

    tenant_id = uuid4()

    async with database_module.get_session_with_tenant(tenant_id) as session:
        assert session is factory.sessions[0]

    assert session.committed is True
    assert any("SET LOCAL app.current_tenant" in stmt for stmt in session.executed)
    assert any("RESET app.current_tenant" in stmt for stmt in session.executed)


@pytest.mark.asyncio
async def test_get_raw_session_avoids_tenant_context(monkeypatch):
    """get_raw_session should not issue tenant context statements."""
    factory = DummySessionFactory()
    monkeypatch.setattr(database_module, "_session_factory", factory)

    async with database_module.get_raw_session() as session:
        assert session is factory.sessions[0]

    assert session.executed == []
