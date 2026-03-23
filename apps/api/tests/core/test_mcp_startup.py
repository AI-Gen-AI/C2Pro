"""
MCP Startup Initialization Tests

Refers to Suite ID: TS-CORE-MCP-STARTUP-001.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI

from src.main import create_application, lifespan
from src.main import settings as main_settings


@pytest.mark.asyncio
async def test_lifespan_initializes_mcp_server_on_startup() -> None:
    """
    Refers to Suite ID: TS-CORE-MCP-STARTUP-001.

    Startup should eagerly initialize the MCP singleton so MCP endpoints do not
    pay first-request initialization cost or fail due to missing startup wiring.
    """
    app = FastAPI()
    event_bus = SimpleNamespace(close=AsyncMock())

    with (
        patch("src.main.init_db", new=AsyncMock()),
        patch("src.main.init_cache", new=AsyncMock()),
        patch("src.main.close_db", new=AsyncMock()),
        patch("src.main.close_cache", new=AsyncMock()),
        patch("src.main.build_event_bus", return_value=event_bus),
        patch("src.main.get_mcp_server", create=True) as mock_get_mcp_server,
        patch("src.main.logger", new=MagicMock()),
        patch.object(main_settings, "sentry_dsn", None),
    ):
        async with lifespan(app):
            pass

    mock_get_mcp_server.assert_called_once_with()


@pytest.mark.asyncio
async def test_lifespan_initializes_and_flushes_sentry_when_dsn_configured() -> None:
    """
    Refers to Suite ID: TS-CORE-MCP-STARTUP-001.

    Startup should initialize Sentry when configured and shutdown should flush it.
    """
    app = FastAPI()
    event_bus = SimpleNamespace(close=AsyncMock())

    with (
        patch("src.main.init_db", new=AsyncMock()),
        patch("src.main.init_cache", new=AsyncMock()),
        patch("src.main.close_db", new=AsyncMock()),
        patch("src.main.close_cache", new=AsyncMock()),
        patch("src.main.build_event_bus", return_value=event_bus),
        patch("src.main.get_mcp_server", create=True),
        patch("src.main.sentry_sdk.init") as mock_sentry_init,
        patch("src.main.sentry_sdk.flush") as mock_sentry_flush,
        patch("src.main.logger", new=MagicMock()),
        patch.object(main_settings, "sentry_dsn", "https://example@sentry.io/1"),
        patch.object(main_settings, "sentry_environment", "staging"),
        patch.object(main_settings, "sentry_traces_sample_rate", 0.25),
    ):
        async with lifespan(app):
            pass

    mock_sentry_init.assert_called_once_with(
        dsn="https://example@sentry.io/1",
        environment="staging",
        traces_sample_rate=0.25,
    )
    mock_sentry_flush.assert_called_once_with()


@pytest.mark.asyncio
async def test_lifespan_skips_sentry_when_dsn_missing() -> None:
    """
    Refers to Suite ID: TS-CORE-MCP-STARTUP-001.

    Startup should not initialize or flush Sentry when no DSN is configured.
    """
    app = FastAPI()
    event_bus = SimpleNamespace(close=AsyncMock())

    with (
        patch("src.main.init_db", new=AsyncMock()),
        patch("src.main.init_cache", new=AsyncMock()),
        patch("src.main.close_db", new=AsyncMock()),
        patch("src.main.close_cache", new=AsyncMock()),
        patch("src.main.build_event_bus", return_value=event_bus),
        patch("src.main.get_mcp_server", create=True),
        patch("src.main.sentry_sdk.init") as mock_sentry_init,
        patch("src.main.sentry_sdk.flush") as mock_sentry_flush,
        patch("src.main.logger", new=MagicMock()),
        patch.object(main_settings, "sentry_dsn", None),
    ):
        async with lifespan(app):
            pass

    mock_sentry_init.assert_not_called()
    mock_sentry_flush.assert_not_called()


def test_create_application_skips_mcp_router_when_import_fails() -> None:
    """
    Refers to Suite ID: TS-CORE-MCP-STARTUP-001.

    The API should still boot when the MCP router cannot be imported.
    """
    with (
        patch("src.main._load_mcp_router", side_effect=ImportError("mcp unavailable")),
        patch("src.main.logger", new=MagicMock()) as mock_logger,
    ):
        app = create_application()

    paths = {route.path for route in app.routes}

    assert not any("/mcp" in path for path in paths)
    warning_calls = [
        call for call in mock_logger.warning.call_args_list
        if call[0] and call[0][0] == "router_unavailable"
    ]
    assert warning_calls, "MCP import failure should be logged as a warning"
