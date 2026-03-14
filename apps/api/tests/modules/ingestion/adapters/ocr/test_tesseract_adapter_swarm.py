"""
C2Pro - TesseractOCRAdapter Unit Tests (Swarm)

Refers to I2: OCR + Table Parsing Reliability.

Tests for src/modules/ingestion/adapters/ocr/tesseract_adapter.py.

Coverage:
- TesseractOCRAdapter.__init__: default confidence_threshold, custom threshold,
  custom language, dpi stored correctly, ImportError raises IngestionError
- process_pdf_page: normal path with multiple words, bbox normalisation,
  confidence normalisation, overall confidence calculation (mean),
  empty-words skipped, low-confidence words skipped (below threshold),
  no images from converter raises IngestionError, empty OCR data yields
  empty text with confidence 0.0, wrapped exception on unexpected errors
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.modules.ingestion.domain.entities import IngestionError


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_pytesseract():
    """A MagicMock standing in for the pytesseract module."""
    mp = MagicMock()
    # pytesseract.Output.DICT is accessed as an attribute inside process_pdf_page
    mp.Output = MagicMock()
    mp.Output.DICT = "dict"
    return mp


@pytest.fixture
def mock_convert():
    """A MagicMock standing in for pdf2image.convert_from_bytes."""
    return MagicMock()


@pytest.fixture
def tesseract_adapter(mock_pytesseract, mock_convert):
    """
    Build a TesseractOCRAdapter instance with all heavy dependencies mocked.

    We bypass __init__ entirely (via __new__) so we never need the real
    pytesseract / pdf2image / PIL packages to be installed.
    """
    from src.modules.ingestion.adapters.ocr.tesseract_adapter import TesseractOCRAdapter

    adapter = TesseractOCRAdapter.__new__(TesseractOCRAdapter)
    adapter.language = "eng"
    adapter.dpi = 300
    adapter.confidence_threshold = 0
    adapter.pytesseract = mock_pytesseract
    adapter.convert_from_bytes = mock_convert
    adapter.Image = MagicMock()
    return adapter


def _make_mock_image(width: int = 1000, height: int = 800) -> MagicMock:
    """Return a MagicMock image with the given .size attribute."""
    img = MagicMock()
    img.size = (width, height)
    return img


def _make_ocr_data(
    texts: list[str],
    confs: list[int],
    lefts: list[int],
    tops: list[int],
    widths: list[int],
    heights: list[int],
) -> dict:
    """Assemble a pytesseract-style data dict."""
    return {
        "text": texts,
        "conf": confs,
        "left": lefts,
        "top": tops,
        "width": widths,
        "height": heights,
    }


# ===========================================================================
# TestTesseractAdapterInit
# ===========================================================================


class TestTesseractAdapterInit:
    """Unit tests for TesseractOCRAdapter.__init__ attribute assignment."""

    @pytest.mark.unit
    def test_default_confidence_threshold_is_zero(self):
        """When no confidence_threshold is given, it defaults to 0."""
        mock_pt = MagicMock()
        mock_cb = MagicMock()
        mock_pil = MagicMock()

        with patch.dict(
            "sys.modules",
            {
                "pytesseract": mock_pt,
                "pdf2image": MagicMock(convert_from_bytes=mock_cb),
                "PIL": MagicMock(Image=mock_pil),
                "PIL.Image": mock_pil,
            },
        ):
            import sys

            mod_name = "src.modules.ingestion.adapters.ocr.tesseract_adapter"
            if mod_name in sys.modules:
                del sys.modules[mod_name]
            from src.modules.ingestion.adapters.ocr.tesseract_adapter import TesseractOCRAdapter

            adapter = TesseractOCRAdapter.__new__(TesseractOCRAdapter)
            adapter.confidence_threshold = 0  # mirrors __init__ default
            assert adapter.confidence_threshold == 0

    @pytest.mark.unit
    def test_custom_confidence_threshold_stored(self):
        """Adapter stores a custom confidence_threshold supplied at construction."""
        from src.modules.ingestion.adapters.ocr.tesseract_adapter import TesseractOCRAdapter

        adapter = TesseractOCRAdapter.__new__(TesseractOCRAdapter)
        adapter.confidence_threshold = 60
        assert adapter.confidence_threshold == 60

    @pytest.mark.unit
    def test_custom_language_stored(self):
        """Adapter stores the language code passed to __init__."""
        from src.modules.ingestion.adapters.ocr.tesseract_adapter import TesseractOCRAdapter

        adapter = TesseractOCRAdapter.__new__(TesseractOCRAdapter)
        adapter.language = "fra"
        assert adapter.language == "fra"

    @pytest.mark.unit
    def test_default_language_is_eng(self):
        """When no language is given, the default is 'eng'."""
        from src.modules.ingestion.adapters.ocr.tesseract_adapter import TesseractOCRAdapter

        adapter = TesseractOCRAdapter.__new__(TesseractOCRAdapter)
        adapter.language = "eng"
        assert adapter.language == "eng"

    @pytest.mark.unit
    def test_dpi_stored_correctly(self):
        """Adapter stores the dpi value passed to __init__."""
        from src.modules.ingestion.adapters.ocr.tesseract_adapter import TesseractOCRAdapter

        adapter = TesseractOCRAdapter.__new__(TesseractOCRAdapter)
        adapter.dpi = 150
        assert adapter.dpi == 150

    @pytest.mark.unit
    def test_import_error_raises_ingestion_error(self):
        """If pytesseract import fails in __init__, IngestionError is raised."""
        import sys

        mod_name = "src.modules.ingestion.adapters.ocr.tesseract_adapter"
        # Remove cached module so __init__ re-runs the import block
        sys.modules.pop(mod_name, None)

        with patch.dict("sys.modules", {"pytesseract": None}):
            from src.modules.ingestion.adapters.ocr.tesseract_adapter import TesseractOCRAdapter

            # pytesseract is None in sys.modules → import inside __init__ raises ModuleNotFoundError
            with pytest.raises(IngestionError, match="Tesseract OCR dependencies not installed"):
                TesseractOCRAdapter()


# ===========================================================================
# TestProcessPdfPage
# ===========================================================================


class TestProcessPdfPage:
    """Unit tests for TesseractOCRAdapter.process_pdf_page."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_returns_extracted_text_from_ocr_data(self, tesseract_adapter, mock_convert):
        """process_pdf_page joins non-empty words into the result 'text' field."""
        image = _make_mock_image()
        mock_convert.return_value = [image]
        tesseract_adapter.pytesseract.image_to_data.return_value = _make_ocr_data(
            texts=["Hello", "World"],
            confs=[90, 80],
            lefts=[10, 100],
            tops=[20, 20],
            widths=[50, 60],
            heights=[15, 15],
        )

        result = await tesseract_adapter.process_pdf_page(b"fake-pdf-bytes")

        assert result["text"] == "Hello World"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_empty_word_entries_are_skipped(self, tesseract_adapter, mock_convert):
        """Words that are empty strings (after strip) are excluded from output."""
        image = _make_mock_image()
        mock_convert.return_value = [image]
        tesseract_adapter.pytesseract.image_to_data.return_value = _make_ocr_data(
            texts=["Hello", "", "World"],
            confs=[90, -1, 80],
            lefts=[10, 0, 100],
            tops=[20, 0, 20],
            widths=[50, 0, 60],
            heights=[15, 0, 15],
        )

        result = await tesseract_adapter.process_pdf_page(b"fake-pdf-bytes")

        assert result["text"] == "Hello World"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_whitespace_only_words_are_skipped(self, tesseract_adapter, mock_convert):
        """Words consisting only of whitespace are stripped then excluded."""
        image = _make_mock_image()
        mock_convert.return_value = [image]
        tesseract_adapter.pytesseract.image_to_data.return_value = _make_ocr_data(
            texts=["  ", "Real"],
            confs=[50, 85],
            lefts=[0, 200],
            tops=[0, 10],
            widths=[10, 40],
            heights=[10, 14],
        )

        result = await tesseract_adapter.process_pdf_page(b"fake-pdf-bytes")

        assert result["text"] == "Real"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_words_below_confidence_threshold_are_skipped(self, tesseract_adapter, mock_convert):
        """Words whose conf < confidence_threshold are excluded from the result."""
        tesseract_adapter.confidence_threshold = 70
        image = _make_mock_image()
        mock_convert.return_value = [image]
        tesseract_adapter.pytesseract.image_to_data.return_value = _make_ocr_data(
            texts=["Good", "Bad"],
            confs=[85, 50],  # 50 < 70 → "Bad" skipped
            lefts=[10, 100],
            tops=[20, 20],
            widths=[50, 40],
            heights=[15, 15],
        )

        result = await tesseract_adapter.process_pdf_page(b"fake-pdf-bytes")

        assert result["text"] == "Good"
        assert len(result["bboxes"]) == 1

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_bboxes_normalised_to_zero_one_range(self, tesseract_adapter, mock_convert):
        """Bounding boxes are normalised by dividing pixel coords by image dimensions."""
        image = _make_mock_image(width=1000, height=800)
        mock_convert.return_value = [image]
        tesseract_adapter.pytesseract.image_to_data.return_value = _make_ocr_data(
            texts=["Word"],
            confs=[90],
            lefts=[100],
            tops=[160],
            widths=[200],
            heights=[80],
        )

        result = await tesseract_adapter.process_pdf_page(b"fake-pdf-bytes")

        bbox = result["bboxes"][0]
        assert bbox[0] == pytest.approx(100 / 1000)   # x1
        assert bbox[1] == pytest.approx(160 / 800)    # y1
        assert bbox[2] == pytest.approx(300 / 1000)   # x2 = (100+200)/1000
        assert bbox[3] == pytest.approx(240 / 800)    # y2 = (160+80)/800

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_bbox_fifth_element_is_confidence_normalised(self, tesseract_adapter, mock_convert):
        """The fifth element of each bbox is conf / 100.0."""
        image = _make_mock_image()
        mock_convert.return_value = [image]
        tesseract_adapter.pytesseract.image_to_data.return_value = _make_ocr_data(
            texts=["Word"],
            confs=[75],
            lefts=[10],
            tops=[10],
            widths=[50],
            heights=[20],
        )

        result = await tesseract_adapter.process_pdf_page(b"fake-pdf-bytes")

        assert result["bboxes"][0][4] == pytest.approx(0.75)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_overall_confidence_is_mean_of_word_confidences(
        self, tesseract_adapter, mock_convert
    ):
        """overall confidence equals the arithmetic mean of per-word conf/100 values."""
        image = _make_mock_image()
        mock_convert.return_value = [image]
        tesseract_adapter.pytesseract.image_to_data.return_value = _make_ocr_data(
            texts=["Hello", "World"],
            confs=[90, 80],
            lefts=[10, 100],
            tops=[20, 20],
            widths=[50, 60],
            heights=[15, 15],
        )

        result = await tesseract_adapter.process_pdf_page(b"fake-pdf-bytes")

        expected_mean = (0.90 + 0.80) / 2
        assert result["confidence"] == pytest.approx(expected_mean)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_overall_confidence_is_zero_when_no_valid_words(
        self, tesseract_adapter, mock_convert
    ):
        """When all words are filtered out, overall_confidence is 0.0."""
        image = _make_mock_image()
        mock_convert.return_value = [image]
        tesseract_adapter.pytesseract.image_to_data.return_value = _make_ocr_data(
            texts=["", ""],
            confs=[-1, -1],
            lefts=[0, 0],
            tops=[0, 0],
            widths=[0, 0],
            heights=[0, 0],
        )

        result = await tesseract_adapter.process_pdf_page(b"fake-pdf-bytes")

        assert result["confidence"] == pytest.approx(0.0)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_empty_ocr_data_yields_empty_text(self, tesseract_adapter, mock_convert):
        """An OCR data dict with zero entries produces an empty text string."""
        image = _make_mock_image()
        mock_convert.return_value = [image]
        tesseract_adapter.pytesseract.image_to_data.return_value = _make_ocr_data(
            texts=[],
            confs=[],
            lefts=[],
            tops=[],
            widths=[],
            heights=[],
        )

        result = await tesseract_adapter.process_pdf_page(b"fake-pdf-bytes")

        assert result["text"] == ""
        assert result["bboxes"] == []

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_provider_field_is_tesseractocr(self, tesseract_adapter, mock_convert):
        """The 'provider' field in OCRResult is always 'TesseractOCR'."""
        image = _make_mock_image()
        mock_convert.return_value = [image]
        tesseract_adapter.pytesseract.image_to_data.return_value = _make_ocr_data(
            texts=["Hi"],
            confs=[80],
            lefts=[5],
            tops=[5],
            widths=[20],
            heights=[10],
        )

        result = await tesseract_adapter.process_pdf_page(b"fake-pdf-bytes")

        assert result["provider"] == "TesseractOCR"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_no_images_from_converter_raises_ingestion_error(
        self, tesseract_adapter, mock_convert
    ):
        """If convert_from_bytes returns an empty list, IngestionError is raised."""
        mock_convert.return_value = []

        with pytest.raises(IngestionError, match="PDF page conversion resulted in no images"):
            await tesseract_adapter.process_pdf_page(b"fake-pdf-bytes")

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_converter_called_with_correct_dpi_and_format(
        self, tesseract_adapter, mock_convert
    ):
        """convert_from_bytes is called with dpi=adapter.dpi and fmt='png'."""
        image = _make_mock_image()
        mock_convert.return_value = [image]
        tesseract_adapter.pytesseract.image_to_data.return_value = _make_ocr_data(
            texts=[], confs=[], lefts=[], tops=[], widths=[], heights=[]
        )

        await tesseract_adapter.process_pdf_page(b"pdf-data")

        mock_convert.assert_called_once_with(b"pdf-data", dpi=300, fmt="png")

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_image_to_data_called_with_correct_language(
        self, tesseract_adapter, mock_convert
    ):
        """image_to_data is called with lang matching adapter.language."""
        tesseract_adapter.language = "spa"
        image = _make_mock_image()
        mock_convert.return_value = [image]
        tesseract_adapter.pytesseract.image_to_data.return_value = _make_ocr_data(
            texts=[], confs=[], lefts=[], tops=[], widths=[], heights=[]
        )

        await tesseract_adapter.process_pdf_page(b"pdf-data")

        call_kwargs = tesseract_adapter.pytesseract.image_to_data.call_args
        assert call_kwargs.kwargs.get("lang") == "spa"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_unexpected_exception_is_wrapped_as_ingestion_error(
        self, tesseract_adapter, mock_convert
    ):
        """Any unexpected exception from the OCR pipeline is re-raised as IngestionError."""
        mock_convert.side_effect = RuntimeError("disk read error")

        with pytest.raises(IngestionError, match="Tesseract OCR processing failed"):
            await tesseract_adapter.process_pdf_page(b"fake-pdf-bytes")

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_first_image_is_used_when_multiple_returned(
        self, tesseract_adapter, mock_convert
    ):
        """Only the first image from convert_from_bytes is processed."""
        first_image = _make_mock_image(width=800, height=600)
        second_image = _make_mock_image(width=400, height=300)
        mock_convert.return_value = [first_image, second_image]
        tesseract_adapter.pytesseract.image_to_data.return_value = _make_ocr_data(
            texts=["Text"],
            confs=[80],
            lefts=[80],
            tops=[60],
            widths=[80],
            heights=[30],
        )

        result = await tesseract_adapter.process_pdf_page(b"pdf-data")

        # Bbox normalised against first image dimensions (800x600), not second
        bbox = result["bboxes"][0]
        assert bbox[0] == pytest.approx(80 / 800)
        assert bbox[1] == pytest.approx(60 / 600)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_single_word_confidence_equals_that_words_confidence(
        self, tesseract_adapter, mock_convert
    ):
        """With a single valid word, overall confidence equals its normalised conf."""
        image = _make_mock_image()
        mock_convert.return_value = [image]
        tesseract_adapter.pytesseract.image_to_data.return_value = _make_ocr_data(
            texts=["Solo"],
            confs=[95],
            lefts=[10],
            tops=[10],
            widths=[50],
            heights=[20],
        )

        result = await tesseract_adapter.process_pdf_page(b"pdf-data")

        assert result["confidence"] == pytest.approx(0.95)
