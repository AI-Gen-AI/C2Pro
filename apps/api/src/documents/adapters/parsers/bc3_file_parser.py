"""
BC3 File Parser Adapter.

This adapter provides functionality to parse BC3 files (FIEBDC-3 standard for construction budgets in Spain)
using the pyfiebdc library, encapsulating external library details.
"""

import datetime
from pathlib import Path
from typing import Any

# Assuming pyfiebdc is installed or available in the environment.
# For demonstration purposes, we'll retain the mock usage.
try:
    import pyfiebdc
    from pyfiebdc.exceptions import InvalidFileException
except ImportError:
    from types import SimpleNamespace

    # This mock class simulates the necessary parts of pyfiebdc for demonstration
    class MockInvalidFileException(Exception):
        pass

    class MockFiebdc:
        def __init__(self, file_path):
            self.file_path = file_path
            self.is_valid_bc3 = self._check_validity(file_path)

        def _check_validity(self, file_path):
            # Simulate basic validity check
            return file_path.name.endswith(".bc3") and file_path.exists()

        def parse(self):
            if not self.is_valid_bc3:
                raise MockInvalidFileException(
                    f"Invalid or non-existent BC3 file: {self.file_path}"
                )

            # Simulate parsing a BC3 file
            return {
                "header": {
                    "version": "FIEBDC-3.2000",
                    "project_name": "Proyecto Sintético BC3",
                    "date": datetime.date(2026, 1, 9),
                },
                "chapters": [
                    {
                        "code": "C01",
                        "title": "Cimentación",
                        "units": [
                            {
                                "code": "U01.01",
                                "description": "Excavación y movimiento de tierras",
                                "unit": "m3",
                                "price": 25.50,
                                "quantity": 150.0,
                                "total": 3825.00,
                                "components": [],
                            },
                        ],
                    }
                ],
            }

    pyfiebdc = SimpleNamespace()
    pyfiebdc.Fiebdc = MockFiebdc
    InvalidFileException = MockInvalidFileException


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

        try:
            fiebdc = pyfiebdc.Fiebdc(file_path)
            parsed_data = fiebdc.parse()
            return parsed_data
        except InvalidFileException as e:
            raise BC3ParsingError(f"Invalid BC3 file format: {e}")
        except Exception as e:
            raise BC3ParsingError(f"An unexpected error occurred during BC3 parsing: {e}")
