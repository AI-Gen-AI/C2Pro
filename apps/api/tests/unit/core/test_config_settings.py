import pytest

from src.config import Settings


def _set_required_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "test-anon-key")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
    monkeypatch.setenv(
        "JWT_SECRET_KEY", "test-secret-key-min-32-chars-required-for-testing-purposes-only"
    )


def test_settings_prefer_test_database_url_over_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_settings_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql://prod-user:prod-pass@supabase.example.com/app")
    monkeypatch.setenv(
        "TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/c2pro_test"
    )

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql://postgres:postgres@localhost:5433/c2pro_test"


def test_settings_use_database_url_when_test_database_url_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_settings_env(monkeypatch)
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://prod-user:prod-pass@supabase.example.com/app"
    )

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql://prod-user:prod-pass@supabase.example.com/app"
