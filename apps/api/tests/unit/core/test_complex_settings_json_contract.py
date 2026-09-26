"""Issue #667: JSON-only contract for complex environment-backed settings.

pydantic-settings decodes complex (list/dict) fields from env and dotenv
sources as JSON *before* any ``mode="before"`` validator runs, so a raw CSV
(or empty) value fails with ``SettingsError`` and never reaches C2Pro code.

Canonical environment contract:
- JSON_ONLY: CORS_ORIGINS, CORS_METHODS, CORS_HEADERS, ALLOWED_DOCUMENT_TYPES,
  BUDGET_ALERT_ADMIN_EMAILS, INTEGRATION_API_KEYS.
- Intentional exception: PLATFORM_OPERATOR_USER_IDS is ``NoDecode`` + CSV.

Direct constructor input is a separate path (no source decoding) and keeps
its documented compatibility for cors_origins / budget_alert_admin_emails /
integration_api_keys; values of the wrong shape fail closed instead of being
silently coerced to empty.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsError

from src.config import Settings
from tests.unit.core.test_config_settings import _set_required_settings_env

COMPLEX_ENV_FIELDS = {
    "CORS_ORIGINS": "cors_origins",
    "CORS_METHODS": "cors_methods",
    "CORS_HEADERS": "cors_headers",
    "ALLOWED_DOCUMENT_TYPES": "allowed_document_types",
    "BUDGET_ALERT_ADMIN_EMAILS": "budget_alert_admin_emails",
    "INTEGRATION_API_KEYS": "integration_api_keys",
}


@pytest.fixture
def runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> pytest.MonkeyPatch:
    """Hermetic test runtime: required settings only, no ambient complex env, no .env."""
    _set_required_settings_env(monkeypatch)
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://contract:contract@settings.example.test/c2pro"
    )
    monkeypatch.setenv("ENVIRONMENT", "test")
    for name in (*COMPLEX_ENV_FIELDS, "PLATFORM_OPERATOR_USER_IDS"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    return monkeypatch


def _write_dotenv(tmp_path: Path, line: str) -> None:
    (tmp_path / ".env").write_text(line + "\n", encoding="utf-8")


# ------------------------------------------------------------------ JSON env
@pytest.mark.parametrize(
    ("env_name", "raw", "expected"),
    [
        (
            "CORS_ORIGINS",
            '["http://localhost:3000","http://localhost:3001"]',
            ["http://localhost:3000", "http://localhost:3001"],
        ),
        ("CORS_METHODS", '["GET","POST"]', ["GET", "POST"]),
        (
            "CORS_HEADERS",
            '["Authorization","X-Request-ID"]',
            ["Authorization", "X-Request-ID"],
        ),
        ("ALLOWED_DOCUMENT_TYPES", '[".pdf",".docx"]', [".pdf", ".docx"]),
        ("BUDGET_ALERT_ADMIN_EMAILS", '["admin@example.com"]', ["admin@example.com"]),
        ("INTEGRATION_API_KEYS", '{"key-a":"tenant-a"}', {"key-a": "tenant-a"}),
    ],
)
def test_valid_json_environment_values_parse(
    runtime: pytest.MonkeyPatch, env_name: str, raw: str, expected: object
) -> None:
    runtime.setenv(env_name, raw)

    settings = Settings(_env_file=None)

    assert getattr(settings, COMPLEX_ENV_FIELDS[env_name]) == expected


@pytest.mark.parametrize(
    ("env_name", "raw", "expected"),
    [
        (
            "CORS_ORIGINS",
            '["https://c2pro.io"]',
            ["https://c2pro.io", "https://www.c2pro.io"],
        ),
        (
            "BUDGET_ALERT_ADMIN_EMAILS",
            '["a@example.com","b@example.com"]',
            ["a@example.com", "b@example.com"],
        ),
        ("INTEGRATION_API_KEYS", '{"k1":"t1","k2":"t2"}', {"k1": "t1", "k2": "t2"}),
    ],
)
def test_valid_json_dotenv_values_parse(
    runtime: pytest.MonkeyPatch,
    tmp_path: Path,
    env_name: str,
    raw: str,
    expected: object,
) -> None:
    _write_dotenv(tmp_path, f"{env_name}={raw}")

    settings = Settings()

    assert getattr(settings, COMPLEX_ENV_FIELDS[env_name]) == expected


def test_empty_json_array_and_object_are_the_way_to_configure_empty(
    runtime: pytest.MonkeyPatch,
) -> None:
    runtime.setenv("CORS_ORIGINS", "[]")
    runtime.setenv("BUDGET_ALERT_ADMIN_EMAILS", "[]")
    runtime.setenv("INTEGRATION_API_KEYS", "{}")

    settings = Settings(_env_file=None)

    assert settings.cors_origins == []
    assert settings.budget_alert_admin_emails == []
    assert settings.integration_api_keys == {}


# ------------------------------------------------------------------ CSV / non-JSON env
@pytest.mark.parametrize(
    ("env_name", "raw"),
    [
        ("CORS_ORIGINS", "http://localhost:3000,http://localhost:3001"),
        ("CORS_ORIGINS", "http://localhost:3000"),
        ("CORS_METHODS", "GET,POST"),
        ("CORS_HEADERS", "Authorization,X-Request-ID"),
        ("ALLOWED_DOCUMENT_TYPES", ".pdf,.docx"),
        ("BUDGET_ALERT_ADMIN_EMAILS", "admin@example.com,finops@example.com"),
        ("BUDGET_ALERT_ADMIN_EMAILS", "admin@example.com"),
        ("INTEGRATION_API_KEYS", "key-a:tenant-a"),
        ("INTEGRATION_API_KEYS", "not json"),
        ("INTEGRATION_API_KEYS", '{"key-a": "tenant-a"'),
    ],
)
def test_raw_csv_or_malformed_environment_value_raises_settings_error(
    runtime: pytest.MonkeyPatch, env_name: str, raw: str
) -> None:
    runtime.setenv(env_name, raw)

    with pytest.raises(SettingsError, match=COMPLEX_ENV_FIELDS[env_name]):
        Settings(_env_file=None)


@pytest.mark.parametrize("env_name", sorted(COMPLEX_ENV_FIELDS))
def test_empty_environment_value_is_not_an_empty_list(
    runtime: pytest.MonkeyPatch, env_name: str
) -> None:
    runtime.setenv(env_name, "")

    with pytest.raises(SettingsError, match=COMPLEX_ENV_FIELDS[env_name]):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    ("env_name", "raw"),
    [
        ("CORS_ORIGINS", "http://localhost:3000,http://localhost:3001"),
        ("BUDGET_ALERT_ADMIN_EMAILS", "admin@example.com,finops@example.com"),
        ("INTEGRATION_API_KEYS", "key-a:tenant-a"),
    ],
)
def test_raw_csv_dotenv_value_raises_settings_error(
    runtime: pytest.MonkeyPatch, tmp_path: Path, env_name: str, raw: str
) -> None:
    _write_dotenv(tmp_path, f"{env_name}={raw}")

    with pytest.raises(SettingsError, match=COMPLEX_ENV_FIELDS[env_name]):
        Settings()


# ------------------------------------------------------------------ wrong JSON shape fails closed
@pytest.mark.parametrize(
    ("env_name", "raw"),
    [
        ("CORS_ORIGINS", '{"http://localhost:3000": true}'),
        ("CORS_ORIGINS", "42"),
        ("BUDGET_ALERT_ADMIN_EMAILS", '{"admin": "admin@example.com"}'),
        ("INTEGRATION_API_KEYS", '["key-a","tenant-a"]'),
        ("INTEGRATION_API_KEYS", "42"),
    ],
)
def test_valid_json_of_the_wrong_shape_fails_closed(
    runtime: pytest.MonkeyPatch, env_name: str, raw: str
) -> None:
    """Previously coerced to [] / {} silently; a misconfiguration must be loud."""
    runtime.setenv(env_name, raw)

    with pytest.raises(ValidationError, match=f"(?i){COMPLEX_ENV_FIELDS[env_name]}"):
        Settings(_env_file=None)


# ------------------------------------------------------------------ PLATFORM_OPERATOR_USER_IDS exception
def test_platform_operator_ids_csv_environment_passes(
    runtime: pytest.MonkeyPatch,
) -> None:
    runtime.setenv(
        "PLATFORM_OPERATOR_USER_IDS", " user_alpha, ,user_Beta , user_alpha "
    )

    settings = Settings(_env_file=None)

    assert settings.platform_operator_user_ids == ["user_alpha", "user_Beta"]


def test_platform_operator_ids_csv_dotenv_passes(
    runtime: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _write_dotenv(
        tmp_path, "PLATFORM_OPERATOR_USER_IDS=user_dot_a,user_dot_b,user_dot_a"
    )

    settings = Settings()

    assert settings.platform_operator_user_ids == ["user_dot_a", "user_dot_b"]


@pytest.mark.parametrize("raw", ['["user_alpha","user_beta"]', '["user_alpha"]'])
def test_platform_operator_ids_json_array_environment_is_rejected(
    runtime: pytest.MonkeyPatch, raw: str
) -> None:
    runtime.setenv("PLATFORM_OPERATOR_USER_IDS", raw)

    with pytest.raises(ValidationError, match="Clerk user IDs"):
        Settings(_env_file=None)


def test_platform_operator_ids_constructor_list_is_rejected(
    runtime: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValidationError, match="CSV of Clerk user IDs"):
        Settings(_env_file=None, platform_operator_user_ids=["user_alpha"])


# ------------------------------------------------------------------ constructor semantics (no source decoding)
def test_constructor_accepts_lists_and_csv_strings_for_cors_origins(
    runtime: pytest.MonkeyPatch,
) -> None:
    assert Settings(_env_file=None, cors_origins=["https://c2pro.io"]).cors_origins == [
        "https://c2pro.io",
        "https://www.c2pro.io",
    ]
    assert Settings(
        _env_file=None, cors_origins="http://a.test, http://b.test"
    ).cors_origins == [
        "http://a.test",
        "http://b.test",
    ]
    assert Settings(_env_file=None, cors_origins='["http://a.test"]').cors_origins == [
        "http://a.test"
    ]
    assert Settings(_env_file=None, cors_origins="").cors_origins == []


def test_constructor_accepts_lists_and_csv_strings_for_budget_emails(
    runtime: pytest.MonkeyPatch,
) -> None:
    assert Settings(
        _env_file=None, budget_alert_admin_emails=[" a@example.com ", ""]
    ).budget_alert_admin_emails == ["a@example.com"]
    assert Settings(
        _env_file=None, budget_alert_admin_emails="a@example.com, b@example.com"
    ).budget_alert_admin_emails == ["a@example.com", "b@example.com"]
    # a JSON array string is parsed as JSON (same as cors_origins), not as one CSV item
    assert Settings(
        _env_file=None, budget_alert_admin_emails='["a@example.com","b@example.com"]'
    ).budget_alert_admin_emails == ["a@example.com", "b@example.com"]


def test_constructor_accepts_dict_or_json_object_for_integration_keys(
    runtime: pytest.MonkeyPatch,
) -> None:
    assert Settings(
        _env_file=None, integration_api_keys={"k": 1}
    ).integration_api_keys == {"k": "1"}
    assert Settings(
        _env_file=None, integration_api_keys='{"k":"t"}'
    ).integration_api_keys == {"k": "t"}
    assert Settings(_env_file=None, integration_api_keys="").integration_api_keys == {}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("integration_api_keys", "key-a:tenant-a"),
        ("integration_api_keys", '["key-a","tenant-a"]'),
        ("integration_api_keys", ["key-a"]),
        ("cors_origins", {"http://a.test": True}),
        ("cors_origins", '{"http://a.test": true}'),
        ("budget_alert_admin_emails", {"a": "a@example.com"}),
        ("budget_alert_admin_emails", '{"a": "a@example.com"}'),
    ],
)
def test_constructor_wrong_shape_raises_validation_error(
    runtime: pytest.MonkeyPatch, field: str, value: object
) -> None:
    with pytest.raises(ValidationError, match=f"(?i){field}"):
        Settings(_env_file=None, **{field: value})
