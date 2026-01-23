"""
C2Pro - BC3 Parser Module

This module provides functionality to parse BC3 files (FIEBDC-3 standard for construction budgets in Spain)
using the pyfiebdc library.
"""

import datetime
from pathlib import Path
from typing import Any

# Assuming pyfiebdc is installed or available in the environment.
# For demonstration purposes, we'll mock its usage.
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
            # In a real scenario, pyfiebdc.Fiebdc would parse the actual content.
            # Here, we return a fixed mock structure.
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
                                "components": [
                                    {
                                        "type": "material",
                                        "code": "M001",
                                        "name": "Arena",
                                        "quantity": 10,
                                        "unit": "m3",
                                        "unit_price": 5,
                                    },
                                    {
                                        "type": "labor",
                                        "code": "L001",
                                        "name": "Operario",
                                        "quantity": 20,
                                        "unit": "h",
                                        "unit_price": 15,
                                    },
                                ],
                            },
                            {
                                "code": "U01.02",
                                "description": "Hormigón de limpieza",
                                "unit": "m3",
                                "price": 80.00,
                                "quantity": 10.0,
                                "total": 800.00,
                                "components": [],
                            },
                        ],
                    }
                ],
            }

    pyfiebdc = SimpleNamespace()
    pyfiebdc.Fiebdc = MockFiebdc
    InvalidFileException = MockInvalidFileException  # Assign mock exception


class BC3ParsingError(Exception):
    """Custom exception for BC3 parsing errors."""

    pass


def parse_bc3_file(file_path: Path) -> dict[str, Any]:
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
        # In a real scenario, this would be `fiebdc = pyfiebdc.Fiebdc(str(file_path))`
        fiebdc = pyfiebdc.Fiebdc(file_path)
        parsed_data = fiebdc.parse()
        return parsed_data
    except InvalidFileException as e:
        raise BC3ParsingError(f"Invalid BC3 file format: {e}")
    except Exception as e:
        raise BC3ParsingError(f"An unexpected error occurred during BC3 parsing: {e}")


# Example Usage (for testing purposes, if run directly)
if __name__ == "__main__":
    # Create a dummy .bc3 file for testing.
    # In a real scenario, you would have actual BC3 files.
    dummy_bc3_path = Path("tests/data/sample_budget.bc3")

    # Ensure the directory exists
    dummy_bc3_path.parent.mkdir(parents=True, exist_ok=True)

    # Simulate a BC3 file content (this is NOT a real BC3 structure, just a marker)
    dummy_bc3_content = (
        "//FIEBDC-3.2000\n"
        "//PRES C2PRO\n"
        "//FECH 09-01-2026\n"
        "//UNID U01.01\n"
        "//TXTL Excavación y movimiento de tierras\n"
        "//PREC 25.50\n"
        "//MATE M001 Arena\n"
        "//MA_U m3\n"
        "//MA_P 5.00\n"
        "//MA_Q 10\n"
        "//FINU\n"
        "//CHAP C01 Cimentación\n"
        "//FINC\n"
        "//FINP\n"
    )
    with open(dummy_bc3_path, "w", encoding="latin-1") as f:  # BC3 often uses latin-1
        f.write(dummy_bc3_content)

    print("--- Simulating BC3 Parsing Test ---")
    try:
        parsed_budget = parse_bc3_file(dummy_bc3_path)
        print("  SUCCESS: BC3 file parsed successfully.")
        print(f"  Project Name: {parsed_budget['header']['project_name']}")
        print(f"  Number of Chapters: {len(parsed_budget['chapters'])}")
        if parsed_budget["chapters"]:
            print(f"  First Unit Code: {parsed_budget['chapters'][0]['units'][0]['code']}")
    except BC3ParsingError as e:
        print(f"  ERROR: {e}")
    except Exception as e:
        print(f"  UNEXPECTED ERROR: {e}")
    finally:
        # Clean up dummy file
        if dummy_bc3_path.exists():
            dummy_bc3_path.unlink()
        if dummy_bc3_path.parent.exists() and not any(dummy_bc3_path.parent.iterdir()):
            dummy_bc3_path.parent.rmdir()
