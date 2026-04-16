"""Document loader for Decision Intelligence LangGraph entry point.

Converts raw base64-decoded document bytes into the plain text payload
required by the N1 ``document_ingestion_node`` in
``src/analysis/adapters/graph``. Reuses the production ``PDFFileParser``
so that OCR and offset extraction behave identically to the main
document ingestion pipeline.

Refers to Suite ID: TS-I13-E2E-REAL-001.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import structlog

from src.documents.adapters.parsers.pdf_file_parser import PDFFileParser

logger = structlog.get_logger()


_PDF_MAGIC = b"%PDF-"


async def load_document_text(doc_bytes: bytes) -> str:
    """Return plain text extracted from ``doc_bytes``.

    - PDF payloads (magic ``%PDF-``) are materialised to a temp file and
      parsed through the production :class:`PDFFileParser`, preserving
      OCR fallback and per-page offsets.
    - Any other payload is decoded as UTF-8 with ``errors="replace"``.

    Empty input returns an empty string so that downstream nodes can
    short-circuit on ``state["document_text"]``.
    """
    if not doc_bytes:
        return ""

    if doc_bytes[:5] == _PDF_MAGIC:
        return await _extract_pdf_text(doc_bytes)

    try:
        return doc_bytes.decode("utf-8", errors="replace")
    except Exception as exc:  # pragma: no cover - decode with replace never raises
        logger.warning("di_plaintext_decode_failed", error=str(exc))
        return ""


async def _extract_pdf_text(doc_bytes: bytes) -> str:
    """Parse a PDF payload via the production parser and flatten to text."""
    parser = PDFFileParser()
    tmp_path: Path | None = None
    try:
        fd, tmp_name = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        tmp_path = Path(tmp_name)
        tmp_path.write_bytes(doc_bytes)

        pages = await parser.extract_text_and_offsets(tmp_path)
        page_texts: list[str] = []
        for page in pages:
            text = page.get("text") if isinstance(page, dict) else None
            if isinstance(text, str) and text.strip():
                page_texts.append(text)
        return "\n\n".join(page_texts)
    except Exception as exc:
        logger.warning("di_pdf_parse_failed", error=str(exc))
        return ""
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:  # pragma: no cover - best-effort cleanup
                logger.debug("di_pdf_tempfile_cleanup_failed", path=str(tmp_path))
