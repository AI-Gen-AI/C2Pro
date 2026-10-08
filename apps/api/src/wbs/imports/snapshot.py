"""Deterministic hierarchy resolution and the ``wbs-import-snapshot/v1`` digest.

Hierarchy is resolved from EVERY method the source provides (``parent_code``, ``parent_id``,
outline ``level``); when several are present they must describe the same tree. Nothing is ever
repaired silently: a cycle, self-parent, unresolved or ambiguous parent, impossible level jump,
conflicting methods, duplicate source identity or missing name is a BLOCKING error. A WBS code is
not identity: an invalid or duplicated code becomes ``normalized_code = NULL`` with a WARNING (the
raw value stays in the snapshot), unless a parent reference depends on it -- then it is BLOCKING.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Iterable, Mapping
from typing import Any

from src.wbs.domain.digest import DICTIONARY_LIST_KEYS, canonical_json, normalize_dictionary
from src.wbs.domain.governance import (
    GovernanceRuleError,
    validate_control_level,
    validate_decomposition_kind,
)
from src.wbs.imports.contracts import (
    MAX_CODE_CHARS,
    MAX_LEVEL,
    MAX_NAME_CHARS,
    SNAPSHOT_SCHEMA_VERSION,
    Diagnostic,
    HierarchyMethod,
    ImportFormat,
    Severity,
    SnapshotRow,
)
from src.wbs.imports.readers import DICTIONARY_FIELDS, FormulaCell, RawRow

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_LIST_SPLIT = re.compile(r"[\n;]")


def _blocking(code: str, message: str, ref: str | None, field_name: str | None = None) -> Diagnostic:
    return Diagnostic(Severity.BLOCKING_ERROR, code, message, ref, field_name)


def _warning(code: str, message: str, ref: str | None, field_name: str | None = None) -> Diagnostic:
    return Diagnostic(Severity.WARNING, code, message, ref, field_name)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = unicodedata.normalize("NFC", str(value).strip())
    return text or None


def _level(value: Any) -> int | None | str:
    """An outline level (>= 1), None when absent, or "invalid"."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "invalid"
    if isinstance(value, int):
        return value if 1 <= value <= MAX_LEVEL else "invalid"
    text = str(value).strip()
    whole = re.fullmatch(r"([0-9]+)(\.0+)?", text)
    if whole:  # exact integer arithmetic on bounded digits: never float, never an overflow
        digits = whole.group(1).lstrip("0") or "0"
        if len(digits) > len(str(MAX_LEVEL)):
            return "invalid"
        number = int(digits)
        return number if 1 <= number <= MAX_LEVEL else "invalid"
    return "invalid"


def _dictionary(row: RawRow, diagnostics: list[Diagnostic]) -> dict[str, Any] | None:
    raw: dict[str, Any] = {}
    nested = row.values.get("dictionary")
    if isinstance(nested, Mapping):
        raw.update(nested)
    for name in DICTIONARY_FIELDS:
        value = row.values.get(name)
        if value is None:
            continue
        if name in DICTIONARY_LIST_KEYS:
            raw[name] = [part.strip() for part in _LIST_SPLIT.split(str(value)) if part.strip()]
        else:
            raw[name] = str(value).strip()
    if not raw:
        return None
    try:
        return normalize_dictionary(raw)
    except (TypeError, ValueError) as exc:
        diagnostics.append(_warning("DICTIONARY_INVALID", f"WBS dictionary dropped: {exc}", row.source_ref, "dictionary"))
        return None


def resolve_rows(
    raw_rows: list[RawRow], fields: frozenset[str], diagnostics: list[Diagnostic]
) -> tuple[tuple[SnapshotRow, ...], tuple[HierarchyMethod, ...]]:
    methods = tuple(m for m in HierarchyMethod if m.value in fields)
    by_ref: dict[str, RawRow] = {row.source_ref: row for row in raw_rows}
    if len(by_ref) != len(raw_rows):  # pragma: no cover - readers derive refs from unique locations
        diagnostics.append(_blocking("DUPLICATE_SOURCE_IDENTITY", "two rows share a source location", None))

    for row in raw_rows:
        for field_name in sorted(row.formula_fields):
            diagnostics.append(_blocking("FORMULA_NOT_ALLOWED", "formulas are never evaluated in WBS structure or "
                                         "dictionary fields: enter the literal value", row.source_ref, field_name))

    def value(row: RawRow, name: str) -> str | None:
        raw = row.values.get(name)
        return None if isinstance(raw, FormulaCell) else _text(raw)

    # External (source) identifiers: unique, never canonical.
    external: dict[str, list[str]] = {}
    for row in raw_rows:
        if (ext := value(row, "id")) is not None:
            external.setdefault(ext, []).append(row.source_ref)
    for ext, refs in external.items():
        if len(refs) > 1:
            for ref in refs:
                diagnostics.append(_blocking("DUPLICATE_SOURCE_IDENTITY", f"source id {ext!r} is not unique", ref, "id"))

    # Codes: identity-free labels.
    raw_codes: dict[str, list[str]] = {}
    for row in raw_rows:
        if (code := value(row, "code")) is not None:
            raw_codes.setdefault(code, []).append(row.source_ref)

    # Parent per method.
    parents: dict[HierarchyMethod, dict[str, str | None]] = {}
    unresolved: set[str] = set()
    if HierarchyMethod.PARENT_CODE in methods:
        mapping: dict[str, str | None] = {}
        for row in raw_rows:
            parent_code = value(row, "parent_code")
            if parent_code is None:
                mapping[row.source_ref] = None
                continue
            targets = raw_codes.get(parent_code, [])
            if not targets:
                diagnostics.append(_blocking("PARENT_UNRESOLVED", f"parent code {parent_code!r} matches no row",
                                             row.source_ref, "parent_code"))
                unresolved.add(row.source_ref)
            elif len(targets) > 1:
                diagnostics.append(_blocking("PARENT_AMBIGUOUS", f"parent code {parent_code!r} matches {len(targets)} "
                                             "rows: the parent is never guessed", row.source_ref, "parent_code"))
                unresolved.add(row.source_ref)
            elif targets[0] == row.source_ref:
                diagnostics.append(_blocking("SELF_PARENT", "a row cannot be its own parent", row.source_ref,
                                             "parent_code"))
                unresolved.add(row.source_ref)
            else:
                mapping[row.source_ref] = targets[0]
        parents[HierarchyMethod.PARENT_CODE] = mapping
    if HierarchyMethod.PARENT_ID in methods:
        mapping = {}
        for row in raw_rows:
            parent_id = value(row, "parent_id")
            if parent_id is None:
                mapping[row.source_ref] = None
                continue
            targets = external.get(parent_id, [])
            if not targets:
                diagnostics.append(_blocking("PARENT_UNRESOLVED", f"parent id {parent_id!r} matches no row",
                                             row.source_ref, "parent_id"))
                unresolved.add(row.source_ref)
            elif len(targets) > 1:
                diagnostics.append(_blocking("PARENT_AMBIGUOUS", f"parent id {parent_id!r} matches {len(targets)} rows",
                                             row.source_ref, "parent_id"))
                unresolved.add(row.source_ref)
            elif targets[0] == row.source_ref:
                diagnostics.append(_blocking("SELF_PARENT", "a row cannot be its own parent", row.source_ref,
                                             "parent_id"))
                unresolved.add(row.source_ref)
            else:
                mapping[row.source_ref] = targets[0]
        parents[HierarchyMethod.PARENT_ID] = mapping
    levels: dict[str, int] = {}
    if HierarchyMethod.LEVEL in methods:
        mapping = {}
        stack: list[str] = []  # stack[i] = last row seen at level i+1
        broken = False
        for row in raw_rows:
            level = _level(row.values.get("level") if not isinstance(row.values.get("level"), FormulaCell) else None)
            if level is None or level == "invalid":
                code = "LEVEL_MISSING" if level is None else "LEVEL_INVALID"
                diagnostics.append(_blocking(code, "every row needs an integer outline level >= 1", row.source_ref,
                                             "level"))
                unresolved.add(row.source_ref)
                broken = True
                continue
            assert isinstance(level, int)
            levels[row.source_ref] = level
            if broken or level > len(stack) + 1:
                if not broken:
                    diagnostics.append(_blocking("LEVEL_JUMP", f"level {level} has no parent at level {level - 1}",
                                                 row.source_ref, "level"))
                unresolved.add(row.source_ref)
                broken = True
                continue
            del stack[level - 1:]
            mapping[row.source_ref] = stack[-1] if stack else None
            stack.append(row.source_ref)
        parents[HierarchyMethod.LEVEL] = mapping

    resolved: dict[str, str | None] = {}
    for row in raw_rows:
        if row.source_ref in unresolved:
            continue
        answers = {method: parents[method].get(row.source_ref) for method in methods if row.source_ref in parents[method]}
        distinct = set(answers.values())
        if len(distinct) > 1:
            diagnostics.append(_blocking("HIERARCHY_CONFLICT", "parent_code / parent_id / level describe different "
                                         "parents for this row: none is silently preferred", row.source_ref))
            unresolved.add(row.source_ref)
            continue
        if distinct:
            resolved[row.source_ref] = distinct.pop()

    # Cycles (parent references only: an outline cannot form one).
    for ref in list(resolved):
        seen: set[str] = set()
        current: str | None = ref
        while current is not None and current in resolved:
            if current in seen:
                diagnostics.append(_blocking("PARENT_CYCLE", "the parent references form a cycle", ref))
                unresolved.add(ref)
                break
            seen.add(current)
            current = resolved[current]

    # Codes that a parent reference depends on must be unambiguous (already BLOCKING above); any
    # other duplicate or invalid code is dropped from the candidate with a WARNING.
    rows: list[SnapshotRow] = []
    for row in raw_rows:
        name = value(row, "name")
        if name is None:
            if "name" not in row.formula_fields:  # a formula name is already BLOCKING
                diagnostics.append(_blocking("NAME_REQUIRED", "every WBS row needs a name", row.source_ref, "name"))
        elif len(name) > MAX_NAME_CHARS:
            diagnostics.append(_blocking("NAME_TOO_LONG", f"a WBS name is at most {MAX_NAME_CHARS} characters",
                                         row.source_ref, "name"))
        raw_code = value(row, "code")
        normalized_code = raw_code
        if raw_code is not None and (len(raw_code) > MAX_CODE_CHARS or _CONTROL_CHARS.search(raw_code)):
            diagnostics.append(_warning("CODE_INVALID", "invalid WBS code: imported without a code (kept in "
                                        "provenance)", row.source_ref, "code"))
            normalized_code = None
        elif raw_code is not None and len(raw_codes[raw_code]) > 1:
            diagnostics.append(_warning("CODE_DUPLICATE", f"WBS code {raw_code!r} appears {len(raw_codes[raw_code])} "
                                        "times: imported without a code (kept in provenance)", row.source_ref, "code"))
            normalized_code = None
        control_level = value(row, "control_level") or "none"
        try:
            control_level = validate_control_level(control_level).value
        except GovernanceRuleError:
            diagnostics.append(_warning("CONTROL_LEVEL_INVALID", f"unknown control_level {control_level!r} ignored",
                                        row.source_ref, "control_level"))
            control_level = "none"
        decomposition_kind = value(row, "decomposition_kind")
        try:
            decomposition_kind = validate_decomposition_kind(decomposition_kind)
        except GovernanceRuleError:
            diagnostics.append(_warning("DECOMPOSITION_KIND_INVALID", f"decomposition_kind {decomposition_kind!r} "
                                        "ignored", row.source_ref, "decomposition_kind"))
            decomposition_kind = None
        level = levels.get(row.source_ref)
        rows.append(SnapshotRow(
            source_ref=row.source_ref, source_ordinal=row.source_ordinal, name=name or "",
            external_id=value(row, "id"), raw_code=raw_code, normalized_code=normalized_code,
            raw_parent_code=value(row, "parent_code"), parent_external_id=value(row, "parent_id"),
            parent_source_ref=None if row.source_ref in unresolved else resolved.get(row.source_ref),
            outline_level=level, control_level=control_level, decomposition_kind=decomposition_kind,
            dictionary=_dictionary(row, diagnostics),
        ))
    if not raw_rows:
        diagnostics.append(_blocking("EMPTY_IMPORT", "the import has no WBS rows", None))
    return tuple(rows), methods


def sorted_diagnostics(diagnostics: Iterable[Diagnostic], ordinals: Mapping[str, int]) -> tuple[Diagnostic, ...]:
    unique = list(dict.fromkeys(diagnostics))
    return tuple(sorted(unique, key=lambda d: (ordinals.get(d.source_ref or "", 0), d.source_ref or "", d.code,
                                               d.field or "", d.severity.value)))


def build_snapshot(fmt: ImportFormat, sheet: str | None, methods: Iterable[HierarchyMethod],
                   rows: Iterable[SnapshotRow], diagnostics: Iterable[Diagnostic]) -> dict[str, Any]:
    return {
        "schema": SNAPSHOT_SCHEMA_VERSION,
        "format": fmt.value,
        "sheet": sheet,
        "hierarchy_methods": sorted(m.value for m in methods),
        "rows": [row.as_json() for row in rows],
        # Stable diagnostic identities change how the snapshot is interpreted; wording never does.
        "diagnostics": [d.identity() for d in diagnostics],
    }


def snapshot_digest(snapshot: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(dict(snapshot))).hexdigest()
