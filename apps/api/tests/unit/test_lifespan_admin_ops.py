from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI

from src.main import lifespan


@pytest.mark.asyncio
async def test_lifespan_participates_and_degraded_does_not_break() -> None:
    # We patch all the external service initializations so we can run lifespan in isolation
    app = FastAPI()

    with (
        patch("src.main.init_db", new_callable=AsyncMock) as mock_init_db,
        patch("src.main.close_db", new_callable=AsyncMock) as mock_close_db,
        patch("src.core.database.init_admin_ops_db", new_callable=AsyncMock) as mock_init_admin,
        patch("src.core.database.close_admin_ops_db", new_callable=AsyncMock) as mock_close_admin,
        patch("src.main.init_cache", new_callable=AsyncMock) as mock_init_cache,
        patch("src.main.close_cache", new_callable=AsyncMock) as mock_close_cache,
        patch("src.main.ensure_checkpointer_ready", new_callable=AsyncMock),
        patch("src.main.build_event_bus") as mock_build_event_bus,
        patch("src.main.get_mcp_server"),
        patch("src.main.build_decision_intelligence_services") as mock_build_di_services,
    ):
        # Mock event bus
        mock_event_bus = MagicMock()
        mock_event_bus.close = AsyncMock()
        mock_build_event_bus.return_value = mock_event_bus

        # Mock Decision Intelligence Services
        mock_di_services = MagicMock()
        mock_di_services.ingestion = MagicMock()
        mock_di_services.extraction = MagicMock()
        mock_di_services.retrieval = MagicMock()
        mock_di_services.coherence = MagicMock()
        mock_di_services.hitl = MagicMock()
        mock_build_di_services.return_value = mock_di_services

        # Act: Run the lifespan context manager
        async with lifespan(app):
            # Assert startup actions
            mock_init_db.assert_called_once()
            mock_init_admin.assert_called_once()
            mock_init_cache.assert_called_once()

        # Assert shutdown actions
        mock_close_db.assert_called_once()
        mock_close_admin.assert_called_once()
        mock_close_cache.assert_called_once()
        mock_event_bus.close.assert_called_once()


@pytest.mark.asyncio
async def test_lifespan_degraded_admin_ops_does_not_break_app() -> None:
    # Run real init_admin_ops_db under exception scenario
    from src.config import settings
    from src.core.database import init_admin_ops_db

    # We patch settings to have a malformed DSN, which will cause create_async_engine to raise an exception
    with (
        patch.object(settings, "admin_ops_database_url", "garbage-protocol://bad"),
        patch("src.core.database.logger") as mock_db_logger,
    ):
        # Run real init_admin_ops_db
        await init_admin_ops_db()

        # It should catch the exception, set globals to None, and log error
        from src.core.database import _admin_ops_engine, _admin_ops_session_factory

        assert _admin_ops_engine is None
        assert _admin_ops_session_factory is None
        assert mock_db_logger.error.called
        call_args = mock_db_logger.error.call_args[0]
        assert call_args[0] == "admin_ops_db_init_failed"


@pytest.mark.asyncio
async def test_lifespan_continues_with_degraded_admin_ops() -> None:
    """MEDIUM 1: Prove ordinary lifespan continues when the REAL admin-ops initialization takes its degraded path."""
    app = FastAPI()

    from src.config import settings

    # We patch all external services except init_admin_ops_db and close_admin_ops_db.
    # This executes the actual production logic of those two functions.
    with (
        patch("src.main.init_db", new_callable=AsyncMock) as mock_init_db,
        patch("src.main.close_db", new_callable=AsyncMock) as mock_close_db,
        patch("src.main.init_cache", new_callable=AsyncMock) as mock_init_cache,
        patch("src.main.close_cache", new_callable=AsyncMock) as mock_close_cache,
        patch("src.main.ensure_checkpointer_ready", new_callable=AsyncMock),
        patch("src.main.build_event_bus") as mock_build_event_bus,
        patch("src.main.get_mcp_server"),
        patch("src.main.build_decision_intelligence_services") as mock_build_di_services,
        patch.object(settings, "admin_ops_database_url", None),
        patch("src.core.database.logger") as mock_db_logger,
    ):
        # Mock event bus
        mock_event_bus = MagicMock()
        mock_event_bus.close = AsyncMock()
        mock_build_event_bus.return_value = mock_event_bus

        # Mock Decision Intelligence Services
        mock_di_services = MagicMock()
        mock_di_services.ingestion = MagicMock()
        mock_di_services.extraction = MagicMock()
        mock_di_services.retrieval = MagicMock()
        mock_di_services.coherence = MagicMock()
        mock_di_services.hitl = MagicMock()
        mock_build_di_services.return_value = mock_di_services

        # Act: Enter the actual application lifespan while admin ops DB is unconfigured
        async with lifespan(app):
            # Assert startup actions of other mocked services were called
            mock_init_db.assert_called_once()
            mock_init_cache.assert_called_once()

            # Assert that the actual degraded admin initialization path executed
            # It should have logged "admin_ops_db_unconfigured_at_startup"
            assert mock_db_logger.warning.called
            warning_calls = [call[0][0] for call in mock_db_logger.warning.call_args_list]
            assert "admin_ops_db_unconfigured_at_startup" in warning_calls

            # Ensure globals are None or reset (i.e. no engine/factory created)
            from src.core.database import _admin_ops_engine, _admin_ops_session_factory

            assert _admin_ops_engine is None
            assert _admin_ops_session_factory is None

        # Assert shutdown actions of other mocked services were called
        mock_close_db.assert_called_once()
        mock_close_cache.assert_called_once()
        mock_event_bus.close.assert_called_once()
