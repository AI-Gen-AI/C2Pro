"""Frozen contracts of the WBS import (PC-2b.3 #922).

``wbs-import-snapshot/v1`` is the normalized, immutable result of deterministically parsing ONE
document revision with ONE parser identity and ONE parse configuration. Each row keeps its
deterministic source identity (``source_ref`` derived from the immutable source location) --
never its WBS code, name or content, and never an identifier written inside the file (those are
SOURCE identifiers only; C2Pro mints every candidate node id).

Any parser behaviour change that can change a normalized snapshot bumps that parser's version.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

SNAPSHOT_SCHEMA_VERSION = "wbs-import-snapshot/v1"
JSON_IMPORT_CONTRACT = "wbs-import/v1"


class ImportFormat(StrEnum):
    XLSX = "xlsx"
    CSV = "csv"
    JSON = "json"


# Parser identity per format (``wbs-xlsx/v1`` ...). Bump the version on ANY normalization change.
PARSERS: dict[ImportFormat, tuple[str, str]] = {
    ImportFormat.XLSX: ("wbs-xlsx", "v1"),
    ImportFormat.CSV: ("wbs-csv", "v1"),
    ImportFormat.JSON: ("wbs-json", "v1"),
}

FORMAT_BY_EXTENSION: dict[str, ImportFormat] = {".xlsx": ImportFormat.XLSX, ".csv": ImportFormat.CSV,
                                               ".json": ImportFormat.JSON}


class ImportStatus(StrEnum):
    """Describes the deterministic parse only -- it confers no workflow authority."""

    READY = "READY"
    READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
    INVALID = "INVALID"


class Severity(StrEnum):
    WARNING = "WARNING"  # the import stays usable (READY_WITH_WARNINGS)
    BLOCKING_ERROR = "BLOCKING_ERROR"  # the import is INVALID: no candidate can be created from it


class HierarchyMethod(StrEnum):
    PARENT_CODE = "parent_code"
    PARENT_ID = "parent_id"
    LEVEL = "level"


# Bounds for untrusted input.
MAX_IMPORT_BYTES = 10 * 1024 * 1024
MAX_XLSX_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
MAX_XLSX_MEMBERS = 2048
MAX_SHEETS = 64
MAX_ROWS = 5000
MAX_COLUMNS = 64
MAX_CELL_CHARS = 4000
MAX_JSON_DEPTH = 8
MAX_CODE_CHARS = 50
MAX_NAME_CHARS = 255
MAX_LEVEL = 50


@dataclass(frozen=True)
class Diagnostic:
    severity: Severity
    code: str
    message: str
    source_ref: str | None = None
    field: str | None = None

    def identity(self) -> dict[str, Any]:
        """The digest-bound part: stable codes and locations, never the human wording."""
        return {"severity": self.severity.value, "code": self.code, "source_ref": self.source_ref, "field": self.field}

    def as_json(self) -> dict[str, Any]:
        return {**self.identity(), "message": self.message}


@dataclass(frozen=True)
class SnapshotRow:
    source_ref: str
    source_ordinal: int
    name: str
    external_id: str | None = None
    raw_code: str | None = None
    normalized_code: str | None = None
    raw_parent_code: str | None = None
    parent_external_id: str | None = None
    parent_source_ref: str | None = None
    outline_level: int | None = None
    control_level: str = "none"
    decomposition_kind: str | None = None
    dictionary: dict[str, Any] | None = None

    def as_json(self) -> dict[str, Any]:
        return {
            "source_ref": self.source_ref, "source_ordinal": self.source_ordinal, "external_id": self.external_id,
            "raw_code": self.raw_code, "normalized_code": self.normalized_code, "name": self.name,
            "raw_parent_code": self.raw_parent_code, "parent_external_id": self.parent_external_id,
            "parent_source_ref": self.parent_source_ref, "outline_level": self.outline_level,
            "control_level": self.control_level, "decomposition_kind": self.decomposition_kind,
            "dictionary": self.dictionary,
        }


@dataclass(frozen=True)
class ParseResult:
    format: ImportFormat
    parser_id: str
    parser_version: str
    parse_config: dict[str, Any]
    parse_config_digest: str
    sheet: str | None
    hierarchy_methods: tuple[HierarchyMethod, ...]
    rows: tuple[SnapshotRow, ...]
    diagnostics: tuple[Diagnostic, ...]
    snapshot: dict[str, Any] = field(default_factory=dict)
    snapshot_digest: str = ""

    @property
    def status(self) -> ImportStatus:
        if any(d.severity is Severity.BLOCKING_ERROR for d in self.diagnostics):
            return ImportStatus.INVALID
        if self.diagnostics:
            return ImportStatus.READY_WITH_WARNINGS
        return ImportStatus.READY

    @property
    def warning_count(self) -> int:
        return sum(1 for d in self.diagnostics if d.severity is Severity.WARNING)

    @property
    def blocking_count(self) -> int:
        return sum(1 for d in self.diagnostics if d.severity is Severity.BLOCKING_ERROR)


__all__ = [
    "FORMAT_BY_EXTENSION",
    "JSON_IMPORT_CONTRACT",
    "MAX_CELL_CHARS",
    "MAX_CODE_CHARS",
    "MAX_COLUMNS",
    "MAX_IMPORT_BYTES",
    "MAX_JSON_DEPTH",
    "MAX_LEVEL",
    "MAX_NAME_CHARS",
    "MAX_ROWS",
    "MAX_SHEETS",
    "MAX_XLSX_MEMBERS",
    "MAX_XLSX_UNCOMPRESSED_BYTES",
    "PARSERS",
    "SNAPSHOT_SCHEMA_VERSION",
    "Diagnostic",
    "HierarchyMethod",
    "ImportFormat",
    "ImportStatus",
    "ParseResult",
    "Severity",
    "SnapshotRow",
]
