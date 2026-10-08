"""``parse_source``: one immutable revision's bytes -> one deterministic ``wbs-import-snapshot/v1``.

Same bytes + same parser identity + same normalized configuration always give the same snapshot
digest. No network, no clock, no randomness, no model call.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.wbs.imports.config import normalize_parse_config, parse_config_digest
from src.wbs.imports.contracts import (
    MAX_IMPORT_BYTES,
    PARSERS,
    Diagnostic,
    ImportFormat,
    ParseResult,
    Severity,
)
from src.wbs.imports.readers import RawSource, read_csv, read_json, read_xlsx
from src.wbs.imports.snapshot import (
    build_snapshot,
    resolve_rows,
    snapshot_digest,
    sorted_diagnostics,
)


def parse_source(fmt: ImportFormat, data: bytes, raw_config: Mapping[str, Any] | None = None) -> ParseResult:
    config = normalize_parse_config(fmt, raw_config)
    parser_id, parser_version = PARSERS[fmt]
    if len(data) > MAX_IMPORT_BYTES:
        source = RawSource(diagnostics=[Diagnostic(Severity.BLOCKING_ERROR, "FILE_TOO_LARGE",
                                                   f"a WBS import is at most {MAX_IMPORT_BYTES} bytes")])
    elif fmt is ImportFormat.XLSX:
        source = read_xlsx(data, config["sheet"])
    elif fmt is ImportFormat.CSV:
        source = read_csv(data, config["delimiter"])
    else:
        source = read_json(data)
    diagnostics: list[Diagnostic] = list(source.diagnostics)
    readable = not any(d.severity is Severity.BLOCKING_ERROR for d in source.diagnostics) or source.rows
    if readable:
        rows, methods = resolve_rows(source.rows, source.fields, diagnostics)
    else:
        rows, methods = (), ()
    ordinals = {row.source_ref: row.source_ordinal for row in source.rows}
    ordered = sorted_diagnostics(diagnostics, ordinals)
    snapshot = build_snapshot(fmt, source.sheet, methods, rows, ordered)
    return ParseResult(
        format=fmt, parser_id=parser_id, parser_version=parser_version, parse_config=config,
        parse_config_digest=parse_config_digest(fmt, config), sheet=source.sheet, hierarchy_methods=methods,
        rows=rows, diagnostics=ordered, snapshot=snapshot, snapshot_digest=snapshot_digest(snapshot),
    )
