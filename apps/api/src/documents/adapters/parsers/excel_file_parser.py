"""
Excel Parser Adapter.

This adapter provides functionality to parse schedule and budget data from Excel files
using the openpyxl library, encapsulating external library details.
"""

from pathlib import Path
from typing import Any, List

import openpyxl
from openpyxl.utils.exceptions import InvalidFileException


class ExcelParsingError(Exception):
    """Custom exception for Excel parsing errors."""
    pass


class ExcelFileParser:
    """
    Adapter class for parsing Excel files.
    Encapsulates the logic specific to the Excel format and `openpyxl` library.
    """
    async def parse_schedule(self, file_path: Path) -> list[dict[str, Any]]:
        """
        Parses schedule data from a standard Excel file format.

        Assumes the first sheet contains the schedule with a header row.
        Expected columns (case-insensitive): 'Task', 'Start Date', 'End Date', 'Duration'.

        Args:
            file_path: The path to the Excel file (.xlsx).

        Returns:
            A list of dictionaries, where each dictionary represents a schedule task.

        Raises:
            ExcelParsingError: If the file cannot be opened or does not match the expected format.
        """
        try:
            workbook = openpyxl.load_workbook(file_path, data_only=True)
            sheet = workbook.active

            headers = [cell.value.lower() if cell.value else "" for cell in sheet[1]]

            # Define expected headers
            expected_headers = ["task", "start date", "end date"]
            if not all(h in headers for h in expected_headers):
                raise ExcelParsingError(
                    f"Missing one or more required headers: {', '.join(expected_headers)}"
                )

            schedule_data = []
            for row in sheet.iter_rows(min_row=2, values_only=True):
                row_data = dict(zip(headers, row))
                # Filter out empty rows
                if any(row_data.values()):
                    schedule_data.append(
                        {
                            "task": row_data.get("task"),
                            "start_date": row_data.get("start date"),
                            "end_date": row_data.get("end date"),
                            "duration": row_data.get("duration"),
                        }
                    )
            return schedule_data

        except (InvalidFileException, FileNotFoundError) as e:
            raise ExcelParsingError(f"Failed to open or read Excel file: {e}")
        except Exception as e:
            raise ExcelParsingError(f"An unexpected error occurred during Excel schedule parsing: {e}")

    async def parse_budget(self, file_path: Path) -> list[dict[str, Any]]:
        """
        Parses budget data from a standard Excel file format.

        Assumes the first sheet contains the budget with a header row.
        Expected columns (case-insensitive): 'Item', 'Quantity', 'Unit Price', 'Total'.

        Args:
            file_path: The path to the Excel file (.xlsx).

        Returns:
            A list of dictionaries, where each dictionary represents a budget line item.

        Raises:
            ExcelParsingError: If the file cannot be opened or does not match the expected format.
        """
        try:
            workbook = openpyxl.load_workbook(file_path, data_only=True)
            sheet = workbook.active

            headers = [cell.value.lower() if cell.value else "" for cell in sheet[1]]

            # Define expected headers
            expected_headers = ["item", "quantity", "unit price", "total"]
            if not all(h in headers for h in expected_headers):
                raise ExcelParsingError(
                    f"Missing one or more required headers: {', '.join(expected_headers)}"
                )

            budget_data = []
            for row in sheet.iter_rows(min_row=2, values_only=True):
                row_data = dict(zip(headers, row))
                if any(row_data.values()):
                    budget_data.append(
                        {
                            "item": row_data.get("item"),
                            "quantity": row_data.get("quantity"),
                            "unit_price": row_data.get("unit price"),
                            "total": row_data.get("total"),
                        }
                    )
            return budget_data

        except (InvalidFileException, FileNotFoundError) as e:
            raise ExcelParsingError(f"Failed to open or read Excel file: {e}")
        except Exception as e:
            raise ExcelParsingError(f"An unexpected error occurred during Excel budget parsing: {e}")
