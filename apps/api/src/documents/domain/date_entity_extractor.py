"""
TS-UD-DOC-ENT-001: Date entity extraction domain service.
"""

import re
from datetime import date, timedelta
from typing import List, NamedTuple, Optional, Callable
from enum import Enum, auto

# A robust date parsing library is a good choice here.
# For this implementation, we will simulate its behavior.
# In a real project, one would use `pip install python-dateutil`.
from dateutil.parser import parse as dateutil_parse

class DateContextType(Enum):
    """Enumerates the context in which a date was found."""
    DELIVERY = auto()
    SIGNATURE = auto()
    START = auto()
    END = auto()
    RANGE_START = auto()
    RANGE_END = auto()
    GENERIC = auto()

class ExtractedDate(NamedTuple):
    """Represents a single extracted date entity from a text."""
    extracted_date: date
    context: DateContextType
    text: str
    start: int
    end: int

class DateEntityExtractor:
    """
    A domain service to extract date entities from text.
    It recognizes various absolute, relative, and contextual date formats.
    """

    def __init__(self):
        # Spanish month names for normalization before parsing
        self.spanish_months = {
            "enero": "January", "febrero": "February", "marzo": "March", "abril": "April",
            "mayo": "May", "junio": "June", "julio": "July", "agosto": "August",
            "septiembre": "September", "octubre": "October", "noviembre": "November", "diciembre": "December"
        }

        # A list of regex patterns to find dates.
        # Each tuple contains: (regex, context, handler_method_name)
        self.patterns = [
            # Contextual Dates first to give them priority
            (re.compile(r"\b(?:fecha de entrega:|delivery date:)\s*(?P<date>[\w\s,/-]+)", re.IGNORECASE), DateContextType.DELIVERY, self._parse_absolute),
            (re.compile(r"\b(?:firmado el|signed on)\s*(?P<date>[\w\s,/-]+)", re.IGNORECASE), DateContextType.SIGNATURE, self._parse_absolute),
            (re.compile(r"\b(?:fecha de inicio:|start date is)\s*(?P<date>[\w\s,/-]+)", re.IGNORECASE), DateContextType.START, self._parse_absolute),
            (re.compile(r"\b(?:fecha de fin:|end date is)\s*(?P<date>[\w\s,/-]+)", re.IGNORECASE), DateContextType.END, self._parse_absolute),
            # Date Ranges
            (
                re.compile(r"\bfrom\s*(?P<date>[\w\s,/-]+?)(?=\s+to\b)", re.IGNORECASE),
                DateContextType.RANGE_START,
                self._parse_absolute,
            ),
            (re.compile(r"\bto\s*(?P<date>[\w\s,/-]+)", re.IGNORECASE), DateContextType.RANGE_END, self._parse_absolute),
            # Relative Dates
            (
                re.compile(
                    r"\b(in|within|after)\s*(?P<num>\d+)\s*(?P<unit>day|days|month|months|year|years)\b",
                    re.IGNORECASE,
                ),
                DateContextType.GENERIC,
                self._parse_relative,
            ),
            (re.compile(r"\b(?P<num>\d+)\s*days\s*from\s*(?P<base_date>[\w\s,/-]+)", re.IGNORECASE), DateContextType.GENERIC, self._parse_relative_from),
            # Absolute Dates (generic)
            (re.compile(r"\b\d{4}-\d{1,2}-\d{1,2}\b"), DateContextType.GENERIC, self._parse_absolute),
            (re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b"), DateContextType.GENERIC, self._parse_absolute),
            (re.compile(r"\b\d{1,2}\s+de\s+\w+\s+de\s+\d{4}\b", re.IGNORECASE), DateContextType.GENERIC, self._parse_absolute),
            (re.compile(r"\b\w+\s+\d{1,2},\s*\d{4}\b", re.IGNORECASE), DateContextType.GENERIC, self._parse_absolute),
        ]

    def _normalize_spanish_month(self, text: str) -> str:
        """Replaces Spanish month names with English ones for the parser."""
        for esp, eng in self.spanish_months.items():
            text = text.lower().replace(esp, eng)
        # "10 de enero de 2025" -> "10 january 2025"
        text = re.sub(r"\s+de\s+", " ", text)
        return text

    # --- Handler Methods ---
    def _parse_absolute(self, match: re.Match, base_date: date) -> Optional[date]:
        date_str = match.group('date') if 'date' in match.groupdict() else match.group(0)
        try:
            # Normalize Spanish months before parsing
            normalized_str = self._normalize_spanish_month(date_str)
            # The parser is robust, but can fail on impossible dates (e.g., 99/99/9999)
            return dateutil_parse(normalized_str, dayfirst=True).date()
        except (ValueError, TypeError):
            # If parsing fails, it's not a valid date format, so ignore it.
            return None

    def _parse_relative(self, match: re.Match, base_date: date) -> Optional[date]:
        num = int(match.group('num'))
        unit = match.group('unit').lower()
        delta = timedelta(days=0)
        if 'day' in unit:
            delta = timedelta(days=num)
        elif 'month' in unit:
            delta = timedelta(days=num * 30) # Approximate
        elif 'year' in unit:
            delta = timedelta(days=num * 365) # Approximate
        return base_date + delta

    def _parse_relative_from(self, match: re.Match, base_date: date) -> Optional[date]:
        num = int(match.group('num'))
        base_date_str = match.group('base_date')
        try:
            new_base_date = dateutil_parse(base_date_str, dayfirst=True).date()
            return new_base_date + timedelta(days=num)
        except (ValueError, TypeError):
            return None

    async def extract(self, text: str, base_date: date) -> List[ExtractedDate]:
        """
        Extracts all recognizable date entities from the input text.

        Args:
            text: The string to scan for dates.
            base_date: The reference date for calculating relative dates.

        Returns:
            A list of ExtractedDate objects, sorted by their appearance in the text.
        """
        found_dates: List[ExtractedDate] = []
        
        for pattern, context, handler in self.patterns:
            for match in pattern.finditer(text):
                extracted_date = handler(match, base_date)
                if extracted_date:
                    # To avoid re-processing the same text chunk, check if this overlaps with a found date
                    is_overlapping = any(
                        max(d.start, match.start()) < min(d.end, match.end())
                        for d in found_dates
                    )
                    if not is_overlapping:
                        found_dates.append(ExtractedDate(
                            extracted_date=extracted_date,
                            context=context,
                            text=match.group(0),
                            start=match.start(),
                            end=match.end()
                        ))
        
        # Sort results by their starting position in the text
        found_dates.sort(key=lambda d: d.start)
        return found_dates
