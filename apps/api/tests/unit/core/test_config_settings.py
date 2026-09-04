import pytest

from src.config import Settings


def _set_required_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("C2PRO_AI_MOCK", raising=False)
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


def test_production_settings_reject_localhost_cors_origins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_settings_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql://prod-user:prod-pass@supabase.example.com/app")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CORS_ORIGINS", '["http://localhost:3000"]')

    with pytest.raises(ValueError, match="localhost origins are not allowed"):
        Settings(_env_file=None)


def test_production_settings_reject_wildcard_cors_origins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_settings_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql://prod-user:prod-pass@supabase.example.com/app")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CORS_ORIGINS", '["*"]')

    with pytest.raises(ValueError, match="wildcard CORS"):
        Settings(_env_file=None)


def test_production_settings_reject_ai_mock_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TS-UD-OPS-DOCFLOW-B-002: production can never start with fabricated AI responses."""
    _set_required_settings_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql://prod-user:prod-pass@supabase.example.com/app")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CORS_ORIGINS", '["https://c2pro.io"]')
    monkeypatch.setenv("C2PRO_AI_MOCK", "1")

    with pytest.raises(ValueError, match="C2PRO_AI_MOCK"):
        Settings(_env_file=None)


def test_production_settings_expand_c2pro_www_origin_pair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_settings_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql://prod-user:prod-pass@supabase.example.com/app")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CORS_ORIGINS", '["https://c2pro.io"]')

    settings = Settings(_env_file=None)

    assert settings.cors_origins == [
        "https://c2pro.io",
        "https://www.c2pro.io",
    ]


def test_production_settings_expand_c2pro_apex_from_www_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_settings_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql://prod-user:prod-pass@supabase.example.com/app")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CORS_ORIGINS", '["https://www.c2pro.io"]')

    settings = Settings(_env_file=None)

    assert settings.cors_origins == [
        "https://www.c2pro.io",
        "https://c2pro.io",
    ]


def test_test_settings_allow_missing_supabase_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/c2pro_test"
    )
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv(
        "JWT_SECRET_KEY", "test-secret-key-min-32-chars-required-for-testing-purposes-only"
    )

    settings = Settings(_env_file=None)

    assert settings.supabase_url == "https://test.supabase.local"
    assert settings.supabase_anon_key == "test-anon-key"
    assert settings.supabase_service_role_key == "test-service-role-key"
    # The placeholder is never dialled, but it is still a URL the codebase
    # hands out, and a clear-text scheme in one is a security finding whether
    # or not anything connects to it. Nothing here needs http://, so nothing
    # here uses it.
    assert not settings.supabase_url.startswith("http://")
