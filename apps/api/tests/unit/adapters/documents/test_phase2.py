"""
Test Suite: BC3 Parser, Storage, Router Additional Tests
Component: Documents Module
Priority: P2

Additional tests to improve coverage.
"""

import os
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

# ===========================================
# BC3 PARSER TESTS
# ===========================================

class TestBC3ParserAdvanced:
    """Advanced tests for BC3FileParser."""

    @pytest.mark.asyncio
    async def test_parse_success(self):
        """Test successful BC3 parsing."""
        from src.documents.adapters.parsers.bc3_file_parser import BC3FileParser

        parser = BC3FileParser()

        # Create mock content
        bc3_content = """*

A1;Item 1;100.00
A2;Item 2;200.00

*"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.bc3', delete=False) as tmp:
            tmp.write(bc3_content)
            tmp_path = tmp.name

        try:
            result = await parser.parse(Path(tmp_path))
            assert isinstance(result, dict)
        finally:
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    async def test_parse_with_comments(self):
        """Test BC3 parsing with comment lines."""
        from src.documents.adapters.parsers.bc3_file_parser import BC3FileParser

        parser = BC3FileParser()

        bc3_content = """*
# This is a comment
A1;Item 1;100.00

*"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.bc3', delete=False) as tmp:
            tmp.write(bc3_content)
            tmp_path = tmp.name

        try:
            result = await parser.parse(Path(tmp_path))
            assert isinstance(result, dict)
        finally:
            os.unlink(tmp_path)

    def test_parser_init(self):
        """Test BC3 parser initialization."""
        from src.documents.adapters.parsers.bc3_file_parser import BC3FileParser

        parser = BC3FileParser()
        assert parser is not None


# ===========================================
# STORAGE SERVICE TESTS
# ===========================================

class TestStorageServiceAdvanced:
    """Advanced tests for LocalFileStorageService."""

    @pytest.mark.asyncio
    async def test_upload_file(self):
        """Test file upload."""
        from src.documents.adapters.storage.local_file_storage_service import (
            LocalFileStorageService,
        )

        service = LocalFileStorageService(base_dir=Path(tempfile.mkdtemp()))

        from io import BytesIO
        file_content = BytesIO(b"test content")
        file_id = uuid4()
        extension = ".txt"

        result = await service.upload_file(
            file_content=file_content,
            file_id=file_id,
            file_extension=extension
        )

        assert result is not None
        assert str(file_id) in result

        # Cleanup
        Path(result).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_delete_file(self):
        """Test file deletion."""
        from io import BytesIO

        from src.documents.adapters.storage.local_file_storage_service import (
            LocalFileStorageService,
        )

        service = LocalFileStorageService(base_dir=Path(tempfile.mkdtemp()))

        # First upload a file
        file_content = BytesIO(b"test content")
        file_id = uuid4()
        extension = ".txt"

        file_path = await service.upload_file(
            file_content=file_content,
            file_id=file_id,
            file_extension=extension
        )

        # Now delete it
        await service.delete_file(file_path)

        # Verify deleted
        assert not Path(file_path).exists()

    @pytest.mark.asyncio
    async def test_get_file_path(self):
        """Test get file path."""
        from src.documents.adapters.storage.local_file_storage_service import (
            LocalFileStorageService,
        )

        service = LocalFileStorageService(base_dir=Path(tempfile.mkdtemp()))

        file_id = uuid4()
        extension = ".txt"
        filename = f"{file_id}{extension}"

        result = await service.get_file_path(filename)

        assert result is not None

    def test_storage_init_custom_dir(self):
        """Test storage with custom directory."""
        from src.documents.adapters.storage.local_file_storage_service import (
            LocalFileStorageService,
        )

        custom_dir = Path(tempfile.mkdtemp())
        service = LocalFileStorageService(base_dir=custom_dir)

        assert service._base_dir == custom_dir


# ===========================================
# ROUTER TESTS
# ===========================================

class TestDocumentRouterHelpers:
    """Tests for document router helper functions."""

    def test_normalize_document_status_uploaded(self):
        """Test status normalization for UPLOADED."""
        from src.documents.adapters.http.router import _normalize_document_status_for_polling
        from src.documents.domain.models import DocumentStatus

        result = _normalize_document_status_for_polling(DocumentStatus.UPLOADED)
        assert result is not None

    def test_normalize_document_status_parsed(self):
        """Test status normalization for PARSED."""
        from src.documents.adapters.http.router import _normalize_document_status_for_polling
        from src.documents.domain.models import DocumentStatus

        result = _normalize_document_status_for_polling(DocumentStatus.PARSED)
        assert result is not None

    def test_normalize_document_status_error(self):
        """Test status normalization for ERROR."""
        from src.documents.adapters.http.router import _normalize_document_status_for_polling
        from src.documents.domain.models import DocumentStatus

        result = _normalize_document_status_for_polling(DocumentStatus.ERROR)
        assert result is not None

    def test_document_status_detail_uploaded(self):
        """Test status detail for UPLOADED."""
        from src.documents.adapters.http.router import _document_status_detail_for_polling
        from src.documents.domain.models import DocumentStatus

        result = _document_status_detail_for_polling(DocumentStatus.UPLOADED)
        assert result is not None
        assert "upload" in result.lower()

    def test_allowed_extensions(self):
        """Test allowed extensions constant."""
        from src.documents.adapters.http.router import ALLOWED_EXTENSIONS

        assert ".pdf" in ALLOWED_EXTENSIONS
        assert ".xlsx" in ALLOWED_EXTENSIONS
        assert ".bc3" in ALLOWED_EXTENSIONS


class TestDocumentRouterEndpoints:
    """Tests for document router endpoints."""

    def test_router_import(self):
        """Test router can be imported."""
        from src.documents.adapters.http.router import router

        assert router is not None

    def test_router_has_routes(self):
        """Test router has routes defined."""
        from src.documents.adapters.http.router import router

        assert len(router.routes) > 0
