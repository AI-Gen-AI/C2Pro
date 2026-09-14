"""P0b storage adapters honour exact immutable keys and document-scoped deletes.

Refers to Suite ID: TS-UT-P0B-STORAGE-002.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.core.exceptions import StorageError
from src.documents.adapters.storage.local_file_storage_service import LocalFileStorageService
from src.documents.adapters.storage.r2_storage_service import R2StorageService
from src.documents.domain.storage_keys import document_object_prefix


def _key(prefix: str, name: str = "a" * 64) -> str:
    return f"{prefix}revisions/{name}.pdf"


# --- local filesystem ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_local_storage_round_trips_a_nested_revision_key(tmp_path: Path) -> None:
    storage = LocalFileStorageService(base_dir=tmp_path)
    key = _key(document_object_prefix(uuid4(), uuid4(), uuid4()))

    await storage.upload_bytes(b"revision bytes", key)

    assert await storage.file_exists(key)
    downloaded = await storage.download_object(key)
    assert downloaded == tmp_path / key
    assert downloaded.read_bytes() == b"revision bytes"


@pytest.mark.asyncio
@pytest.mark.parametrize("key", ["../escape.pdf", "/etc/passwd", "tenants/../../escape.pdf", ""])
async def test_local_storage_rejects_keys_that_escape_the_store(tmp_path: Path, key: str) -> None:
    storage = LocalFileStorageService(base_dir=tmp_path / "store")

    with pytest.raises(StorageError):
        await storage.upload_bytes(b"x", key)
    with pytest.raises(StorageError):
        await storage.download_object(key)
    with pytest.raises(StorageError):
        await storage.delete_prefix(key)


@pytest.mark.asyncio
async def test_local_delete_prefix_removes_only_that_document(tmp_path: Path) -> None:
    storage = LocalFileStorageService(base_dir=tmp_path)
    tenant_id, project_id = uuid4(), uuid4()
    doomed = document_object_prefix(tenant_id, project_id, uuid4())
    sibling = document_object_prefix(tenant_id, project_id, uuid4())
    other_tenant = document_object_prefix(uuid4(), project_id, uuid4())
    for prefix in (doomed, sibling, other_tenant):
        await storage.upload_bytes(b"same bytes", _key(prefix))
        await storage.upload_bytes(b"other", _key(prefix, "b" * 64))

    await storage.delete_prefix(doomed)

    assert not await storage.file_exists(_key(doomed))
    assert not await storage.file_exists(_key(doomed, "b" * 64))
    assert await storage.file_exists(_key(sibling))
    assert await storage.file_exists(_key(other_tenant))


@pytest.mark.asyncio
async def test_local_delete_prefix_requires_a_document_prefix(tmp_path: Path) -> None:
    storage = LocalFileStorageService(base_dir=tmp_path)
    await storage.upload_bytes(b"x", _key(document_object_prefix(uuid4(), uuid4(), uuid4())))

    for prefix in ("tenants/", "tenants", "revisions/"):
        with pytest.raises(StorageError):
            await storage.delete_prefix(prefix)


# --- R2 ------------------------------------------------------------------------------------


class _Body:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self) -> bytes:
        return self._data


@pytest.fixture
def r2_client() -> AsyncMock:
    client = AsyncMock()
    client.put_object = AsyncMock(return_value={})
    client.get_object = AsyncMock(return_value={"Body": _Body(b"revision bytes")})
    client.delete_object = AsyncMock(return_value={})
    client.list_objects_v2 = AsyncMock()
    client.delete_objects = AsyncMock(return_value={})
    return client


@pytest.fixture
def r2(r2_client: AsyncMock, monkeypatch: pytest.MonkeyPatch) -> R2StorageService:
    from src.config import settings

    monkeypatch.setattr(settings, "r2_bucket_name", "c2pro-bucket")
    monkeypatch.setattr(settings, "r2_endpoint_url", "https://r2.test")
    monkeypatch.setattr("src.documents.adapters.storage.r2_storage_service.get_circuit_breaker_settings",
                        lambda: type("S", (), {"enable_circuit_breakers": False})())
    return R2StorageService(client=r2_client)


@pytest.mark.asyncio
async def test_r2_download_object_keeps_the_full_revision_key(r2: R2StorageService, r2_client: AsyncMock) -> None:
    key = _key(document_object_prefix(uuid4(), uuid4(), uuid4()))

    path = await r2.download_object(key)

    assert r2_client.get_object.call_args.kwargs == {"Bucket": "c2pro-bucket", "Key": key}
    assert path.read_bytes() == b"revision bytes"


@pytest.mark.asyncio
async def test_r2_delete_prefix_pages_through_and_deletes_only_that_document(r2: R2StorageService, r2_client: AsyncMock) -> None:
    prefix = document_object_prefix(uuid4(), uuid4(), uuid4())
    r2_client.list_objects_v2.side_effect = [
        {"Contents": [{"Key": _key(prefix)}], "IsTruncated": True, "NextContinuationToken": "t1"},
        {"Contents": [{"Key": _key(prefix, "b" * 64)}], "IsTruncated": False},
    ]

    await r2.delete_prefix(prefix)

    listed = [call.kwargs for call in r2_client.list_objects_v2.call_args_list]
    assert listed == [
        {"Bucket": "c2pro-bucket", "Prefix": prefix},
        {"Bucket": "c2pro-bucket", "Prefix": prefix, "ContinuationToken": "t1"},
    ]
    deleted = [
        obj["Key"]
        for call in r2_client.delete_objects.call_args_list
        for obj in call.kwargs["Delete"]["Objects"]
    ]
    assert deleted == [_key(prefix), _key(prefix, "b" * 64)]


@pytest.mark.asyncio
@pytest.mark.parametrize("prefix", ["", "tenants/", "revisions/", "tenants/x/projects/y/documents/z"])
async def test_r2_delete_prefix_refuses_anything_wider_than_one_document(r2: R2StorageService, r2_client: AsyncMock, prefix: str) -> None:
    with pytest.raises(StorageError):
        await r2.delete_prefix(prefix)
    r2_client.list_objects_v2.assert_not_called()
    r2_client.delete_objects.assert_not_called()
