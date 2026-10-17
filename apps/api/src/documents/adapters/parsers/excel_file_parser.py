"""
Excel Parser Adapter.

This adapter provides functionality to parse schedule and budget data from Excel files
using the openpyxl library, encapsulating external library details.
"""

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from numbers import Number
from pathlib import Path
from typing import Any, cast

import openpyxl
from openpyxl.utils.exceptions import InvalidFileException


class ExcelParsingError(Exception):
    """Custom exception for Excel parsing errors."""

    pass


class BudgetRows(list[dict[str, Any]]):
    """TS-COH-BUD-RECON-004: budget line items with optional declared total."""

    def __init__(
        self,
        rows: list[dict[str, Any]] | None = None,
        *,
        stated_total: float | None = None,
    ) -> None:
        super().__init__(rows or [])
        self.stated_total = stated_total


# ---------------------------------------------------------------------------
# Budget category inference (best-effort). Parallels the multi-factor detection
# in coherence/rules_engine/deterministic.py, kept local to avoid a documents ->
# coherence import. Time-priced rows are labor/rental (service); equipment nouns
# are equipment; measured goods are material.
# ---------------------------------------------------------------------------
_TIME_UNIT_TOKENS = frozenset({
    "mes", "meses", "month", "months", "mo", "h", "hr", "hora", "horas",
    "hour", "hours", "hh", "jornada", "jornadas", "dia", "dias", "day", "days",
    "semana", "semanas", "week", "weeks", "ano", "anio", "anios", "year", "years",
})
_LABOR_NAME_TOKENS = (
    "soldador", "montador", "electricista", "ayudante", "peon", "peones",
    "oficial", "operario", "operador", "encargado", "capataz", "ingeniero",
    "tecnico", "jefe", "director", "administrativo", "auxiliar", "jornalero",
    "maquinista", "conductor", "gruista", "mano de obra",
)
_EQUIPMENT_NAME_TOKENS = (
    "bomba", "motor", "variador", "cuadro", "valvula", "grupo", "compresor",
    "generador", "transformador", "ventilador", "equipo", "maquina",
    "arrancador", "caldera", "carretilla",
)
_MATERIAL_UNIT_TOKENS = frozenset({
    "ud", "u", "uds", "unidad", "m", "m2", "m3", "ml", "mm", "cm", "km",
    "kg", "g", "gr", "t", "tn", "l", "lt",
})


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
            raise ExcelParsingError(
                f"An unexpected error occurred during Excel schedule parsing: {e}"
            )
        finally:
            workbook_to_close = locals().get("workbook")
            if workbook_to_close is not None and hasattr(workbook_to_close, "close"):
                workbook_to_close.close()

    @staticmethod
    def _schedule_header_aliases() -> dict[str, set[str]]:
        return {
            "task": {"task", "actividad", "tarea", "activity"},
            "start date": {"start date", "inicio", "comienzo", "fecha inicio"},
            "end date": {"end date", "fin", "termino", "fecha fin"},
            "duration": {"duration", "duracion"},
            "wbs": {"wbs"},
            "predecessors": {"predecessors", "predecesoras"},
        }

    @classmethod
    def _find_schedule_headers(cls, sheet: Any) -> tuple[int | None, list[str]]:
        aliases = cls._schedule_header_aliases()
        required = {"task", "start date", "end date"}

        for row_index, row in enumerate(sheet.iter_rows(values_only=True), start=1):
            canonical_headers = cls._canonicalize_headers(row, aliases)
            if required.issubset(set(canonical_headers)):
                return row_index, canonical_headers

        first_row: Any = getattr(sheet, "__getitem__", lambda _: [])(1)
        fallback_headers = [
            getattr(cell, "value", cell) if cell is not None else "" for cell in first_row
        ]
        fallback_canonical_headers = cls._canonicalize_headers(fallback_headers, aliases)
        if required.issubset(set(fallback_canonical_headers)):
            return 1, fallback_canonical_headers

        return None, []

    async def parse_budget(
        self, file_path: Path, *, include_evidence: bool = False
    ) -> list[dict[str, Any]]:
        """
        Parses budget data from a standard Excel file format.

        Scans the first sheet for a budget header row.
        Expected canonical columns: 'Item', 'Quantity', 'Unit Price', 'Total'.

        Args:
            file_path: The path to the Excel file (.xlsx).
            include_evidence: Include revision-local source locators and raw numeric
                cell provenance for the verified BudgetRowEvidence extraction case.
                False preserves the original budget parser row schema for existing
                consumers; this flag does not itself verify source revision hashes.

        Returns:
            A list of dictionaries, where each dictionary represents a budget line item.

        Raises:
            ExcelParsingError: If the file cannot be opened or does not match the expected format.
        """
        try:
            workbook = openpyxl.load_workbook(file_path, data_only=True)
            sheet = workbook.active
            # In evidence mode, inspect the formula-bearing cells separately.
            # Cached values are NOT proof that Excel recalculated a formula for
            # these immutable bytes. Never record stale cache as trusted amounts.
            formula_workbook = (
                openpyxl.load_workbook(file_path, data_only=False)
                if include_evidence
                else None
            )
            formula_sheet = formula_workbook.active if formula_workbook else None

            header_row_index, headers = self._find_budget_headers(sheet)
            if header_row_index is None:
                expected_headers = ["item", "quantity", "unit price", "total"]
                accepted_aliases = "; ".join(
                    f"{canonical}: {', '.join(sorted(aliases))}"
                    for canonical, aliases in self._budget_header_aliases().items()
                )
                raise ExcelParsingError(
                    "Missing one or more required headers: "
                    f"{', '.join(expected_headers)}. Accepted aliases: {accepted_aliases}"
                )

            if include_evidence:
                # A canonical evidence field must have ONE unambiguous source
                # column. Dict construction would otherwise silently drop one
                # of two columns (e.g. Total Net / Total Gross).
                consumed = {
                    "item", "quantity", "unit price", "total", "unit",
                    "currency", "tax basis", "wbs node id",
                }
                evidence_headers = [h for h in headers if h in consumed]
                duplicate_headers = {
                    h for h in evidence_headers if evidence_headers.count(h) > 1
                }
                if duplicate_headers:
                    raise ExcelParsingError(
                        "Duplicate canonical budget evidence columns: "
                        + ", ".join(sorted(duplicate_headers))
                    )

            budget_data: BudgetRows = BudgetRows()
            for row_index, row in enumerate(
                sheet.iter_rows(min_row=header_row_index + 1, values_only=True),
                start=header_row_index + 1,
            ):
                row_data = dict(zip(headers, row, strict=False))
                if include_evidence:
                    # A verified source hash attests bytes, NOT formula evaluation.
                    # Inspect all consumed evidence fields, not only numeric cells.
                    # Check before empty-row/subtotal skips: cached formulas may be
                    # None under data_only=True and otherwise vanish silently.
                    assert formula_sheet is not None
                    evidence_columns = {
                        "item", "quantity", "unit price", "total", "unit",
                        "currency", "tax basis", "wbs node id",
                    }
                    for column_index, column_name in enumerate(headers, start=1):
                        if column_name not in evidence_columns:
                            continue
                        if formula_sheet.cell(row=row_index, column=column_index).data_type == "f":
                            raise ExcelParsingError(
                                "Unverified formula-derived budget evidence at "
                                f"{sheet.title}!{row_index} ({column_name}); "
                                "source formula requires separately attested evaluation"
                            )
                if not any(row_data.values()):
                    continue
                stated_total = self._extract_declared_total(row_data)
                if stated_total is not None:
                    budget_data.stated_total = stated_total
                    continue
                quantity: float | Decimal | None
                unit_price: float | Decimal | None
                total: float | Decimal | None
                if include_evidence:
                    # The column currency is the only authoritative row
                    # denomination. A numeric cell's optional currency symbol
                    # must agree with it; stripping it first could turn $100
                    # into seemingly verified EUR 100, or hide EUR 100 USD.
                    row_currency = row_data.get("currency")
                    for monetary_field in ("unit price", "total"):
                        assert formula_sheet is not None
                        column_index = headers.index(monetary_field) + 1
                        number_format = formula_sheet.cell(
                            row=row_index, column=column_index
                        ).number_format
                        self._require_budget_currency_consistency(
                            row_data.get(monetary_field),
                            row_currency,
                            locator=f"{sheet.title}!{row_index} ({monetary_field})",
                            number_format=number_format,
                        )
                    # Evidence MUST use original cell values, not the lossy
                    # float-normalization used by the legacy analysis parser.
                    quantity = self._coerce_budget_decimal(row_data.get("quantity"))
                    unit_price = self._coerce_budget_decimal(row_data.get("unit price"))
                    total = self._coerce_budget_decimal(row_data.get("total"))
                else:
                    quantity = self._coerce_budget_number(row_data.get("quantity"))
                    unit_price = self._coerce_budget_number(row_data.get("unit price"))
                    total = self._coerce_budget_number(row_data.get("total"))
                # Skip structural chapter/section subtotal rows. In a hierarchical
                # budget (presupuesto por capítulos) chapters carry a rolled-up total
                # with no quantity or unit price; emitting them as line items would
                # double-count against their own leaf partidas. A genuine line item
                # has a measured quantity and/or a unit price.
                if quantity is None and unit_price is None:
                    continue
                unit_raw = row_data.get("unit")
                unit_value = (
                    str(unit_raw).strip()
                    if unit_raw is not None and str(unit_raw).strip()
                    else None
                )
                budget_row = {
                    "item": row_data.get("item"),
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "total": total,
                    "unit": unit_value,
                    "category": self._infer_budget_category(
                        row_data.get("item"), unit_value
                    ),
                }
                if include_evidence:
                    budget_row.update(
                        {
                            "currency": row_data.get("currency"),
                            "tax_basis": row_data.get("tax basis"),
                            "wbs_node_id": row_data.get("wbs node id"),
                            "source_locator": f"{sheet.title}!{row_index}",
                            "numeric_provenance": {
                                field: repr(row_data.get(field))
                                for field in ("quantity", "unit price", "total")
                            },
                        }
                    )
                budget_data.append(budget_row)
            return budget_data

        except ExcelParsingError:
            raise
        except (InvalidFileException, FileNotFoundError) as e:
            raise ExcelParsingError(f"Failed to open or read Excel file: {e}")
        except Exception as e:
            raise ExcelParsingError(
                f"An unexpected error occurred during Excel budget parsing: {e}"
            )
        finally:
            workbook_to_close = locals().get("workbook")
            if workbook_to_close is not None and hasattr(workbook_to_close, "close"):
                workbook_to_close.close()
            formula_to_close = locals().get("formula_workbook")
            if formula_to_close is not None and hasattr(formula_to_close, "close"):
                formula_to_close.close()

    @staticmethod
    def _budget_header_aliases() -> dict[str, set[str]]:
        return {
            "item": {
                "item",
                "partida",
                "descripción",
                "descripcion",
                "concepto",
                "código",
                "codigo",
                "capítulo",
                "capitulo",
            },
            "quantity": {
                "quantity",
                "cantidad",
                "medición",
                "medicion",
                "cant",
                "cant.",
                "uds",
                "ud",
                "unidades",
            },
            "unit price": {
                "unit price",
                "precio unitario",
                "precio",
                "p. unitario",
                "precio ud",
                "precio/ud",
                "importe unitario",
                "coste unitario",
            },
            "total": {
                "total",
                "importe",
                "importe total",
                "total partida",
                "subtotal",
                "coste",
            },
            # Optional unit-of-measure column (not in `required`). Kept distinct
            # from `quantity` ("ud"/"uds"/"unidades") and `unit price` ("precio
            # unitario"); most-specific-alias-wins keeps "PRECIO UNIT." as price.
            "unit": {
                "unit",
                "unidad",
                "u.m.",
                "u. m.",
                "uom",
                "medida",
                "unidad de medida",
            },
            "currency": {"currency", "moneda", "divisa"},
            "tax basis": {"tax basis", "base fiscal", "impuestos", "tax"},
            "wbs node id": {"wbs node id", "wbs id", "id wbs"},
        }

    @classmethod
    def _infer_budget_category(cls, name: Any, unit: str | None) -> str | None:
        """Best-effort BOM category (a BOMCategory value) from unit + item name.

        Time-priced rows (``mes``, ``mes/h``, ``día``, ``h``) and personnel names
        are labor/rental -> ``"service"``; equipment nouns -> ``"equipment"``;
        measured goods -> ``"material"``. Returns ``None`` when undecidable (e.g.
        ``"gl"`` lump-sum, ``"%"`` overhead). Heuristic; no external dependency.
        """
        unit_tokens = set(cls._normalize_header(unit).split()) if unit else set()
        name_norm = cls._normalize_header(name)
        if unit_tokens & _TIME_UNIT_TOKENS or any(
            kw in name_norm for kw in _LABOR_NAME_TOKENS
        ):
            return "service"
        if any(kw in name_norm for kw in _EQUIPMENT_NAME_TOKENS):
            return "equipment"
        if unit_tokens & _MATERIAL_UNIT_TOKENS:
            return "material"
        return None

    @classmethod
    def _find_budget_headers(cls, sheet: Any) -> tuple[int | None, list[str]]:
        aliases = cls._budget_header_aliases()
        required = {"item", "quantity", "unit price", "total"}

        for row_index, row in enumerate(sheet.iter_rows(values_only=True), start=1):
            canonical_headers = cls._canonicalize_headers(row, aliases)
            if required.issubset(set(canonical_headers)):
                return row_index, canonical_headers

        first_row: Any = getattr(sheet, "__getitem__", lambda _: [])(1)
        fallback_headers = [
            getattr(cell, "value", cell) if cell is not None else "" for cell in first_row
        ]
        fallback_canonical_headers = cls._canonicalize_headers(fallback_headers, aliases)
        if required.issubset(set(fallback_canonical_headers)):
            return 1, fallback_canonical_headers

        return None, []

    @staticmethod
    def _normalize_header(value: Any) -> str:
        """Normalize a header cell for tolerant matching.

        Lowercases, strips accents, drops parenthetical qualifiers (e.g. ``(€)``,
        ``(Semana)``, ``(días)``), and reduces any punctuation/currency/symbols to
        single spaces. This lets real-world headers like ``PRECIO UNIT. (€)`` or
        ``Inicio (Semana)`` match their canonical aliases (``precio``, ``inicio``).
        """
        if value is None:
            return ""
        text = unicodedata.normalize("NFKD", str(value))
        text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
        text = re.sub(r"\([^)]*\)", " ", text)  # drop parenthetical qualifiers
        text = re.sub(r"[^a-z0-9]+", " ", text)  # currency/punctuation -> space
        return " ".join(text.split())

    @classmethod
    def _match_canonical(cls, header_norm: str, aliases: dict[str, set[str]]) -> str | None:
        """Return the canonical column for a normalized header, or ``None``.

        A header matches an alias when every token of the (normalized) alias is
        present in the header's tokens (subset match), so ``importe (€)`` matches
        ``importe`` and ``precio unit. (€)`` matches ``precio``. When several
        aliases match, the most specific one wins (more tokens, then longer),
        which keeps ``importe unitario`` (unit price) from being read as ``importe``
        (total). Iteration is sorted so ties resolve deterministically.
        """
        if not header_norm:
            return None
        header_tokens = set(header_norm.split())
        best_score: tuple[int, int] = (0, 0)
        best_canonical: str | None = None
        for canonical, accepted in aliases.items():
            for alias in sorted(accepted):
                alias_tokens = cls._normalize_header(alias).split()
                if alias_tokens and all(tok in header_tokens for tok in alias_tokens):
                    score = (len(alias_tokens), len("".join(alias_tokens)))
                    if score > best_score:
                        best_score = score
                        best_canonical = canonical
        return best_canonical

    @classmethod
    def _canonicalize_headers(cls, row: Any, aliases: dict[str, set[str]]) -> list[str]:
        canonical: list[str] = []
        for value in row:
            header_norm = cls._normalize_header(value)
            match = cls._match_canonical(header_norm, aliases)
            canonical.append(match if match is not None else header_norm)
        return canonical

    @staticmethod
    def _budget_numeric_format_sections(value: Any, number_format: str) -> str:
        """Discard only Excel's fourth, text-only format section for numeric cells.

        Split at actual section delimiters, not semicolons inside quoted
        literals, escaped sequences or bracket directives.
        """
        if not isinstance(value, (int, float, Decimal)):
            return number_format
        sections: list[str] = []
        current: list[str] = []
        quoted = False
        escaped = False
        bracket_depth = 0
        for char in number_format:
            if escaped:
                current.append(char)
                escaped = False
            elif char == "\\" and not quoted:
                current.append(char)
                escaped = True
            elif char == '"':
                current.append(char)
                quoted = not quoted
            elif char == "[" and not quoted:
                current.append(char)
                bracket_depth += 1
            elif char == "]" and not quoted and bracket_depth:
                current.append(char)
                bracket_depth -= 1
            elif char == ";" and not quoted and not bracket_depth:
                sections.append("".join(current))
                current = []
            else:
                current.append(char)
        sections.append("".join(current))
        return ";".join(sections[:3]) if len(sections) == 4 else number_format

    @staticmethod
    def _require_budget_currency_consistency(
        value: Any, currency: Any, *, locator: str, number_format: str = ""
    ) -> None:
        """Reject conflicting currency markers in both source text and XLSX formats.

        A source SHA authenticates Excel number formats as well as stored values.
        Generic locale codes (such as [$-409]) are not currency denominations.
        """
        number_format = ExcelFileParser._budget_numeric_format_sections(
            value, number_format
        )
        currency_pattern = r"(?<![A-Za-z])(?:EUR|USD|GBP)(?![A-Za-z])|[€$£]"
        markers = re.findall(
            currency_pattern, value if isinstance(value, str) else "", flags=re.I
        )
        # Localized currency formats include the currency marker inside a
        # bracket directive. Locale-only directives contain no currency marker.
        for directive in re.findall(r"\[\$([^\]]*)\]", number_format):
            symbol = directive.split("-", 1)[0].strip()
            if symbol:
                found = re.findall(currency_pattern, symbol, flags=re.I)
                if not found:
                    raise ExcelParsingError(
                        f"Unsupported budget currency format marker at {locator}"
                    )
                markers.extend(found)
        remaining_format = re.sub(r"\[\$[^\]]*\]", "", number_format)
        # Unicode currency symbols outside our supported EUR/USD/GBP scope
        # must never be mistaken for a currency-free numeric format.
        if any(
            unicodedata.category(char) == "Sc" and char not in "€$£"
            for char in number_format
        ):
            raise ExcelParsingError(
                f"Unsupported budget currency format marker at {locator}"
            )
        markers.extend(re.findall(currency_pattern, remaining_format, flags=re.I))
        if not markers:
            return
        codes = {"€": "EUR", "$": "USD", "£": "GBP"}
        identified = [codes.get(token, token.upper()) for token in markers]
        declared = str(currency).strip().upper() if currency is not None else ""
        if not declared or any(token != declared for token in identified):
            raise ExcelParsingError(
                f"Budget currency marker conflicts with row currency at {locator}"
            )

    @staticmethod
    def _coerce_budget_decimal(value: Any) -> Decimal | None:
        """Parse a source cell as Decimal without any intermediate float conversion.

        Applies the established ES/EN separator heuristic while retaining all
        decimal digits from text cells; an XLSX binary-float cell has only the
        precision already encoded by the original workbook.
        """
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, (int, float, Decimal)):
            try:
                decimal = Decimal(str(value))
                return decimal if decimal.is_finite() else None
            except InvalidOperation:
                return None
        if not isinstance(value, str):
            return None
        source = value.strip()
        if not source:
            return None
        # Accept ONLY explicit currency labels, not arbitrary text. Deleting
        # unsupported characters silently turned "1e3" into "13".
        source = re.sub(r"\s*(?:EUR|USD|GBP|€|\$|£)\s*$", "", source, flags=re.I).strip()
        source = re.sub(r"^(?:EUR|USD|GBP|€|\$|£)\s*", "", source, flags=re.I).strip()
        accounting_negative = source.startswith("(") and source.endswith(")")
        if accounting_negative:
            source = source[1:-1].strip()
        if not re.fullmatch(r"-?[0-9]+(?:[.,][0-9]+)*", source):
            raise ExcelParsingError("Unsupported verified budget numeric syntax")
        if accounting_negative and source.startswith("-"):
            raise ExcelParsingError("Ambiguous accounting negative")
        if "," in source and "." in source:
            # Both separators require explicit thousands grouping to
            # disambiguate the decimal separator.
            if re.fullmatch(r"-?[0-9]{1,3}(?:\.[0-9]{3})+,[0-9]{1,}", source):
                normalized = source.replace(".", "").replace(",", ".")
            elif re.fullmatch(r"-?[0-9]{1,3}(?:,[0-9]{3})+\.[0-9]{1,}", source):
                normalized = source.replace(",", "")
            else:
                raise ExcelParsingError("Ambiguous mixed budget numeric separators")
        elif "," in source:
            if source.count(",") > 1:
                if not re.fullmatch(r"-?[0-9]{1,3}(?:,[0-9]{3}){2,}", source):
                    raise ExcelParsingError("Ambiguous budget number grouping")
                normalized = source.replace(",", "")
            else:
                _, fractional = source.split(",", 1)
                if len(fractional) >= 3:
                    raise ExcelParsingError(
                        "Ambiguous single-comma decimal in verified budget evidence"
                    )
                normalized = source.replace(",", ".")
        elif "." in source:
            if source.count(".") > 1:
                if not re.fullmatch(r"-?[0-9]{1,3}(?:\.[0-9]{3}){2,}", source):
                    raise ExcelParsingError("Ambiguous budget number grouping")
                normalized = source.replace(".", "")
            else:
                _, fractional = source.split(".", 1)
                if len(fractional) == 3:
                    raise ExcelParsingError(
                        "Ambiguous single-dot decimal in verified budget evidence"
                    )
                normalized = source
        else:
            normalized = source
        if accounting_negative:
            normalized = "-" + normalized
        try:
            decimal = Decimal(normalized)
            return decimal if decimal.is_finite() else None
        except InvalidOperation:
            return None

    @staticmethod
    def _coerce_budget_number(value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, Number):
            return float(cast(float, value))
        if not isinstance(value, str):
            return None

        text = value.strip()
        if not text:
            return None

        cleaned = re.sub(r"[^0-9,.\-]", "", text)
        if cleaned in {"", "-", ".", ","}:
            return None

        if "," in cleaned and "." in cleaned:
            if cleaned.rfind(",") > cleaned.rfind("."):
                normalized = cleaned.replace(".", "").replace(",", ".")
            else:
                normalized = cleaned.replace(",", "")
        elif "," in cleaned:
            left, right = cleaned.rsplit(",", 1)
            if len(right) in {1, 2}:
                normalized = f"{left.replace(',', '')}.{right}"
            else:
                normalized = cleaned.replace(",", "")
        else:
            normalized = cleaned

        try:
            return float(normalized)
        except ValueError:
            return None

    @classmethod
    def _extract_declared_total(cls, row_data: dict[str, Any]) -> float | None:
        item = row_data.get("item")
        quantity = row_data.get("quantity")
        unit_price = row_data.get("unit price")
        total = cls._coerce_budget_number(row_data.get("total"))
        if total is None or quantity not in (None, "") or unit_price not in (None, ""):
            return None
        if not isinstance(item, str):
            return None
        label = item.strip().lower()
        declared_total_labels = (
            "total presupuesto",
            "total general",
            "total licitacion",
            "total licitación",
            "presupuesto total",
            "grand total",
            "declared total",
        )
        if label == "total" or any(marker in label for marker in declared_total_labels):
            return total
        return None
