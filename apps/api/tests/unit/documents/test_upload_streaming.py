"""EPIC-OPS-DOCFLOW Stream A: bounded-memory upload streaming.

Refers to Suite ID: TASK-OPS-DOCFLOW-A.

`_stream_upload_to_tempfile` replaces `await file.read()` (which
materializes the entire upload as one contiguous bytes object) with a
chunked read/write loop that never holds more than one chunk in memory
and enforces a hard size cap while streaming, not after the fact.
"""

from __future__ import annotations

import io

import pytest
from fastapi import HTTPException, UploadFile

from src.documents.adapters.http.router import (
    _UPLOAD_STREAM_CHUNK_BYTES,
    _stream_upload_to_tempfile,
)


def _upload_file(content: bytes, filename: str = "test.pdf") -> UploadFile:
    return UploadFile(file=io.BytesIO(content), filename=filename)


class TestStreamUploadToTempfile:
    @pytest.mark.asyncio
    async def test_streams_content_under_cap_to_disk_intact(self) -> None:
        content = b"contract body " * 1000  # well under any reasonable cap
        file = _upload_file(content)

        tmp_path = await _stream_upload_to_tempfile(file, max_bytes=len(content) + 1)
        try:
            assert tmp_path.exists()
            assert tmp_path.read_bytes() == content
        finally:
            tmp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_aborts_mid_stream_when_cap_exceeded(self) -> None:
        """The cap is enforced on actual bytes received, not a declared
        Content-Length — a lying/absent size must still be caught."""
        content = b"x" * 100
        file = _upload_file(content)

        with pytest.raises(HTTPException) as exc_info:
            await _stream_upload_to_tempfile(file, max_bytes=50)

        assert exc_info.value.status_code == 413

    @pytest.mark.asyncio
    async def test_cleans_up_tempfile_on_cap_exceeded(self, tmp_path, monkeypatch) -> None:
        """A rejected upload must not leak a temp file on disk."""
        import tempfile as tempfile_module

        created_paths: list[str] = []
        real_mkstemp = tempfile_module.mkstemp

        def _tracking_mkstemp(*args, **kwargs):
            fd, name = real_mkstemp(*args, **kwargs)
            created_paths.append(name)
            return fd, name

        monkeypatch.setattr(
            "src.documents.adapters.http.router.tempfile.mkstemp", _tracking_mkstemp
        )

        file = _upload_file(b"x" * 100)
        with pytest.raises(HTTPException):
            await _stream_upload_to_tempfile(file, max_bytes=10)

        assert len(created_paths) == 1
        assert not __import__("pathlib").Path(created_paths[0]).exists()

    @pytest.mark.asyncio
    async def test_reads_in_bounded_chunks_not_one_giant_read(self) -> None:
        """Verify the loop actually issues multiple bounded .read() calls
        instead of a single unbounded .read() — the whole point of the fix."""
        chunk_size = 4
        content = b"0123456789ABCDEF"  # 16 bytes -> 4 chunks at chunk_size=4
        file = _upload_file(content)

        read_sizes: list[int] = []
        original_read = file.read

        async def _tracking_read(size: int = -1):
            read_sizes.append(size)
            return await original_read(size)

        file.read = _tracking_read  # type: ignore[method-assign]

        import src.documents.adapters.http.router as router_module

        original_chunk = router_module._UPLOAD_STREAM_CHUNK_BYTES
        router_module._UPLOAD_STREAM_CHUNK_BYTES = chunk_size
        try:
            tmp_path = await _stream_upload_to_tempfile(file, max_bytes=len(content))
            try:
                assert tmp_path.read_bytes() == content
            finally:
                tmp_path.unlink(missing_ok=True)
        finally:
            router_module._UPLOAD_STREAM_CHUNK_BYTES = original_chunk

        # 4 chunks of 4 bytes + 1 final empty read to detect EOF.
        assert len(read_sizes) == 5
        assert all(size == chunk_size for size in read_sizes)

    @pytest.mark.asyncio
    async def test_empty_upload_produces_empty_tempfile(self) -> None:
        file = _upload_file(b"")

        tmp_path = await _stream_upload_to_tempfile(file, max_bytes=1024)
        try:
            assert tmp_path.read_bytes() == b""
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_chunk_size_is_reasonably_bounded(self) -> None:
        """Sanity check on the constant itself — must be a real bound, not
        accidentally set to something huge that defeats the purpose."""
        assert 0 < _UPLOAD_STREAM_CHUNK_BYTES <= 16 * 1024 * 1024
