"""
TS-UD-DOC-ENT-002: Money entity extraction domain service.
"""

import re
from typing import List, NamedTuple, Union, Any
from enum import Enum, auto

# --- DTOs and Enums ---
class MoneyContextType(Enum):
    """Enumerates the context in which a monetary value was found."""
    ADVANCE = auto()
    FINAL_PAYMENT = auto()
    PENALTY = auto()
    TOTAL = auto()
    GENERIC = auto()

class ExtractedMoney(NamedTuple):
    """Represents a single extracted monetary value."""
    amount: float
    currency: str
    context: MoneyContextType
    text: str
    start: int
    end: int

class ExtractedPercentage(NamedTuple):
    """Represents a single extracted percentage value."""
    value: float
    context: MoneyContextType # Re-using for consistency, might be GENERIC
    text: str
    start: int
    end: int

# A union type for the return value
ExtractedEntity = Union[ExtractedMoney, ExtractedPercentage]

# --- Domain Service Implementation ---
class MoneyEntityExtractor:
    """
    A domain service to extract monetary and percentage entities from text.
    """

    def __init__(self):
        amount_pattern = r"-?\d{1,3}(?:[.,\s]\d{3})*(?:[.,]\d+)?|-?\d+(?:[.,]\d+)?"
        self.patterns = [
            (
                "EUR",
                MoneyContextType.ADVANCE,
                re.compile(
                    rf"\b(?:anticipo|advance)\b[^-\d€$]*(?P<amount>{amount_pattern})\s*(?:€|euros?\b)",
                    re.IGNORECASE,
                ),
            ),
            (
                "EUR",
                MoneyContextType.FINAL_PAYMENT,
                re.compile(
                    rf"\b(?:pago final de|final payment of)\b[^-\d€$]*(?P<amount>{amount_pattern})\s*(?:€|euros?\b)",
                    re.IGNORECASE,
                ),
            ),
            (
                "EUR",
                MoneyContextType.PENALTY,
                re.compile(
                    rf"\b(?:penalizaci[oó]n de|penalty of)\b[^-\d€$]*(?P<amount>{amount_pattern})\s*(?:€|euros?\b)",
                    re.IGNORECASE,
                ),
            ),
            (
                "USD",
                MoneyContextType.TOTAL,
                re.compile(
                    rf"\btotal\b[^-\d€$]*\$\s*(?P<amount>{amount_pattern})",
                    re.IGNORECASE,
                ),
            ),
            (
                "EUR",
                MoneyContextType.GENERIC,
                re.compile(rf"(?P<amount>{amount_pattern})\s*(?:€|euros?\b)", re.IGNORECASE),
            ),
            (
                "EUR",
                MoneyContextType.GENERIC,
                re.compile(rf"€\s*(?P<amount>{amount_pattern})", re.IGNORECASE),
            ),
            (
                "USD",
                MoneyContextType.GENERIC,
                re.compile(rf"(?P<amount>{amount_pattern})\s*(?:dollars?|usd)\b", re.IGNORECASE),
            ),
            (
                "USD",
                MoneyContextType.GENERIC,
                re.compile(rf"\$\s*(?P<amount>{amount_pattern})", re.IGNORECASE),
            ),
            (
                "PERCENT",
                MoneyContextType.GENERIC,
                re.compile(rf"(?P<amount>-?\d+(?:[.,]\d+)?)\s*%", re.IGNORECASE),
            ),
        ]

    def _normalize_amount_string(self, text: str) -> float:
        """
        Cleans a string representing a number and converts it to a float.
        Example: "1.234,56" -> 1234.56
        Example: "1,234.56" -> 1234.56
        """
        text = text.strip().replace(" ", "")
        if "," in text and "." in text:
            if text.rfind(",") > text.rfind("."):
                cleaned_text = text.replace(".", "").replace(",", ".")
            else:
                cleaned_text = text.replace(",", "")
        elif "." in text:
            parts = text.split(".")
            if len(parts) > 2:
                cleaned_text = "".join(parts)
            elif len(parts) == 2 and len(parts[1]) == 3 and len(parts[0]) >= 1:
                cleaned_text = text.replace(".", "")
            else:
                cleaned_text = text
        elif "," in text:
            parts = text.split(",")
            if len(parts) > 2:
                cleaned_text = "".join(parts)
            elif len(parts) == 2 and len(parts[1]) == 3 and len(parts[0]) >= 1:
                cleaned_text = text.replace(",", "")
            else:
                cleaned_text = text.replace(",", ".")
        else:
            cleaned_text = text

        cleaned_text = re.sub(r"[^-0-9.]", "", cleaned_text)
        return float(cleaned_text)

    async def extract(self, text: str) -> List[ExtractedEntity]:
        """
        Extracts all recognizable money and percentage entities from the input text.
        """
        found_entities: List[ExtractedEntity] = []

        for currency, context, pattern in self.patterns:
            for match in pattern.finditer(text):
                # Check for overlap with already found entities
                is_overlapping = any(
                    max(e.start, match.start()) < min(e.end, match.end())
                    for e in found_entities
                )
                if is_overlapping:
                    continue

                try:
                    amount_str = match.group("amount")
                    normalized_amount = self._normalize_amount_string(amount_str)

                    if currency == "PERCENT":
                        entity = ExtractedPercentage(
                            value=normalized_amount,
                            context=context,
                            text=match.group(0),
                            start=match.start(),
                            end=match.end()
                        )
                    else:
                        entity = ExtractedMoney(
                            amount=normalized_amount,
                            currency=currency,
                            context=context,
                            text=match.group(0),
                            start=match.start(),
                            end=match.end()
                        )
                    found_entities.append(entity)
                except (ValueError, IndexError):
                    # Ignore if normalization or group extraction fails
                    continue
        
        found_entities.sort(key=lambda e: e.start)
        return found_entities
