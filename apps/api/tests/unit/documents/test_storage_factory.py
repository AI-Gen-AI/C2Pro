"""Tests for the canonical document storage provider factory."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from src.core.exceptions import StorageError
from src.documents.adapters.storage import factory
from src.documents.adapters.storage.local_file_storage_service import LocalFileStorageService
from src.documents.adapters.storage.r2_storage_service import R2StorageService


class _SyncMemoryS3:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_object(self, *, Bucket: str, Key: str, Body: bytes, **_: Any) -> dict[str, Any]:
        self.objects[f"{Bucket}/{Key}"] = bytes(Body)
        return {}

    def get_object(self, *, Bucket: str, Key: str, **_: Any) -> dict[str, Any]:
        data = self.objects[f"{Bucket}/{Key}"]
        return {"Body": SimpleNamespace(read=lambda: data)}

    def delete_object(self, *, Bucket: str, Key: str, **_: Any) -> dict[str, Any]:
        self.objects.pop(f"{Bucket}/{Key}", None)
        return {}

    def list_objects_v2(self, *, Bucket: str, Prefix: str, **_: Any) -> dict[str, Any]:
        prefix = f"{Bucket}/{Prefix}"
        keys = [
            {"Key": stored.split("/", 1)[1]}
            for stored in self.objects
            if stored.startswith(prefix)
        ]
        return {"Contents": keys, "IsTruncated": False}

    def delete_objects(self, *, Bucket: str, Delete: dict[str, Any], **_: Any) -> dict[str, Any]:
        for item in Delete["Objects"]:
            self.objects.pop(f"{Bucket}/{item['Key']}", None)
        return {}


def _config(tmp_path: Path, *, provider: str = "local") -> SimpleNamespace:
    return SimpleNamespace(
        storage_provider=provider,
        local_storage_path=str(tmp_path / "local"),
        r2_endpoint_url="https://r2.example.invalid",
        r2_account_id="account",
        r2_access_key_id="access",
        r2_secret_access_key="secret",
        r2_bucket_name="bucket",
        storage_endpoint="https://r2.example.invalid",
    )


def test_local_provider_returns_local_storage(tmp_path: Path) -> None:
    service = factory.build_storage_service(_config(tmp_path, provider="local"))
    assert isinstance(service, LocalFileStorageService)


def test_r2_provider_returns_r2_storage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sync_client = _SyncMemoryS3()
    monkeypatch.setattr(
        "boto3.client",
        lambda *args, **kwargs: sync_client,
    )
    monkeypatch.setattr(
        "src.documents.adapters.storage.r2_storage_service.get_circuit_breaker_settings",
        lambda: type("S", (), {"enable_circuit_breakers": False})(),
    )

    service = factory.build_storage_service(_config(tmp_path, provider="r2"))

    assert isinstance(service, R2StorageService)


@pytest.mark.parametrize(
    "field",
    ["r2_access_key_id", "r2_secret_access_key", "r2_bucket_name", "storage_endpoint"],
)
def test_r2_incomplete_configuration_fails_closed(
    tmp_path: Path, field: str
) -> None:
    config = _config(tmp_path, provider="r2")
    setattr(config, field, "")

    with pytest.raises(StorageError, match="configuration incomplete"):
        factory.build_storage_service(config)


def test_s3_provider_does_not_silently_reuse_r2_contract(tmp_path: Path) -> None:
    with pytest.raises(StorageError, match="S3 storage provider is not configured"):
        factory.build_storage_service(_config(tmp_path, provider="s3"))


@pytest.mark.asyncio
async def test_r2_factory_round_trip_does_not_require_shared_local_storage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sync_client = _SyncMemoryS3()
    monkeypatch.setattr("boto3.client", lambda *args, **kwargs: sync_client)
    monkeypatch.setattr(
        "src.documents.adapters.storage.r2_storage_service.get_circuit_breaker_settings",
        lambda: type("S", (), {"enable_circuit_breakers": False})(),
    )
    service = factory.build_storage_service(_config(tmp_path, provider="r2"))

    key = "tenants/t/projects/p/documents/d/revisions/" + ("a" * 64) + ".pdf"
    await service.upload_bytes(b"production-safe-bytes", key)
    downloaded = await service.download_object(key)

    assert downloaded.read_bytes() == b"production-safe-bytes"
