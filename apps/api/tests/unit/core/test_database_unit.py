import time
from unittest.mock import ANY, AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import (
    close_db,
    get_raw_session,
    get_session,
    get_session_with_tenant,
    init_db,
)


@pytest.mark.asyncio
async def test_init_db():
    """Prueba la inicialización de la base de datos."""
    with patch("src.core.database.create_async_engine") as mock_create_engine:
        with patch("src.core.database.async_sessionmaker") as mock_sessionmaker:
            with patch("src.config.settings.database_url", "postgresql://user:pass@localhost/db"):
                await init_db()
                mock_create_engine.assert_called_once()
                mock_sessionmaker.assert_called_once()

@pytest.mark.asyncio
async def test_init_db_sqlite():
    """Prueba la inicialización de la base de datos con sqlite."""
    with patch("src.core.database.create_async_engine") as mock_create_engine:
        with patch("src.core.database.async_sessionmaker"):
            with patch("src.config.settings.database_url", "sqlite+aiosqlite:///test.db"):
                await init_db()
                mock_create_engine.assert_called_once()

@pytest.mark.asyncio
async def test_close_db():
    """Prueba el cierre de la base de datos."""
    mock_engine = AsyncMock()
    with patch("src.core.database._engine", mock_engine):
        await close_db()
        mock_engine.dispose.assert_called_once()

@pytest.mark.asyncio
async def test_get_session_with_tenant_rls():
    """get_session debe configurar RLS si hay tenant_id en request state."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_factory = MagicMock(return_value=mock_session)
    mock_session.__aenter__.return_value = mock_session

    request = MagicMock(spec=Request)
    tenant_id = uuid4()
    request.state.tenant_id = tenant_id

    with patch("src.core.database._session_factory", mock_factory):
        with patch("src.config.settings.database_url", "postgresql://user:pass@localhost/db"):
            async for session in get_session(request):
                assert session == mock_session
                # Verify RLS was set
                mock_session.execute.assert_any_call(ANY)

@pytest.mark.asyncio
async def test_get_session_with_tenant_rls_context_manager():
    """get_session_with_tenant debe configurar RLS."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_factory = MagicMock(return_value=mock_session)
    mock_session.__aenter__.return_value = mock_session

    tenant_id = uuid4()

    with patch("src.core.database._session_factory", mock_factory):
        async with get_session_with_tenant(tenant_id) as session:
            assert session == mock_session
            # Verify RLS was set
            mock_session.execute.assert_any_call(ANY)

@pytest.mark.asyncio
async def test_get_raw_session():
    """get_raw_session no debe configurar RLS."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_factory = MagicMock(return_value=mock_session)
    mock_session.__aenter__.return_value = mock_session

    with patch("src.core.database._session_factory", mock_factory):
        async with get_raw_session() as session:
            assert session == mock_session
            # Verify RLS was NOT set via SET LOCAL
            for call in mock_session.execute.call_args_list:
                args, kwargs = call
                assert "SET LOCAL" not in str(args[0])

@pytest.mark.asyncio
async def test_get_session_exception():
    """get_session debe hacer rollback ante excepciones."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_factory = MagicMock(return_value=mock_session)
    mock_session.__aenter__.return_value = mock_session

    request = MagicMock(spec=Request)
    request.state = MagicMock()

    with patch("src.core.database._session_factory", mock_factory):
        gen = get_session(request)
        try:
            await gen.__anext__()
            await gen.athrow(ValueError("Simulated error"))
        except ValueError:
            pass

        mock_session.rollback.assert_called_once()

@pytest.mark.asyncio
async def test_get_session_with_tenant_exception():
    """get_session_with_tenant debe hacer rollback ante excepciones."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_factory = MagicMock(return_value=mock_session)
    mock_session.__aenter__.return_value = mock_session

    with patch("src.core.database._session_factory", mock_factory):
        try:
            async with get_session_with_tenant(uuid4()):
                raise ValueError("Simulated error")
        except ValueError:
            pass

        mock_session.rollback.assert_called_once()

@pytest.mark.asyncio
async def test_get_session_sqlite():
    """get_session no debe intentar SET LOCAL en sqlite."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_factory = MagicMock(return_value=mock_session)
    mock_session.__aenter__.return_value = mock_session

    request = MagicMock(spec=Request)
    request.state.tenant_id = uuid4()

    with patch("src.core.database._session_factory", mock_factory):
        with patch("src.config.settings.database_url", "sqlite+aiosqlite:///test.db"):
            async for session in get_session(request):
                assert session == mock_session
                # Verify SET LOCAL was NOT called
                for call in mock_session.execute.call_args_list:
                    assert "SET LOCAL" not in str(call[0])

@pytest.mark.asyncio
async def test_get_session_with_tenant_sqlite():
    """get_session_with_tenant no debe intentar SET LOCAL en sqlite."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_factory = MagicMock(return_value=mock_session)
    mock_session.__aenter__.return_value = mock_session

    with patch("src.core.database._session_factory", mock_factory):
        with patch("src.config.settings.database_url", "sqlite+aiosqlite:///test.db"):
            async with get_session_with_tenant(uuid4()) as session:
                assert session == mock_session
                for call in mock_session.execute.call_args_list:
                    assert "SET LOCAL" not in str(call[0])

@pytest.mark.asyncio
async def test_get_raw_session_exception():
    """get_raw_session debe hacer rollback ante excepciones."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_factory = MagicMock(return_value=mock_session)
    mock_session.__aenter__.return_value = mock_session

    with patch("src.core.database._session_factory", mock_factory):
        try:
            async with get_raw_session():
                raise ValueError("Simulated error")
        except ValueError:
            pass

        mock_session.rollback.assert_called_once()

def test_slow_query_logging():
    """Prueba los listeners de detección de queries lentas."""
    from src.core.database import _receive_after_cursor_execute, _receive_before_cursor_execute
    mock_conn = MagicMock()
    mock_conn.info = {}

    # Start timer
    _receive_before_cursor_execute(mock_conn, None, "SELECT 1", None, None, False)
    assert "query_start_time" in mock_conn.info

    # Mock time to be 1 second later
    with patch("time.perf_counter", return_value=time.perf_counter() + 1.0):
        with patch("src.core.database.logger") as mock_logger:
            _receive_after_cursor_execute(mock_conn, None, "SELECT 1", None, None, False)
            mock_logger.warning.assert_called_once()
            assert "slow_query_detected" in mock_logger.warning.call_args[0][0]

def test_initialize_tenant_guc():
    """Prueba el listener de inicialización de GUC."""
    from src.core.database import _initialize_tenant_guc
    mock_dbapi_conn = MagicMock()
    mock_cursor = mock_dbapi_conn.cursor.return_value

    with patch("src.config.settings.database_url", "postgresql://user:pass@localhost/db"):
        _initialize_tenant_guc(mock_dbapi_conn, None)
        mock_cursor.execute.assert_called_with("SET SESSION app.current_tenant = ''")

def test_initialize_tenant_guc_sqlite():
    """Prueba el listener de GUC con sqlite (debe skipear)."""
    from src.core.database import _initialize_tenant_guc
    mock_dbapi_conn = MagicMock()

    with patch("src.config.settings.database_url", "sqlite:///test.db"):
        _initialize_tenant_guc(mock_dbapi_conn, None)
        mock_dbapi_conn.cursor.assert_not_called()

def test_initialize_tenant_guc_exception():
    """Prueba el listener de GUC con excepción (no debe propagar)."""
    from src.core.database import _initialize_tenant_guc
    mock_dbapi_conn = MagicMock()
    mock_dbapi_conn.cursor.side_effect = Exception("Cursor error")

    with patch("src.config.settings.database_url", "postgresql://user:pass@localhost/db"):
        # No debe lanzar excepción
        _initialize_tenant_guc(mock_dbapi_conn, None)
