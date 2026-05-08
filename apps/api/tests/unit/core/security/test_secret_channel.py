"""Secret channel provider unit coverage.

Test Suite ID: TASK-OPS-DOCFLOW-013
"""

import sys
from types import SimpleNamespace

import pytest

from src.core.security.secret_channel import (
    AwsSecretsManagerBundleProvider,
    EnvJsonSecretBundleProvider,
    VaultKvBundleProvider,
    redact_clerk_bundle,
)


def test_env_json_provider_loads_object_payload() -> None:
    """TASK-OPS-DOCFLOW-013: env JSON bundles must decode to an object."""
    provider = EnvJsonSecretBundleProvider()

    bundle = provider.load_bundle(bundle_ref='{"CLERK_ISSUER":"https://issuer"}')

    assert bundle == {"CLERK_ISSUER": "https://issuer"}


@pytest.mark.parametrize("payload", ["", "[]"])
def test_env_json_provider_rejects_empty_or_non_object_payload(payload: str) -> None:
    """TASK-OPS-DOCFLOW-013: malformed env bundles fail closed."""
    provider = EnvJsonSecretBundleProvider()

    with pytest.raises(ValueError):
        provider.load_bundle(bundle_ref=payload)


def test_redact_clerk_bundle_returns_only_frontend_safe_non_empty_strings() -> None:
    """TASK-OPS-DOCFLOW-013: secret channel redaction excludes private fields."""
    redacted = redact_clerk_bundle(
        {
            "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY": "pk_test",
            "CLERK_ISSUER": "https://issuer",
            "CLERK_SECRET_KEY": "sk_test",
            "CLERK_JWKS_URL": "",
            "NEXT_PUBLIC_CLERK_SIGN_IN_URL": 123,
        }
    )

    assert redacted == {
        "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY": "pk_test",
        "CLERK_ISSUER": "https://issuer",
    }


def test_aws_provider_loads_secret_string_json(monkeypatch) -> None:
    """TASK-OPS-DOCFLOW-013: AWS provider parses Secrets Manager JSON payloads."""
    calls: list[tuple[str, str]] = []

    class _Client:
        def get_secret_value(self, *, SecretId: str) -> dict[str, str]:
            calls.append(("get_secret_value", SecretId))
            return {"SecretString": '{"CLERK_ISSUER":"https://aws"}'}

    monkeypatch.setitem(
        sys.modules,
        "boto3",
        SimpleNamespace(client=lambda service, region_name: _Client()),
    )

    bundle = AwsSecretsManagerBundleProvider(region="eu-west-1").load_bundle(
        bundle_ref="c2pro/clerk"
    )

    assert bundle == {"CLERK_ISSUER": "https://aws"}
    assert calls == [("get_secret_value", "c2pro/clerk")]


def test_vault_provider_loads_kv_v2_bundle(monkeypatch) -> None:
    """TASK-OPS-DOCFLOW-013: Vault provider extracts the KV v2 data object."""

    class _KvV2:
        def read_secret_version(self, *, path: str, mount_point: str) -> dict[str, object]:
            assert path == "frontend/clerk"
            assert mount_point == "secret"
            return {"data": {"data": {"CLERK_ISSUER": "https://vault"}}}

    class _Client:
        secrets = SimpleNamespace(kv=SimpleNamespace(v2=_KvV2()))

        def __init__(self, *, url: str, token: str) -> None:
            assert url == "https://vault.local"
            assert token == "token"

    monkeypatch.setitem(sys.modules, "hvac", SimpleNamespace(Client=_Client))

    bundle = VaultKvBundleProvider(url="https://vault.local", token="token").load_bundle(
        bundle_ref="secret:frontend/clerk"
    )

    assert bundle == {"CLERK_ISSUER": "https://vault"}
