"""
C2Pro - GoogleVisionOCRAdapter Unit Tests (Swarm)

Refers to I2: OCR + Table Parsing Reliability.

Tests for src/modules/ingestion/adapters/ocr/google_vision_adapter.py.

Coverage:
- MockGoogleVisionOCRAdapter.process_pdf_page:
    deterministic output based on MD5 hash, confidence always 0.92,
    bboxes always has 4 items, provider always "GoogleVisionOCR",
    same input always produces same output, different inputs differ in hash text.

- GoogleVisionOCRAdapter.process_pdf_page (via __new__ bypass):
    API error message raises IngestionError,
    word confidence below min_confidence excludes word from bboxes,
    word confidence at/above min_confidence includes word,
    nested iteration (pages → blocks → paragraphs → words) produces correct bboxes,
    empty full_text_annotation yields empty text, empty bboxes, confidence 0.0,
    bboxes are normalised by page dimensions,
    overall confidence is mean of included word confidences.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Patch google cloud imports before any module-level import of the adapter.
# This prevents ImportError when google-cloud-vision is not installed.
# ---------------------------------------------------------------------------
sys.modules.setdefault("google", MagicMock())
sys.modules.setdefault("google.cloud", MagicMock())
sys.modules.setdefault("google.cloud.vision", MagicMock())
sys.modules.setdefault("google.auth", MagicMock())

from src.modules.ingestion.adapters.ocr.google_vision_adapter import (  # noqa: E402
    GoogleVisionOCRAdapter,
    MockGoogleVisionOCRAdapter,
)
from src.modules.ingestion.domain.entities import IngestionError  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_adapter(min_confidence: float = 0.0) -> GoogleVisionOCRAdapter:
    """
    Build a GoogleVisionOCRAdapter without calling __init__.

    Bypasses the google.cloud.vision dependency entirely by using __new__
    and manually injecting the attributes that process_pdf_page relies on.
    """
    adapter = GoogleVisionOCRAdapter.__new__(GoogleVisionOCRAdapter)
    adapter.credentials_path = None
    adapter.min_confidence = min_confidence
    adapter.vision = MagicMock()
    adapter.client = MagicMock()
    return adapter


def _make_mock_word(confidence: float, x1: int, y1: int, x2: int, y2: int) -> MagicMock:
    """Return a MagicMock word with the given confidence and bounding box vertices."""
    word = MagicMock()
    word.confidence = confidence
    word.bounding_box.vertices = [
        MagicMock(x=x1, y=y1),
        MagicMock(x=x2, y=y1),
        MagicMock(x=x2, y=y2),
        MagicMock(x=x1, y=y2),
    ]
    return word


def _make_response(
    error_message: str = "",
    full_text: str = "Sample text",
    page_width: int = 1000,
    page_height: int = 800,
    words: list | None = None,
) -> MagicMock:
    """
    Construct a mock Google Vision API response.

    Mirrors the structure that process_pdf_page iterates:
        response.full_text_annotation.pages[0].blocks[0].paragraphs[0].words
    """
    response = MagicMock()
    response.error.message = error_message

    if words is None:
        words = []

    mock_paragraph = MagicMock()
    mock_paragraph.words = words

    mock_block = MagicMock()
    mock_block.paragraphs = [mock_paragraph]

    mock_page = MagicMock()
    mock_page.width = page_width
    mock_page.height = page_height
    mock_page.blocks = [mock_block]

    response.full_text_annotation.text = full_text
    response.full_text_annotation.pages = [mock_page]

    return response


def _make_empty_annotation_response() -> MagicMock:
    """Return a response whose full_text_annotation is falsy (None-like)."""
    response = MagicMock()
    response.error.message = ""
    # Make full_text_annotation evaluate to False in a boolean context
    response.full_text_annotation = None
    return response


# ===========================================================================
# TestMockGoogleVisionOCRAdapter
# ===========================================================================


class TestMockGoogleVisionOCRAdapter:
    """Unit tests for MockGoogleVisionOCRAdapter (no external dependencies)."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_confidence_is_always_0_92(self):
        """process_pdf_page always returns confidence == 0.92."""
        adapter = MockGoogleVisionOCRAdapter()
        result = await adapter.process_pdf_page(b"some pdf content")
        assert result["confidence"] == pytest.approx(0.92)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_provider_is_always_google_vision_ocr(self):
        """process_pdf_page always returns provider == 'GoogleVisionOCR'."""
        adapter = MockGoogleVisionOCRAdapter()
        result = await adapter.process_pdf_page(b"some pdf content")
        assert result["provider"] == "GoogleVisionOCR"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_bboxes_always_has_4_items(self):
        """process_pdf_page always returns exactly 4 bounding boxes."""
        adapter = MockGoogleVisionOCRAdapter()
        result = await adapter.process_pdf_page(b"any content here")
        assert len(result["bboxes"]) == 4

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_same_input_produces_same_text(self):
        """Same page_content always yields identical text (deterministic MD5 hash)."""
        adapter = MockGoogleVisionOCRAdapter()
        content = b"deterministic input bytes"
        result_a = await adapter.process_pdf_page(content)
        result_b = await adapter.process_pdf_page(content)
        assert result_a["text"] == result_b["text"]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_different_inputs_produce_different_text(self):
        """Different page_content values produce different hash substrings in text."""
        adapter = MockGoogleVisionOCRAdapter()
        result_a = await adapter.process_pdf_page(b"first document page")
        result_b = await adapter.process_pdf_page(b"second document page")
        assert result_a["text"] != result_b["text"]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_text_contains_md5_hash_substring(self):
        """Result text contains an 8-char hex hash derived from the content MD5."""
        import hashlib

        adapter = MockGoogleVisionOCRAdapter()
        content = b"test content for hash check"
        result = await adapter.process_pdf_page(content)

        expected_hash = hashlib.md5(content).hexdigest()[:8]
        assert expected_hash in result["text"]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_result_has_all_required_keys(self):
        """OCRResult contains all required keys: text, bboxes, confidence, provider."""
        adapter = MockGoogleVisionOCRAdapter()
        result = await adapter.process_pdf_page(b"content")
        assert set(result.keys()) >= {"text", "bboxes", "confidence", "provider"}

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_empty_bytes_still_returns_valid_result(self):
        """Empty bytes input still produces a valid OCRResult (no exception)."""
        adapter = MockGoogleVisionOCRAdapter()
        result = await adapter.process_pdf_page(b"")
        assert result["confidence"] == pytest.approx(0.92)
        assert len(result["bboxes"]) == 4

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_same_input_different_adapter_instances_same_output(self):
        """Two separate MockGoogleVisionOCRAdapter instances produce identical output."""
        content = b"shared input content"
        adapter_a = MockGoogleVisionOCRAdapter()
        adapter_b = MockGoogleVisionOCRAdapter()
        result_a = await adapter_a.process_pdf_page(content)
        result_b = await adapter_b.process_pdf_page(content)
        assert result_a["text"] == result_b["text"]
        assert result_a["confidence"] == result_b["confidence"]


# ===========================================================================
# TestGoogleVisionOCRAdapterProcessPdfPage
# ===========================================================================


class TestGoogleVisionOCRAdapterProcessPdfPage:
    """Unit tests for GoogleVisionOCRAdapter.process_pdf_page (mocked Vision client)."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_api_error_message_raises_ingestion_error(self):
        """Non-empty response.error.message causes IngestionError to be raised."""
        adapter = _make_adapter()
        adapter.client.document_text_detection.return_value = MagicMock(
            **{"error.message": "API quota exceeded"}
        )
        adapter.vision.Image.return_value = MagicMock()

        with pytest.raises(IngestionError):
            await adapter.process_pdf_page(b"page content")

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_api_error_message_contains_original_error_text(self):
        """IngestionError message includes the Google Vision error text."""
        adapter = _make_adapter()
        error_msg = "Invalid credential"
        response = MagicMock()
        response.error.message = error_msg
        adapter.client.document_text_detection.return_value = response
        adapter.vision.Image.return_value = MagicMock()

        with pytest.raises(IngestionError, match=error_msg):
            await adapter.process_pdf_page(b"page content")

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_empty_full_text_annotation_returns_empty_text(self):
        """None full_text_annotation yields text == '' in result."""
        adapter = _make_adapter()
        adapter.client.document_text_detection.return_value = _make_empty_annotation_response()
        adapter.vision.Image.return_value = MagicMock()

        result = await adapter.process_pdf_page(b"page bytes")

        assert result["text"] == ""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_empty_full_text_annotation_returns_empty_bboxes(self):
        """None full_text_annotation yields bboxes == [] in result."""
        adapter = _make_adapter()
        adapter.client.document_text_detection.return_value = _make_empty_annotation_response()
        adapter.vision.Image.return_value = MagicMock()

        result = await adapter.process_pdf_page(b"page bytes")

        assert result["bboxes"] == []

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_empty_full_text_annotation_returns_confidence_zero(self):
        """None full_text_annotation yields confidence == 0.0 in result."""
        adapter = _make_adapter()
        adapter.client.document_text_detection.return_value = _make_empty_annotation_response()
        adapter.vision.Image.return_value = MagicMock()

        result = await adapter.process_pdf_page(b"page bytes")

        assert result["confidence"] == pytest.approx(0.0)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_provider_field_is_google_vision_ocr(self):
        """Result 'provider' field is always 'GoogleVisionOCR'."""
        adapter = _make_adapter()
        word = _make_mock_word(confidence=0.95, x1=100, y1=50, x2=200, y2=80)
        response = _make_response(words=[word])
        adapter.client.document_text_detection.return_value = response
        adapter.vision.Image.return_value = MagicMock()

        result = await adapter.process_pdf_page(b"page content")

        assert result["provider"] == "GoogleVisionOCR"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_word_above_min_confidence_is_included_in_bboxes(self):
        """Word with confidence >= min_confidence appears in result bboxes."""
        adapter = _make_adapter(min_confidence=0.5)
        word = _make_mock_word(confidence=0.8, x1=100, y1=50, x2=200, y2=80)
        response = _make_response(words=[word])
        adapter.client.document_text_detection.return_value = response
        adapter.vision.Image.return_value = MagicMock()

        result = await adapter.process_pdf_page(b"page content")

        assert len(result["bboxes"]) == 1

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_word_at_exact_min_confidence_is_included_in_bboxes(self):
        """Word with confidence == min_confidence (boundary) is included in bboxes."""
        adapter = _make_adapter(min_confidence=0.5)
        word = _make_mock_word(confidence=0.5, x1=100, y1=50, x2=200, y2=80)
        response = _make_response(words=[word])
        adapter.client.document_text_detection.return_value = response
        adapter.vision.Image.return_value = MagicMock()

        result = await adapter.process_pdf_page(b"page content")

        assert len(result["bboxes"]) == 1

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_word_below_min_confidence_is_excluded_from_bboxes(self):
        """Word with confidence < min_confidence is not included in result bboxes."""
        adapter = _make_adapter(min_confidence=0.5)
        word = _make_mock_word(confidence=0.3, x1=100, y1=50, x2=200, y2=80)
        response = _make_response(words=[word])
        adapter.client.document_text_detection.return_value = response
        adapter.vision.Image.return_value = MagicMock()

        result = await adapter.process_pdf_page(b"page content")

        assert len(result["bboxes"]) == 0

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_mixed_confidence_words_filters_correctly(self):
        """Words above threshold are included; words below are excluded."""
        adapter = _make_adapter(min_confidence=0.7)
        word_high = _make_mock_word(confidence=0.9, x1=10, y1=10, x2=50, y2=30)
        word_low = _make_mock_word(confidence=0.5, x1=60, y1=10, x2=100, y2=30)
        response = _make_response(words=[word_high, word_low])
        adapter.client.document_text_detection.return_value = response
        adapter.vision.Image.return_value = MagicMock()

        result = await adapter.process_pdf_page(b"page content")

        assert len(result["bboxes"]) == 1

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_bboxes_normalised_by_page_dimensions(self):
        """Bounding box coordinates are divided by page width and height."""
        adapter = _make_adapter()
        # page is 1000x800; word occupies x=[100,200], y=[50,80]
        word = _make_mock_word(confidence=0.95, x1=100, y1=50, x2=200, y2=80)
        response = _make_response(words=[word], page_width=1000, page_height=800)
        adapter.client.document_text_detection.return_value = response
        adapter.vision.Image.return_value = MagicMock()

        result = await adapter.process_pdf_page(b"page content")

        bbox = result["bboxes"][0]
        assert bbox[0] == pytest.approx(100 / 1000)  # x1 normalised
        assert bbox[1] == pytest.approx(50 / 800)    # y1 normalised
        assert bbox[2] == pytest.approx(200 / 1000)  # x2 normalised
        assert bbox[3] == pytest.approx(80 / 800)    # y2 normalised

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_bbox_fifth_element_is_word_confidence(self):
        """The fifth element of each bbox is the word's raw confidence value."""
        adapter = _make_adapter()
        word = _make_mock_word(confidence=0.87, x1=10, y1=10, x2=50, y2=30)
        response = _make_response(words=[word])
        adapter.client.document_text_detection.return_value = response
        adapter.vision.Image.return_value = MagicMock()

        result = await adapter.process_pdf_page(b"page content")

        assert result["bboxes"][0][4] == pytest.approx(0.87)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_overall_confidence_is_mean_of_included_word_confidences(self):
        """Overall confidence is the arithmetic mean of included word confidences."""
        adapter = _make_adapter()
        word_a = _make_mock_word(confidence=0.8, x1=10, y1=10, x2=50, y2=30)
        word_b = _make_mock_word(confidence=0.6, x1=60, y1=10, x2=100, y2=30)
        response = _make_response(words=[word_a, word_b])
        adapter.client.document_text_detection.return_value = response
        adapter.vision.Image.return_value = MagicMock()

        result = await adapter.process_pdf_page(b"page content")

        expected = (0.8 + 0.6) / 2
        assert result["confidence"] == pytest.approx(expected)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_confidence_is_zero_when_all_words_excluded_by_threshold(self):
        """When all words are filtered out by min_confidence, confidence is 0.0."""
        adapter = _make_adapter(min_confidence=0.99)
        word = _make_mock_word(confidence=0.5, x1=10, y1=10, x2=50, y2=30)
        response = _make_response(words=[word])
        adapter.client.document_text_detection.return_value = response
        adapter.vision.Image.return_value = MagicMock()

        result = await adapter.process_pdf_page(b"page content")

        assert result["confidence"] == pytest.approx(0.0)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_extracted_text_comes_from_full_text_annotation(self):
        """The 'text' field in result mirrors response.full_text_annotation.text."""
        adapter = _make_adapter()
        word = _make_mock_word(confidence=0.9, x1=10, y1=10, x2=50, y2=30)
        expected_text = "Contract clause number one"
        response = _make_response(full_text=expected_text, words=[word])
        adapter.client.document_text_detection.return_value = response
        adapter.vision.Image.return_value = MagicMock()

        result = await adapter.process_pdf_page(b"page content")

        assert result["text"] == expected_text

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_multiple_words_in_nested_structure_all_included(self):
        """All words nested in pages→blocks→paragraphs→words are extracted."""
        adapter = _make_adapter()
        words = [
            _make_mock_word(confidence=0.9, x1=10, y1=10, x2=50, y2=30),
            _make_mock_word(confidence=0.85, x1=60, y1=10, x2=100, y2=30),
            _make_mock_word(confidence=0.8, x1=110, y1=10, x2=150, y2=30),
        ]
        response = _make_response(words=words)
        adapter.client.document_text_detection.return_value = response
        adapter.vision.Image.return_value = MagicMock()

        result = await adapter.process_pdf_page(b"page content")

        assert len(result["bboxes"]) == 3

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_vision_image_called_with_page_content(self):
        """adapter.vision.Image is called with content=page_content."""
        adapter = _make_adapter()
        word = _make_mock_word(confidence=0.9, x1=10, y1=10, x2=50, y2=30)
        response = _make_response(words=[word])
        adapter.client.document_text_detection.return_value = response
        mock_image_instance = MagicMock()
        adapter.vision.Image.return_value = mock_image_instance

        page_bytes = b"my pdf page content"
        await adapter.process_pdf_page(page_bytes)

        adapter.vision.Image.assert_called_once_with(content=page_bytes)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_client_document_text_detection_called_with_image(self):
        """adapter.client.document_text_detection is called with the created image."""
        adapter = _make_adapter()
        word = _make_mock_word(confidence=0.9, x1=10, y1=10, x2=50, y2=30)
        response = _make_response(words=[word])
        adapter.client.document_text_detection.return_value = response
        mock_image_instance = MagicMock()
        adapter.vision.Image.return_value = mock_image_instance

        await adapter.process_pdf_page(b"page bytes")

        adapter.client.document_text_detection.assert_called_once_with(image=mock_image_instance)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_single_word_confidence_equals_that_words_confidence(self):
        """With exactly one valid word, overall confidence equals that word's confidence."""
        adapter = _make_adapter()
        word = _make_mock_word(confidence=0.77, x1=10, y1=10, x2=50, y2=30)
        response = _make_response(words=[word])
        adapter.client.document_text_detection.return_value = response
        adapter.vision.Image.return_value = MagicMock()

        result = await adapter.process_pdf_page(b"page content")

        assert result["confidence"] == pytest.approx(0.77)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_no_words_with_no_pages_returns_empty_bboxes(self):
        """Response with empty pages list produces empty bboxes."""
        adapter = _make_adapter()
        response = MagicMock()
        response.error.message = ""
        response.full_text_annotation.text = ""
        response.full_text_annotation.pages = []
        adapter.client.document_text_detection.return_value = response
        adapter.vision.Image.return_value = MagicMock()

        result = await adapter.process_pdf_page(b"page content")

        assert result["bboxes"] == []
        assert result["confidence"] == pytest.approx(0.0)
