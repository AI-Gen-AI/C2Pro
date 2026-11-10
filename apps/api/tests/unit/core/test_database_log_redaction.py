from unittest.mock import patch

import pytest

from src.core.database import init_db


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("database_url", "username", "password", "expected_logged_url"),
    [
        (
            "postgresql://short-user:short-password@db.example.test:5432/short_db",
            "short-user",
            "short-password",
            "postgresql+asyncpg://db.example.test:5432/short_db",
        ),
        (
            "postgresql+asyncpg://long%2Buser%40example:"
            "p%40ss%3Aword%2Fwith%3Fspecial%23characters-and-a-long-suffix"
            "@db.example.test:6543/long_db",
            "long%2Buser%40example",
            "p%40ss%3Aword%2Fwith%3Fspecial%23characters-and-a-long-suffix",
            "postgresql+asyncpg://db.example.test:6543/long_db",
        ),
        (
            "postgresql+asyncpg://db.example.test:5432/no_credentials_db",
            None,
            None,
            "postgresql+asyncpg://db.example.test:5432/no_credentials_db",
        ),
        (
            "postgresql://unsafe-user:unsafe-password@db.example.test:not-a-port/db",
            "unsafe-user",
            "unsafe-password",
            "<unparseable database URL>",
        ),
    ],
)
async def test_database_engine_log_redacts_credentials(
    database_url: str,
    username: str | None,
    password: str | None,
    expected_logged_url: str,
) -> None:
    """The database-engine log contains connection metadata, never credentials."""
    with (
        patch("src.core.database.create_async_engine"),
        patch("src.core.database.async_sessionmaker"),
        patch("src.core.database._engine", None),
        patch("src.core.database._session_factory", None),
        patch("src.core.database.logger") as mock_logger,
        patch("src.config.settings.database_url", database_url),
    ):
        await init_db()

    logged_url = next(
        call.kwargs["url"]
        for call in mock_logger.info.call_args_list
        if call.args and call.args[0] == "database_engine_created"
    )

    assert logged_url == expected_logged_url
    if username is not None:
        assert username not in logged_url
    if password is not None:
        assert password not in logged_url
