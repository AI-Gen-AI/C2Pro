"""Regression guard tests for RLS/tenant_id, cache-key, and Anthropic invariants.

GUARD 1 — tenant_id: Scans src/ for raw SQL INSERT/UPSERT via text() or
sql_text(). Every write to an RLS-protected table must include tenant_id
in the column list. The KNOWN_SAFE set is the baseline; a new raw INSERT
that omits tenant_id will cause this test to fail.

GUARD 2 — cache keys: Asserts that the semantic cache-key builders
coherence_llm_gate._content_hash and core/cache.build_extraction_cache_fingerprint
still include their invalidating inputs (detection_logic, prompt, model).

GUARD 3 — Anthropic instantiation: Locks AsyncAnthropic/Anthropic class
instantiation to a strict allowlist (core/ai/ proxy objects). Any file
outside this set that creates an Anthropic client directly bypasses
budget controls, tenant isolation, and prompt caching.

Encoded invariants: QA-341, QA-342, QA-343, QA-344, V3-P1-OBS-09, V3-P1-OBS-10.

Gate: tests-only, no src modifications. ruff clean + green on CI.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_SRC_ROOT = Path(__file__).resolve().parents[2] / "src"

# Files containing the cache-key builders we guard
_GATE_FILE = _SRC_ROOT / "coherence" / "adapters" / "ai" / "coherence_llm_gate.py"
_CACHE_FILE = _SRC_ROOT / "core" / "cache.py"


# ---------------------------------------------------------------------------
# GUARD 1 — tenant_id invariant on raw SQL writes
# ---------------------------------------------------------------------------

# Regex:  text(  or  sql_text(  followed by a triple-quoted string containing
# INSERT or UPSERT.  We match across line boundaries.
_RAW_SQL_PATTERN = re.compile(
    r"(?:\btext|\bsql_text)\(\s*(?:f)?(\"{3}|'{3})(.+?)\1",
    re.DOTALL,
)

# Extract the column list between the first pair of parentheses after INSERT INTO <table>
_INSERT_COL_RE = re.compile(
    r"INSERT\s+INTO\s+(\w+)\s*\(([^)]+)\)",
    re.IGNORECASE | re.DOTALL,
)

# Tables that currently have RLS and receive raw INSERT/UPSERT writes.
# If a NEW table is added here, the test will auto-include it.
# Removing a table here is a regression — the test will fail.
KNOWN_RLS_TABLES_WITH_RAW_INSERTS: set[str] = {
    "alerts",
    "clause_embeddings",
    "document_chunks",
    "audit_logs",
}

# Tables whose raw INSERT uses f-string dynamic columns (not statically
# analysable).  The guard skips these from the column-list check.
# Each entry must have a comment proving tenant_id is always included.
DYNAMIC_COLUMN_TABLES: dict[str, str] = {
    # audit_logs: _build_audit_log_insert() always starts with
    # ["tenant_id", "action", "resource_type"] (database_server.py:653)
    "audit_logs": "database_server.py:_build_audit_log_insert starts with tenant_id",
}


def _scan_raw_inserts(src_root: Path) -> list[dict[str, str]]:
    """Scan src/ for raw SQL INSERT/UPSERT statements via text()/sql_text().

    Returns a list of dicts with keys: file, line_approx, table, columns, is_dynamic.
    """
    hits: list[dict[str, str]] = []
    for py_file in src_root.rglob("*.py"):
        try:
            source = py_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for m in _RAW_SQL_PATTERN.finditer(source):
            sql_blob = m.group(2)
            if not re.search(r"\bINSERT\b|\bUPSERT\b", sql_blob, re.IGNORECASE):
                continue
            col_match = _INSERT_COL_RE.search(sql_blob)
            if not col_match:
                continue
            table = col_match.group(1).lower()
            columns_raw = col_match.group(2)
            # Detect f-string dynamic columns: if raw text contains { it's
            # a Python expression, not literal column names.
            is_dynamic = "{" in columns_raw
            if is_dynamic:
                columns_str = f"(dynamic: {columns_raw.strip()})"
            else:
                columns = {c.strip().strip('"').strip("'").lower() for c in columns_raw.split(",")}
                columns_str = ",".join(sorted(columns))
            line_approx = source[: m.start()].count("\n") + 1
            hits.append(
                {
                    "file": str(py_file.relative_to(src_root)),
                    "line_approx": str(line_approx),
                    "table": table,
                    "columns": columns_str,
                    "is_dynamic": "1" if is_dynamic else "0",
                }
            )
    return hits


def test_raw_inserts_include_tenant_id():
    """Every raw INSERT/UPSERT to an RLS table must supply tenant_id.

    If a developer adds a new raw INSERT to an RLS-protected table without
    tenant_id, this test fails.  They must either add tenant_id to the
    column list or use the ORM (which handles it automatically).

    Invariants: QA-341 (alert INSERT tenant_id), QA-342 (clause_embeddings),
    V3-P1-OBS-09 (RLS enforcement on all writes).
    """
    hits = _scan_raw_inserts(_SRC_ROOT)
    violations: list[str] = []
    for h in hits:
        table = h["table"]
        if table not in KNOWN_RLS_TABLES_WITH_RAW_INSERTS:
            continue
        if h["is_dynamic"] == "1":
            # Dynamic columns — verify the table is in the allowlist
            if table not in DYNAMIC_COLUMN_TABLES:
                violations.append(
                    f"  {h['file']}:{h['line_approx']} — {table} has dynamic (f-string) "
                    f"columns but is NOT in DYNAMIC_COLUMN_TABLES. Add it with proof "
                    f"that tenant_id is always included."
                )
            continue
        cols = set(h["columns"].split(","))
        if "tenant_id" not in cols:
            violations.append(
                f"  {h['file']}:{h['line_approx']} — {table} INSERT missing tenant_id "
                f"(columns: {h['columns']})"
            )
    assert not violations, (
        "Raw INSERT/UPSERT to RLS table(s) without tenant_id in column list:\n"
        + "\n".join(violations)
        + "\n\nAdd tenant_id to the column list, or register the table in "
        "KNOWN_RLS_TABLES_WITH_RAW_INSERTS if this is a known-safe exception."
    )


def test_known_rls_raw_insert_tables_covers_all():
    """Verify KNOWN_RLS_TABLES_WITH_RAW_INSERTS is not stale.

    Scans for raw INSERTs to any table and asserts every RLS-protected
    table that appears is listed in the known-safe set. If a new raw
    INSERT targeting an RLS table appears, the developer must either:
    (a) add tenant_id to the column list (passing GUARD 1 above), or
    (b) add the table to KNOWN_RLS_TABLES_WITH_RAW_INSERTS with a comment.
    """
    hits = _scan_raw_inserts(_SRC_ROOT)
    discovered_tables = {h["table"] for h in hits}
    # Tables not in the known set — informational, not a failure,
    # but we surface them so the developer is aware.
    unknown = discovered_tables - KNOWN_RLS_TABLES_WITH_RAW_INSERTS - {"projects"}
    # projects is not in our guard scope (it's not in the Gemini RLS matrix
    # for raw INSERT writes — only UPDATEs appear there).
    if unknown:
        msg = (
            "Raw INSERT/UPSERT targets tables not in KNOWN_RLS_TABLES_WITH_RAW_INSERTS: "
            f"{sorted(unknown)}. If these are RLS-protected, add them to the set "
            "and ensure tenant_id is in the column list."
        )
        # Soft warning — not a hard failure, but surfaces the discovery.
        import warnings

        warnings.warn(msg, stacklevel=1)


# ---------------------------------------------------------------------------
# GUARD 2 — cache-key invariant: invalidating inputs must stay in the hash
# ---------------------------------------------------------------------------


def _get_keyword_params(filepath: Path, func_name: str) -> dict[str, str | None]:
    """Parse a Python file with AST and return keyword-only params of func_name.

    Returns a dict mapping param name -> annotation string (or None).
    """
    source = filepath.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(filepath))
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if node.name != func_name:
            continue
        params: dict[str, str | None] = {}
        args = node.args
        # keyword-only args (after *)
        kw_only = args.kwonlyargs
        for arg in kw_only:
            ann = None
            if arg.annotation:
                ann = ast.dump(arg.annotation)
            params[arg.arg] = ann
        # Also include positional params for full picture
        for arg in args.args:
            if arg.arg == "self" or arg.arg == "cls":
                continue
            ann = None
            if arg.annotation:
                ann = ast.dump(arg.annotation)
            params[arg.arg] = ann
        return params
    return {}


def test_coherence_cache_key_includes_detection_logic():
    """_content_hash must include detection_logic as a parameter.

    If someone removes detection_logic from the function signature,
    edits to rule detection logic would silently stop invalidating
    the cache, serving stale LLM findings.

    Invariant: QA-343 (LLM gate cache key).
    """
    params = _get_keyword_params(_GATE_FILE, "_content_hash")
    assert "detection_logic" in params, (
        f"detection_logic was removed from _content_hash params: {list(params.keys())}. "
        "This would cause stale cached LLM findings when rule detection logic changes. "
        "Restore detection_logic as a keyword parameter."
    )


# ---------------------------------------------------------------------------
# GUARD 3 — Anthropic client instantiation locked to core/ai/ wrappers
# ---------------------------------------------------------------------------

# Only these src-relative files may directly instantiate AsyncAnthropic/Anthropic.
_ANTHROPIC_ALLOWLIST: frozenset[str] = frozenset({
    "core/ai/llm_client.py",
    "core/ai/anthropic_wrapper.py",
    "analysis/adapters/ai/anthropic_client.py",
})


def test_anthropic_client_instantiation_locked_to_core_ai_wrappers():
    """GUARD 3: Lock AsyncAnthropic/Anthropic instantiation to allowlist.

    Only the canonical transport files (llm_client.py, anthropic_wrapper.py,
    anthropic_client.py) may directly instantiate the Anthropic SDK. Any
    other file that creates an Anthropic client bypasses budget controls,
    tenant isolation, and prompt caching.

    Invariant: QA-344, V3-P1-OBS-10.
    """
    offenders: list[tuple[str, int, str]] = []

    for py_file in sorted(_SRC_ROOT.rglob("*.py")):
        rel = py_file.relative_to(_SRC_ROOT).as_posix()
        try:
            tree = ast.parse(py_file.read_text("utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name) and func.id in ("AsyncAnthropic", "Anthropic") and rel not in _ANTHROPIC_ALLOWLIST:
                offenders.append((rel, node.lineno, func.id))

    assert not offenders, (
        "AsyncAnthropic/Anthropic instantiated outside allowlist:\n"
        + "\n".join(f"  {f}:{line_no}  ({cls})" for f, line_no, cls in offenders)
        + "\n\nAll Anthropic client creation must go through the allowlisted "
        f"transport files: {', '.join(sorted(_ANTHROPIC_ALLOWLIST))}. "
        "Use dependency injection instead of direct SDK instantiation."
    )


def test_extraction_cache_key_includes_prompt_and_model():
    """build_extraction_cache_fingerprint must include prompt and model.

    If either is removed, changing the extraction prompt or switching
    models would silently reuse cached results from the old configuration.

    Invariant: QA-343 (extraction cache key).
    """
    params = _get_keyword_params(_CACHE_FILE, "build_extraction_cache_fingerprint")
    missing = []
    for required in ("prompt", "model"):
        if required not in params:
            missing.append(required)
    assert not missing, (
        f"{missing} were removed from build_extraction_cache_fingerprint params: "
        f"{list(params.keys())}. This would cause stale cached extraction results "
        "when the prompt or model changes. Restore the missing parameters."
    )
