"""
Service for parsing FIEBDC-3 (BC3) budget files.

This module provides a parser for the FIEBDC-3 standard format, which is
common in the construction industry in Spain and Latin America. It handles
the specific challenges of this legacy format, such as character encoding and
validates file structure before full parsing.
"""

from typing import List, Dict, Any

from pyfiebdc import FIEBDC
from src.modules.projects.schemas import BOMItemBase as BudgetItem
from src.core.exceptions import InvalidFileFormatException, DocumentParsingError

# List of encodings to try when opening a BC3 file.
# The order is important: start with the most common (UTF-8) and fall back
# to legacy encodings typical for older Windows-based software.
ENCODING_GUESS_ORDER = ['utf-8', 'cp1252', 'iso-8859-1']


class Bc3ParserService:
    """
    Parses budget data from FIEBDC-3 (.bc3) files with pre-validation.
    """

    def _validate_header(self, decoded_content: str) -> bool:
        """
        Checks if the file starts with the mandatory ~V record.
        A valid FIEBDC-3 file must begin with this version identifier.
        """
        # We strip leading whitespace as some files might have it.
        return decoded_content.lstrip().startswith("~V|")

    def parse_bc3(self, file_content: bytes, filename: str = None) -> List[BudgetItem]:
        """
        Main entry point for parsing a BC3 file's binary content.

        It automatically detects the character encoding by validating the header,
        then normalizes the hierarchical BC3 data into a flat list of budget items.

        Args:
            file_content: The binary content of the .bc3 file.
            filename: The name of the file (used for error reporting).

        Returns:
            A list of BudgetItem objects.

        Raises:
            InvalidFileFormatException: If the file is not a valid BC3 file
                                        (missing header or wrong encoding).
            DocumentParsingError: If an error occurs during the parsing process
                                  by the underlying library.
        """
        # --- Critical: Encoding Detection and Header Validation ---
        # This block now integrates header validation into the encoding detection loop.
        # A file is only considered correctly decoded if the content can be read AND
        # the FIEBDC-3 header (~V|) is present. This is a "fail-fast" strategy.
        decoded_content = None
        for encoding in ENCODING_GUESS_ORDER:
            try:
                content_as_string = file_content.decode(encoding)
                if self._validate_header(content_as_string):
                    decoded_content = content_as_string
                    break  # Stop on the first valid decoding and validation
            except UnicodeDecodeError:
                continue

        if decoded_content is None:
            raise InvalidFileFormatException(
                message="The file is not a valid FIEBDC-3 format (missing or invalid header '~V|') "
                        "or could not be decoded.",
                document_type="bc3",
                filename=filename
            )

        # --- Parsing and Data Extraction ---
        try:
            bc3_file = FIEBDC(decoded_content)
        except Exception as e:
            # Wrap generic library errors into our custom exception
            raise DocumentParsingError(
                message=f"Failed to process BC3 file '{filename}'. The file may be malformed. "
                        f"Original error: {e}",
                document_type="bc3",
                filename=filename
            )

        all_items: List[BudgetItem] = []
        
        for concept in bc3_file.conceptos:
            if concept.precio and concept.precio > 0:
                item_data = {
                    "item_code": concept.codigo,
                    "item_name": concept.resumen,
                    "description": concept.descripcion,
                    "unit": concept.ud,
                    "quantity": 1.0,
                    "unit_price": concept.precio,
                    "total_price": concept.precio,
                }
                try:
                    budget_item = BudgetItem(**item_data)
                    all_items.append(budget_item)
                except Exception:
                    continue
        
        return all_items

    def get_project_details(self, file_content: bytes) -> Dict[str, Any]:
        """
        Extracts high-level project details from the BC3 header.
        This is an example of a potential useful utility method.
        """
        # This is a simplified decoding for utility purposes.
        # Production use should employ the robust multi-encoding strategy.
        try:
            decoded_content = file_content.decode('utf-8')
            if not self._validate_header(decoded_content):
                return {}
                
            bc3_file = FIEBDC(decoded_content)
            header = bc3_file.cabecera
            return {
                "project_name": header.nombre_proyecto,
                "concurso_date": header.fecha_concurso,
                "file_date": header.fecha,
                "currency": header.moneda,
                "owner": header.propietario
            }
        except Exception:
            return {}

