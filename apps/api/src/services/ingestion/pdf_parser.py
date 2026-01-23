"""
Service for parsing PDF documents.

This module provides a service to extract text and metadata from PDF files
using the PyMuPDF (fitz) library, with a hybrid strategy for handling
both plain text and structured tables.
"""
import re
from typing import TypedDict, List, Dict, Any, Optional

import fitz  # PyMuPDF

from src.core.exceptions import DocumentEncryptedError, ScannedDocumentError


class PageContent(TypedDict):
    """A dictionary representing the content of a single page."""
    page_number: int
    text_content: str


class ParsedDocument(TypedDict):
    """A dictionary representing the structured content of a parsed document."""
    full_text: str
    meta: Dict[str, Any]
    page_count: int
    pages: List[PageContent]
    tables_data: List[Dict[str, Any]] # Structured data from all tables


class PdfParserService:
    """
    A service to extract structured text content from PDF files,
    specializing in converting tables to Markdown for LLM consumption.
    """

    def _table_to_markdown(self, table: fitz.Table, page_num: int) -> tuple[str, list[list[str]] | None]:
        """
        Converts a fitz.Table object to a Markdown string.

        Args:
            table: The fitz.Table object to convert.
            page_num: The page number where the table was found.

        Returns:
            A tuple containing the Markdown string and the raw table data.
            If the table is considered low quality, the Markdown string will be
            a simple text block, and the raw data will be None.
        """
        raw_table = table.extract()
        if not raw_table:
            return "", None

        # Fallback for low-quality tables
        total_cells = len(raw_table) * len(raw_table[0])
        empty_cells = sum(row.count(None) + row.count('') for row in raw_table)
        if total_cells > 0 and (empty_cells / total_cells) > 0.8:
            # Degradation: return as simple text block
            plain_text = "\n".join(" ".join(str(cell) for cell in row if cell) for row in raw_table)
            return plain_text, None

        # Clean None values and escape pipes for Markdown
        cleaned_table = []
        for row in raw_table:
            cleaned_row = [str(cell).replace('|', '\\|') if cell is not None else '' for cell in row]
            cleaned_table.append(cleaned_row)

        header = " | ".join(cleaned_table[0])
        separator = " | ".join(['---'] * len(cleaned_table[0]))
        body = "\n".join([" | ".join(row) for row in cleaned_table[1:]])

        markdown_table = f"| {header} |\n| {separator} |\n| {body} |"
        
        # Add a caption for context
        caption = f"\n\n--- Table found on page {page_num} ---\n\n"
        return caption + markdown_table + caption, raw_table


    def extract_text(self, file_content: bytes, filename: Optional[str] = None) -> ParsedDocument:
        """
        Extracts text and metadata from a PDF, preserving tables in Markdown.

        Args:
            file_content: The binary content of the PDF file.
            filename: The original name of the file, for error reporting.

        Returns:
            A ParsedDocument dictionary with text, metadata, and structured tables.

        Raises:
            DocumentEncryptedError: If the PDF is password-protected.
            ScannedDocumentError: If the PDF contains no extractable text.
            RuntimeError: For other fitz-related parsing errors.
        """
        try:
            doc = fitz.open(stream=file_content, filetype="pdf")
        except fitz.errors.FitzError as e:
            raise RuntimeError(f"Failed to open PDF stream for '{filename}': {e}") from e

        if doc.is_encrypted:
            raise DocumentEncryptedError(filename=filename)

        all_pages_content: List[PageContent] = []
        all_tables_data: List[Dict[str, Any]] = []
        total_text_len = 0
        
        # Configure table detection strategy
        table_settings = {
            "vertical_strategy": "lines",
            "horizontal_strategy": "lines",
            "snap_tolerance": 5,
            "join_tolerance": 5,
        }

        for page_num in range(doc.page_count):
            page = doc.load_page(page_num)
            
            # 1. Detect tables and their bounding boxes
            tables = page.find_tables(table_settings)
            table_bboxes = [fitz.Rect(t.bbox) for t in tables]

            # 2. Extract text blocks, excluding those fully inside tables
            text_blocks = page.get_text("blocks")
            filtered_blocks = []
            for block in text_blocks:
                block_rect = fitz.Rect(block[:4])
                is_in_table = any(table_bbox.contains(block_rect) for table_bbox in table_bboxes)
                if not is_in_table:
                    filtered_blocks.append(block)

            # 3. Create a sorted list of content items (tables and text blocks)
            content_items = []
            for i, table in enumerate(tables):
                content_items.append({"type": "table", "bbox": table.bbox, "item": table, "index": i})
            
            for block in filtered_blocks:
                content_items.append({"type": "text", "bbox": block[:4], "item": block[4]})

            # Sort by vertical position, then horizontal
            content_items.sort(key=lambda x: (x["bbox"][1], x["bbox"][0]))
            
            # 4. Reconstruct page content
            page_text_parts = []
            for item in content_items:
                if item["type"] == "text":
                    page_text_parts.append(item["item"])
                elif item["type"] == "table":
                    markdown_table, raw_data = self._table_to_markdown(item["item"], page_num + 1)
                    page_text_parts.append(markdown_table)
                    if raw_data:
                        all_tables_data.append({
                            "page": page_num + 1,
                            "data": raw_data
                        })
            
            # Basic cleaning for the reconstructed page text
            page_text = "".join(page_text_parts)
            cleaned_text = re.sub(r'\s{2,}', ' ', page_text).strip()
            total_text_len += len(cleaned_text)

            all_pages_content.append({
                "page_number": page_num + 1,
                "text_content": cleaned_text
            })

        if total_text_len == 0 and doc.page_count > 0:
            raise ScannedDocumentError(filename=filename)

        full_text = "\n\n".join(p["text_content"] for p in all_pages_content)
        full_text = full_text.replace('\x00', '')

        result: ParsedDocument = {
            "full_text": full_text,
            "meta": {
                "author": doc.metadata.get("author"),
                "title": doc.metadata.get("title"),
                "creation_date": doc.metadata.get("creationDate"),
                "producer": doc.metadata.get("producer"),
            },
            "page_count": doc.page_count,
            "pages": all_pages_content,
            "tables_data": all_tables_data,
        }
        
        doc.close()
        return result
