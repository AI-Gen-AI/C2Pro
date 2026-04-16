"""Decision Intelligence ingestion port adapter.

Parses raw document bytes (PDF, with plain-text fallback) into the chunked
representation required by the DecisionOrchestrationService.

Refers to Suite ID: TS-I13-E2E-REAL-001.
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger()

_DEFAULT_CHUNK_CHARS = 1500
_DEFAULT_CHUNK_OVERLAP = 200


class IngestionPortAdapter:
    """Real IngestionPort implementation backed by PyMuPDF.

    ``ingest_document`` accepts raw document bytes (PDF or UTF-8 text),
    extracts per-page text, and emits chunks compatible with the I13
    orchestration pipeline. When PyMuPDF fails or the payload is not a
    PDF, the adapter falls back to decoding the bytes as UTF-8 so
    downstream stages never see an empty chunk list.
    """

    def __init__(
        self,
        *,
        chunk_chars: int = _DEFAULT_CHUNK_CHARS,
        chunk_overlap: int = _DEFAULT_CHUNK_OVERLAP,
    ) -> None:
        if chunk_chars <= 0:
            raise ValueError("chunk_chars must be positive")
        if chunk_overlap < 0 or chunk_overlap >= chunk_chars:
            raise ValueError("chunk_overlap must be in [0, chunk_chars)")
        self._chunk_chars = chunk_chars
        self._chunk_overlap = chunk_overlap

    async def ingest_document(self, doc_bytes: bytes) -> dict[str, Any]:
        if not doc_bytes:
            return {"chunks": [], "page_count": 0, "source": "empty"}

        pages = self._extract_pdf_pages(doc_bytes)
        source = "pdf"
        if pages is None:
            text = self._decode_plaintext(doc_bytes)
            pages = [(1, text)] if text else []
            source = "plaintext"

        chunks: list[dict[str, Any]] = []
        for page_number, page_text in pages:
            for offset, piece in self._chunk_text(page_text):
                if not piece.strip():
                    continue
                chunks.append(
                    {
                        "text": piece,
                        "page": page_number,
                        "offset": offset,
                    }
                )

        logger.info(
            "di_ingestion_completed",
            source=source,
            page_count=len(pages),
            chunk_count=len(chunks),
        )
        return {"chunks": chunks, "page_count": len(pages), "source": source}

    def _extract_pdf_pages(self, doc_bytes: bytes) -> list[tuple[int, str]] | None:
        try:
            import fitz  # PyMuPDF
        except ImportError:
            logger.warning("di_ingestion_pymupdf_unavailable")
            return None

        try:
            document = fitz.open(stream=doc_bytes, filetype="pdf")
        except Exception as exc:
            logger.warning("di_ingestion_pdf_open_failed", error=str(exc))
            return None

        pages: list[tuple[int, str]] = []
        try:
            for index in range(document.page_count):
                page = document.load_page(index)
                text = page.get_text("text") or ""
                pages.append((index + 1, text.strip()))
        finally:
            document.close()
        return pages

    @staticmethod
    def _decode_plaintext(doc_bytes: bytes) -> str:
        try:
            return doc_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return doc_bytes.decode("utf-8", errors="replace")

    def _chunk_text(self, text: str) -> list[tuple[int, str]]:
        if not text:
            return []
        step = self._chunk_chars - self._chunk_overlap
        chunks: list[tuple[int, str]] = []
        start = 0
        while start < len(text):
            end = start + self._chunk_chars
            chunks.append((start, text[start:end]))
            if end >= len(text):
                break
            start += step
        return chunks
