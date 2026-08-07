"""Suite ID: TS-SEC-SECRET-CHANNEL-001.

Secret channel providers for secure delivery of frontend-safe Clerk config.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol


class SecretBundleProvider(Protocol):
    def load_bundle(self, *, bundle_ref: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class EnvJsonSecretBundleProvider:
    """Loads a JSON bundle from an environment variable payload."""

    def load_bundle(self, *, bundle_ref: str) -> dict[str, Any]:
        payload = bundle_ref.strip()
        if not payload:
            raise ValueError("Secret channel bundle payload is empty")
        parsed = json.loads(payload)
        if not isinstance(parsed, dict):
            raise ValueError("Secret channel bundle must decode to an object")
        return parsed


@dataclass(frozen=True)
class AwsSecretsManagerBundleProvider:
    """Loads a JSON bundle from AWS Secrets Manager secret string."""

    region: str

    def load_bundle(self, *, bundle_ref: str) -> dict[str, Any]:
        import boto3

        client = boto3.client("secretsmanager", region_name=self.region)
        response = client.get_secret_value(SecretId=bundle_ref)
        secret_string = response.get("SecretString")
        if not isinstance(secret_string, str):
            raise ValueError("AWS secret is missing SecretString JSON payload")
        parsed = json.loads(secret_string)
        if not isinstance(parsed, dict):
            raise ValueError("AWS secret payload must decode to an object")
        return parsed


@dataclass(frozen=True)
class VaultKvBundleProvider:
    """Loads a JSON bundle from HashiCorp Vault KV v2 path."""

    url: str
    token: str

    def load_bundle(self, *, bundle_ref: str) -> dict[str, Any]:
        import hvac

        if ":" not in bundle_ref:
            raise ValueError(
                f"secret_channel_bundle_ref must be in 'mount:path' format, got: {bundle_ref!r}"
            )
        client = hvac.Client(url=self.url, token=self.token)
        mount_point, secret_path = bundle_ref.split(":", 1)
        response = client.secrets.kv.v2.read_secret_version(path=secret_path, mount_point=mount_point)
        data = response.get("data", {}).get("data", {})
        if not isinstance(data, dict):
            raise ValueError("Vault KV bundle did not return an object")
        return data


def redact_clerk_bundle(bundle: dict[str, Any]) -> dict[str, str]:
    """Return frontend-safe Clerk fields only."""
    allowed = {
        "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY",
        "CLERK_ISSUER",
        "CLERK_JWKS_URL",
        "NEXT_PUBLIC_CLERK_SIGN_IN_URL",
        "NEXT_PUBLIC_CLERK_SIGN_UP_URL",
        "NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL",
        "NEXT_PUBLIC_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL",
    }
    redacted: dict[str, str] = {}
    for key in allowed:
        value = bundle.get(key)
        if isinstance(value, str) and value:
            redacted[key] = value
    return redacted
