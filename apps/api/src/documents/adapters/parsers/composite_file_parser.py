"""
Composite File Parser Adapter.

This adapter implements the IFileParserService port, delegating parsing
to specific parsers based on document type and format.
"""
from pathlib import Path
from typing import Any, Dict

from src.documents.domain.models import Document, DocumentType
from src.documents.ports.file_parser_service import IFileParserService
from src.documents.adapters.parsers.bc3_file_parser import BC3FileParser, BC3ParsingError
from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser, ExcelParsingError
from src.documents.adapters.parsers.pdf_file_parser import PDFFileParser, PDFParsingError


class CompositeFileParser(IFileParserService):
    def __init__(
        self,
        bc3_parser: BC3FileParser,
        excel_parser: ExcelFileParser,
        pdf_parser: PDFFileParser,
    ):
        self.bc3_parser = bc3_parser
        self.excel_parser = excel_parser
        self.pdf_parser = pdf_parser

    async def parse_document_file(self, document: Document, file_path: Path) -> Dict[str, Any]:
        """
        Parses a document file based on its type and format by delegating to specific parsers.
        """
        file_format = (document.file_format or "").lower()

        if file_format == ".pdf":
            try:
                text_blocks = await self.pdf_parser.extract_text_and_offsets(file_path)
                return {"file_format": file_format, "text_blocks": text_blocks}
            except PDFParsingError as e:
                raise ValueError(f"PDF parsing failed: {e}")

        if file_format in {".xlsx", ".xls"}:
            if document.document_type == DocumentType.SCHEDULE:
                try:
                    schedule = await self.excel_parser.parse_schedule(file_path)
                    return {"file_format": file_format, "schedule": schedule}
                except ExcelParsingError as e:
                    raise ValueError(f"Excel schedule parsing failed: {e}")
            if document.document_type == DocumentType.BUDGET:
                try:
                    budget = await self.excel_parser.parse_budget(file_path)
                    return {"file_format": file_format, "budget": budget}
                except ExcelParsingError as e:
                    raise ValueError(f"Excel budget parsing failed: {e}")
            raise ValueError(
                f"Excel parsing for document type {document.document_type.value} is not supported."
            )

        if file_format == ".bc3":
            try:
                budget = await self.bc3_parser.parse(file_path)
                return {"file_format": file_format, "budget": budget}
            except BC3ParsingError as e:
                raise ValueError(f"BC3 parsing failed: {e}")

        raise ValueError(f"No parser available for file format: {file_format} and document type: {document.document_type.value}")
