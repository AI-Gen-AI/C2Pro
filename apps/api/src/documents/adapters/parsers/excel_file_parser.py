"""
Excel Parser Adapter.

This adapter provides functionality to parse schedule and budget data from Excel files
using the openpyxl library, encapsulating external library details.
"""

from pathlib import Path
from typing import Any

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

            header_row_index, headers = self._find_schedule_headers(sheet)
            if header_row_index is None:
                expected_headers = ["task/actividad", "start date/inicio", "end date/fin"]
                raise ExcelParsingError(
                    f"Missing one or more required headers: {', '.join(expected_headers)}"
                )

            schedule_data = []
            for row in sheet.iter_rows(min_row=header_row_index + 1, values_only=True):
                row_data = dict(zip(headers, row, strict=False))
                # Filter out empty rows
                if any(row_data.values()):
                    schedule_data.append(
                        {
                            "task": row_data.get("task"),
                            "start_date": row_data.get("start date"),
                            "end_date": row_data.get("end date"),
                            "duration": row_data.get("duration"),
                            "wbs": row_data.get("wbs"),
                            "predecessors": row_data.get("predecessors"),
                        }
                    )
            return schedule_data

        except ExcelParsingError:
            raise
        except (InvalidFileException, FileNotFoundError) as e:
            raise ExcelParsingError(f"Failed to open or read Excel file: {e}")
        except Exception as e:
            raise ExcelParsingError(f"An unexpected error occurred during Excel schedule parsing: {e}")
        finally:
            workbook_to_close = locals().get("workbook")
            if workbook_to_close is not None and hasattr(workbook_to_close, "close"):
                workbook_to_close.close()

    @staticmethod
    def _find_schedule_headers(sheet: Any) -> tuple[int | None, list[str]]:
        aliases = {
            "task": {"task", "actividad"},
            "start date": {"start date", "inicio"},
            "end date": {"end date", "fin"},
            "duration": {"duration", "duración", "duracion", "duración (días)", "duracion (dias)"},
            "wbs": {"wbs"},
            "predecessors": {"predecessors", "predecesoras"},
        }

        for row_index, row in enumerate(sheet.iter_rows(values_only=True), start=1):
            normalized = [
                str(value).strip().lower() if value is not None else ""
                for value in row
            ]
            canonical_headers = [
                next(
                    (
                        canonical
                        for canonical, accepted in aliases.items()
                        if header in accepted
                    ),
                    header,
                )
                for header in normalized
            ]
            required = {"task", "start date", "end date"}
            if required.issubset(set(canonical_headers)):
                return row_index, canonical_headers

        first_row = getattr(sheet, "__getitem__", lambda _: [])(1)
        fallback_headers = [
            str(getattr(cell, "value", cell)).strip().lower() if cell is not None else ""
            for cell in first_row
        ]
        fallback_canonical_headers = [
            next(
                (
                    canonical
                    for canonical, accepted in aliases.items()
                    if header in accepted
                ),
                header,
            )
            for header in fallback_headers
        ]
        if {"task", "start date", "end date"}.issubset(set(fallback_canonical_headers)):
            return 1, fallback_canonical_headers

        return None, []

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
                row_data = dict(zip(headers, row, strict=False))
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
