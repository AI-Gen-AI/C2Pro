
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
        # A regex for a typical monetary amount, allowing for negative values,
        # thousands separators (dot or comma), and a decimal separator (comma or dot).
        amount_pattern = r"(-?[\d.,\s]+)"

        # The order of patterns matters. More specific (contextual) patterns should come first.
        self.patterns = [
            # --- Contextual Patterns ---
            ("EUR", MoneyContextType.ADVANCE, re.compile(fr"\b(?:anticipo|advance)[\s:]*{amount_pattern}\s*(?:€|euros)\b", re.IGNORECASE)),
            ("EUR", MoneyContextType.FINAL_PAYMENT, re.compile(fr"\b(?:pago final de|final payment of)\s*{amount_pattern}\s*(?:€|euros)\b", re.IGNORECASE)),
            ("EUR", MoneyContextType.PENALTY, re.compile(fr"\b(?:penalizaci[oó]n de|penalty of)\s*{amount_pattern}\s*(?:€|euros?)\b", re.IGNORECASE)),
            ("USD", MoneyContextType.TOTAL, re.compile(fr"\b(?:total)[\s:]*\$\s*{amount_pattern}\b", re.IGNORECASE)),
            
            # --- Generic Currency Patterns ---
            ("EUR", MoneyContextType.GENERIC, re.compile(fr"\b{amount_pattern}\s*(?:€|euros?)\b", re.IGNORECASE)),
            ("EUR", MoneyContextType.GENERIC, re.compile(fr"\b€\s*{amount_pattern}\b", re.IGNORECASE)),
            ("USD", MoneyContextType.GENERIC, re.compile(fr"\b{amount_pattern}\s*(?:dollars?|usd)\b", re.IGNORECASE)),
            ("USD", MoneyContextType.GENERIC, re.compile(fr"\b\$\s*{amount_pattern}\b", re.IGNORECASE)),
            
            # --- Percentage Pattern ---
            ("PERCENT", MoneyContextType.GENERIC, re.compile(fr"\b({amount_pattern})\s*%\b", re.IGNORECASE)),
        ]

    def _normalize_amount_string(self, text: str) -> float:
        """
        Cleans a string representing a number and converts it to a float.
        Example: "1.234,56" -> 1234.56
        Example: "1,234.56" -> 1234.56
        """
        text = text.strip()
        # If the last separator is a comma, assume it's the decimal point
        if ',' in text and '.' in text:
            if text.rfind(',') > text.rfind('.'):
                # Format is 1.234,56 -> remove dots, replace comma with dot
                cleaned_text = text.replace('.', '').replace(',', '.')
            else:
                # Format is 1,234.56 -> remove commas
                cleaned_text = text.replace(',', '')
        elif ',' in text:
             cleaned_text = text.replace(',', '.') # Assume comma is decimal
        else:
            cleaned_text = text
        
        # Remove any remaining non-numeric characters (except '-' and '.')
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
                    # The amount is captured in the first group of the regex
                    amount_str = match.group(1)
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
