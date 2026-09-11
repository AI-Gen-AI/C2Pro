import pytest

from src.config import Settings
from tests.unit.core.test_config_settings import _set_required_settings_env


def test_admin_ops_database_url_async_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_settings_env(monkeypatch)
    monkeypatch.delenv("ADMIN_OPS_DATABASE_URL", raising=False)
    settings = Settings(_env_file=None)
    with pytest.raises(RuntimeError, match="ADMIN_OPS_DATABASE_URL is not configured"):
        _ = settings.admin_ops_database_url_async


def test_admin_ops_database_url_async_normalization(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_settings_env(monkeypatch)
    monkeypatch.setenv("ADMIN_OPS_DATABASE_URL", "postgresql://admin:pass@host:5432/db")
    settings = Settings(_env_file=None)
    assert settings.admin_ops_database_url_async == "postgresql+asyncpg://admin:pass@host:5432/db"


def test_admin_ops_database_url_async_already_async(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_settings_env(monkeypatch)
    monkeypatch.setenv("ADMIN_OPS_DATABASE_URL", "postgresql+asyncpg://admin:pass@host:5432/db")
    settings = Settings(_env_file=None)
    assert settings.admin_ops_database_url_async == "postgresql+asyncpg://admin:pass@host:5432/db"
