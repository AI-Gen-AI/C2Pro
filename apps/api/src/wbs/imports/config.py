"""Parse configuration per import format: strict, fully defaulted, digestible.

The normalized configuration (every key present) is what the import identity and its digest
bind, so ``{}`` and ``{"sheet": null}`` are the same configuration.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from src.wbs.domain.digest import canonical_json
from src.wbs.imports.contracts import ImportFormat

CSV_DELIMITERS = (",", ";", "\t")
_MAX_SHEET_NAME = 255


class ImportConfigError(ValueError):
    """The parse configuration is not valid for this format."""


def normalize_parse_config(fmt: ImportFormat, raw: Mapping[str, Any] | None) -> dict[str, Any]:
    config = dict(raw or {})
    if fmt is ImportFormat.XLSX:
        allowed: dict[str, Any] = {"sheet": None}
    elif fmt is ImportFormat.CSV:
        allowed = {"delimiter": None}
    else:
        allowed = {}
    unknown = sorted(set(config) - set(allowed))
    if unknown:
        raise ImportConfigError(f"unsupported parse_config keys for {fmt.value}: {unknown}")
    out = {**allowed, **config}
    if fmt is ImportFormat.XLSX:
        sheet = out["sheet"]
        if sheet is not None and (not isinstance(sheet, str) or not sheet.strip() or len(sheet) > _MAX_SHEET_NAME):
            raise ImportConfigError("parse_config.sheet must be a non-empty sheet name or null")
    if fmt is ImportFormat.CSV and out["delimiter"] is not None and out["delimiter"] not in CSV_DELIMITERS:
        raise ImportConfigError("parse_config.delimiter must be one of ',', ';', TAB or null (detect)")
    return out


def parse_config_digest(fmt: ImportFormat, config: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical_json({"format": fmt.value, "config": dict(config)})).hexdigest()
