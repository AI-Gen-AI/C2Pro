"""
BC3 File Parser Adapter.

This adapter provides functionality to parse BC3 files (FIEBDC-3 standard for construction budgets in Spain)
using the pyfiebdc library, encapsulating external library details.
"""

from pathlib import Path
from typing import Any

try:
    import pyfiebdc
    from pyfiebdc.exceptions import InvalidFileException
except ImportError:
    pyfiebdc = None
    InvalidFileException: type[Exception] | None = None
    PYFIEBDC_AVAILABLE = False
else:
    PYFIEBDC_AVAILABLE = True


class BC3ParsingError(Exception):
    """Custom exception for BC3 parsing errors."""
    pass


class BC3FileParser:
    """
    Adapter class for parsing BC3 files.
    Encapsulates the logic specific to the BC3 format and `pyfiebdc` library.
    """
    async def parse(self, file_path: Path) -> dict[str, Any]:
        """
        Parses a BC3 file and extracts budget items.

        Args:
            file_path: The path to the BC3 file.

        Returns:
            A dictionary containing the parsed BC3 data, including header, chapters, and units.

        Raises:
            BC3ParsingError: If the file cannot be opened, is not a valid BC3, or parsing fails.
        """
        if not file_path.exists():
            raise BC3ParsingError(f"BC3 file not found: {file_path}")
        if not file_path.suffix.lower() == ".bc3":
            raise BC3ParsingError(f"File is not a BC3 file: {file_path}")
        if not PYFIEBDC_AVAILABLE or pyfiebdc is None:
            raise BC3ParsingError(
                "BC3 parser is unavailable: pyfiebdc is not installed; "
                "no budget data was generated"
            )

        try:
            fiebdc = pyfiebdc.Fiebdc(file_path)
            parsed_data: dict[str, Any] = fiebdc.parse()
            return parsed_data
        except Exception as exc:
            if InvalidFileException is not None and isinstance(exc, InvalidFileException):
                raise BC3ParsingError(f"Invalid BC3 file format: {exc}") from exc
            raise BC3ParsingError(
                f"An unexpected error occurred during BC3 parsing: {exc}"
            ) from exc
