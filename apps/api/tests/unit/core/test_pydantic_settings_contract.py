from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.config import Settings
from src.core.resilience.config import CircuitBreakerSettings
from tests.unit.core.test_config_settings import _set_required_settings_env


def _set_test_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide only the required runtime fields while keeping source tests hermetic."""
    _set_required_settings_env(monkeypatch)
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://settings-user:settings-pass@settings.example.test/c2pro",
    )
    monkeypatch.setenv("ENVIRONMENT", "test")


def test_settings_source_precedence_init_over_env_over_dotenv_over_default(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _set_test_runtime(monkeypatch)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("APP_NAME=dotenv-name\n", encoding="utf-8")
    monkeypatch.setenv("APP_NAME", "env-name")

    assert Settings(app_name="init-name").app_name == "init-name"
    assert Settings().app_name == "env-name"

    monkeypatch.delenv("APP_NAME")
    assert Settings().app_name == "dotenv-name"

    assert Settings(_env_file=None).app_name == "C2Pro API"


def test_settings_reads_default_dotenv_from_current_working_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    for key in (
        "TEST_DATABASE_URL",
        "DATABASE_URL",
        "JWT_SECRET_KEY",
        "ENVIRONMENT",
        "APP_NAME",
    ):
        monkeypatch.delenv(key, raising=False)

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "\n".join(
            (
                "ENVIRONMENT=test",
                "DATABASE_URL=postgresql://dotenv-user:dotenv-pass@dotenv.example.test/c2pro",
                "JWT_SECRET_KEY=dotenv-secret-key-min-32-chars-for-settings-contract",
                "APP_NAME=dotenv-c2pro",
                "",
            )
        ),
        encoding="utf-8",
    )

    settings = Settings()

    assert settings.app_name == "dotenv-c2pro"
    assert settings.database_url.startswith("postgresql://dotenv-user:")


def test_aliaschoices_constructor_field_name_overrides_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_test_runtime(monkeypatch)
    monkeypatch.setenv(
        "TEST_DATABASE_URL",
        "postgresql://test-env:test-env@settings.example.test/c2pro",
    )

    settings = Settings(
        database_url="postgresql://init-user:init-pass@settings.example.test/c2pro",
        _env_file=None,
    )

    assert settings.database_url == "postgresql://init-user:init-pass@settings.example.test/c2pro"


def test_aliaschoices_environment_lookup_is_case_insensitive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_test_runtime(monkeypatch)
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    monkeypatch.setenv(
        "test_database_url",
        "postgresql://lowercase:lowercase@settings.example.test/c2pro",
    )

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql://lowercase:lowercase@settings.example.test/c2pro"


def test_nodecode_platform_operator_csv_contract_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_test_runtime(monkeypatch)
    monkeypatch.setenv(
        "PLATFORM_OPERATOR_USER_IDS",
        " user_alpha, ,user_Beta, user_alpha ",
    )

    settings = Settings(_env_file=None)

    assert settings.platform_operator_user_ids == ["user_alpha", "user_Beta"]


def test_nodecode_platform_operator_csv_contract_from_dotenv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    for key in (
        "TEST_DATABASE_URL",
        "DATABASE_URL",
        "JWT_SECRET_KEY",
        "ENVIRONMENT",
        "PLATFORM_OPERATOR_USER_IDS",
    ):
        monkeypatch.delenv(key, raising=False)

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "\n".join(
            (
                "ENVIRONMENT=test",
                "DATABASE_URL=postgresql://dotenv-user:dotenv-pass@dotenv.example.test/c2pro",
                "JWT_SECRET_KEY=dotenv-secret-key-min-32-chars-for-settings-contract",
                "PLATFORM_OPERATOR_USER_IDS=user_dot_a,user_dot_b",
                "",
            )
        ),
        encoding="utf-8",
    )

    settings = Settings()

    assert settings.platform_operator_user_ids == ["user_dot_a", "user_dot_b"]


def test_complex_environment_fields_keep_json_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_test_runtime(monkeypatch)
    monkeypatch.setenv("CORS_ORIGINS", '["https://one.example.test","https://two.example.test"]')
    monkeypatch.setenv(
        "INTEGRATION_API_KEYS",
        '{"key-live-a":"tenant-a","key-live-b":"tenant-b"}',
    )

    settings = Settings(_env_file=None)

    assert settings.cors_origins == [
        "https://one.example.test",
        "https://two.example.test",
    ]
    assert settings.integration_api_keys == {
        "key-live-a": "tenant-a",
        "key-live-b": "tenant-b",
    }


def test_secretstr_is_masked_but_explicit_value_access_is_preserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_test_runtime(monkeypatch)
    token = "settings-contract-super-secret"
    monkeypatch.setenv("SECRET_CHANNEL_TOKEN", token)

    settings = Settings(_env_file=None)

    assert settings.secret_channel_token is not None
    assert settings.secret_channel_token.get_secret_value() == token
    assert token not in str(settings.secret_channel_token)
    assert token not in repr(settings.secret_channel_token)


def test_invalid_environment_value_fails_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_test_runtime(monkeypatch)
    monkeypatch.setenv("DB_POOL_SIZE", "0")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_staging_non_production_auth_fallback_is_coerced_to_deny(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_test_runtime(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("CORS_ORIGINS", '["https://staging.c2pro.io"]')
    monkeypatch.setenv("AUTH_BOOTSTRAP_FALLBACK_MODE", "non_production")

    settings = Settings(_env_file=None)

    assert settings.auth_bootstrap_fallback_mode == "deny"


def test_circuit_breaker_prefix_and_case_insensitive_environment_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_FAILURE_THRESHOLD", "99")
    monkeypatch.setenv("CB_OPENAI_FAILURE_THRESHOLD", "11")
    monkeypatch.delenv("CB_REDIS_FAILURE_THRESHOLD", raising=False)
    monkeypatch.setenv("cb_redis_failure_threshold", "7")

    settings = CircuitBreakerSettings(_env_file=None)

    assert settings.openai_failure_threshold == 11
    assert settings.redis_failure_threshold == 7


def test_circuit_breaker_default_dotenv_honours_cb_prefix(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    for key in (
        "CB_ANTHROPIC_FAILURE_THRESHOLD",
        "ANTHROPIC_FAILURE_THRESHOLD",
    ):
        monkeypatch.delenv(key, raising=False)

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "CB_ANTHROPIC_FAILURE_THRESHOLD=13\n",
        encoding="utf-8",
    )

    settings = CircuitBreakerSettings()

    assert settings.anthropic_failure_threshold == 13
