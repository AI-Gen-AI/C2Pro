import pytest

from src.config import Settings
from tests.unit.core.test_config_settings import _set_required_settings_env


def test_platform_operator_allowlist_is_exact_csv_narrowing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_settings_env(monkeypatch)
    monkeypatch.setenv("PLATFORM_OPERATOR_ORG_ID", "org_platform")
    monkeypatch.setenv(
        "PLATFORM_OPERATOR_USER_IDS", " user_alpha, ,user_Beta , user_alpha ",
    )

    settings = Settings(_env_file=None)

    assert settings.platform_operator_org_id == "org_platform"
    assert settings.platform_operator_user_ids == ["user_alpha", "user_Beta"]


def test_platform_operator_allowlist_rejects_non_clerk_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_settings_env(monkeypatch)
    monkeypatch.setenv("PLATFORM_OPERATOR_USER_IDS", "admin@example.test")

    with pytest.raises(ValueError, match="Clerk user IDs"):
        Settings(_env_file=None)


def test_unset_platform_operator_allowlist_does_not_narrow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_settings_env(monkeypatch)
    monkeypatch.delenv("PLATFORM_OPERATOR_USER_IDS", raising=False)

    settings = Settings(_env_file=None)

    assert settings.platform_operator_user_ids == []
