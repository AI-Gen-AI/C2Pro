"""
Refers to Suite ID: TS-UAD-PER-R2-001.
"""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.core.exceptions import StorageError
from src.documents.adapters.storage.r2_storage_service import R2StorageService


class _Body:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    async def read(self) -> bytes:
        return self._payload


@pytest.fixture
def client() -> AsyncMock:
    client = AsyncMock()
    client.put_object = AsyncMock()
    client.delete_object = AsyncMock()
    return client


@pytest.fixture
def service(client, monkeypatch) -> R2StorageService:
    monkeypatch.setattr("src.documents.adapters.storage.r2_storage_service.settings.r2_bucket_name", "c2pro-bucket")
    monkeypatch.setattr("src.documents.adapters.storage.r2_storage_service.settings.r2_endpoint_url", "https://r2.test")
    return R2StorageService(client=client)


@pytest.mark.asyncio
async def test_upload_file_builds_key_and_returns_url(service: R2StorageService, client: AsyncMock) -> None:
    file_id = uuid4()
    url = await service.upload_file(io.BytesIO(b"data"), file_id, ".pdf")

    client.put_object.assert_awaited_once()
    args = client.put_object.call_args.kwargs
    assert args["Bucket"] == "c2pro-bucket"
    assert args["Key"] == f"{file_id}.pdf"
    assert url == f"https://r2.test/c2pro-bucket/{file_id}.pdf"


@pytest.mark.asyncio
async def test_upload_file_raises_storage_error_on_failure(service: R2StorageService, client: AsyncMock) -> None:
    client.put_object.side_effect = Exception("boom")
    with pytest.raises(StorageError):
        await service.upload_file(io.BytesIO(b"data"), uuid4(), ".pdf")


@pytest.mark.asyncio
async def test_download_file_writes_temp_path(service: R2StorageService, client: AsyncMock, tmp_path) -> None:
    payload = b"content"
    client.get_object = AsyncMock(return_value={"Body": _Body(payload)})

    path = await service.download_file("https://r2.test/c2pro-bucket/file-1.pdf")

    assert isinstance(path, Path)
    assert path.exists()
    assert path.read_bytes() == payload


@pytest.mark.asyncio
async def test_download_file_raises_storage_error_on_failure(service: R2StorageService, client: AsyncMock) -> None:
    client.get_object = AsyncMock(side_effect=Exception("boom"))
    with pytest.raises(StorageError):
        await service.download_file("file-1.pdf")


@pytest.mark.asyncio
async def test_download_file_calls_client_with_bucket_and_key(service: R2StorageService, client: AsyncMock) -> None:
    client.get_object = AsyncMock(return_value={"Body": _Body(b"data")})
    await service.download_file("file-2.pdf")

    client.get_object.assert_awaited_once()
    args = client.get_object.call_args.kwargs
    assert args["Bucket"] == "c2pro-bucket"
    assert args["Key"] == "file-2.pdf"


@pytest.mark.asyncio
async def test_delete_file_calls_client(service: R2StorageService, client: AsyncMock) -> None:
    await service.delete_file("file-3.pdf")

    client.delete_object.assert_awaited_once()
    args = client.delete_object.call_args.kwargs
    assert args["Bucket"] == "c2pro-bucket"
    assert args["Key"] == "file-3.pdf"


@pytest.mark.asyncio
async def test_delete_file_raises_storage_error_on_failure(service: R2StorageService, client: AsyncMock) -> None:
    client.delete_object.side_effect = Exception("boom")
    with pytest.raises(StorageError):
        await service.delete_file("file-4.pdf")


@pytest.mark.asyncio
async def test_download_strips_path_prefix(service: R2StorageService, client: AsyncMock) -> None:
    client.get_object = AsyncMock(return_value={"Body": _Body(b"data")})
    await service.download_file("folder/sub/file-5.pdf")

    args = client.get_object.call_args.kwargs
    assert args["Key"] == "file-5.pdf"
