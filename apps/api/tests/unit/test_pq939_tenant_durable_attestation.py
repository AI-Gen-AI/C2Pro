"""Offline safety tests for PQ939 read-only synthetic tenant attestation."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[2] / "scripts" / "pq939_tenant_durable_attestation.py"
SPEC = importlib.util.spec_from_file_location("pq939_tenant_durable_attestation", SOURCE)
assert SPEC and SPEC.loader
attest = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(attest)


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("postgresql://db.example/x", "postgresql+asyncpg://db.example/x"),
        ("postgres://db.example/x", "postgresql+asyncpg://db.example/x"),
        ("postgresql+asyncpg://db.example/x", "postgresql+asyncpg://db.example/x"),
    ],
)
def test_only_postgres_urls_allowed(given: str, expected: str) -> None:
    assert attest._pg_url(given) == expected
    with pytest.raises(attest.AttestationFailure):
        attest._pg_url("sqlite:///dev.db")


def test_catalog_identifier_is_quoted_and_escaped() -> None:
    assert attest._quoted('a"b') == '"a""b"'


def test_runner_temp_restricts_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    runner = tmp_path / "runner"
    runner.mkdir()
    monkeypatch.setenv("RUNNER_TEMP", str(runner))
    assert attest._runner_file(str(runner / "baseline.json")) == runner / "baseline.json"
    with pytest.raises(attest.AttestationFailure, match="OUTSIDE"):
        attest._runner_file(str(tmp_path / "repo" / "baseline.json"))
    with pytest.raises(attest.AttestationFailure, match="OUTSIDE"):
        attest._runner_file(str(runner))
    outside = tmp_path / "external"
    outside.mkdir()
    (runner / "escape").symlink_to(outside, target_is_directory=True)
    with pytest.raises(attest.AttestationFailure, match="OUTSIDE"):
        attest._runner_file(str(runner / "escape" / "baseline.json"))


def test_private_key_exclusive_creation(tmp_path: Path) -> None:
    path = tmp_path / "private" / "key"
    attest._write_private(path, b"test-secret")
    assert path.read_bytes() == b"test-secret"
    assert os.stat(path).st_mode & 0o077 == 0
    with pytest.raises(FileExistsError):
        attest._write_private(path, b"replacement")


def test_missing_protected_preflight_fails_before_connect(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    runner = tmp_path / "runner"
    runner.mkdir()
    monkeypatch.setenv("RUNNER_TEMP", str(runner))
    monkeypatch.setenv("PROD_ACCEPTANCE_EXPECTED_TENANT_ID", "13309a24-8ae9-4c63-a8ec-af1bcd2466a6")
    monkeypatch.delenv("PROD_ACCEPTANCE_DATABASE_URL_READONLY", raising=False)
    monkeypatch.delenv("PROD_ACCEPTANCE_TENANT_PREFLIGHT_VERIFIED", raising=False)
    monkeypatch.setattr(
        "sys.argv",
        [
            "pq939_tenant_durable_attestation",
            "before",
            "--baseline",
            str(runner / "baseline.json"),
            "--key-file",
            str(runner / "key"),
        ],
    )
    assert attest.main() == 2
    captured = capsys.readouterr()
    assert "PROTECTED_TENANT_PREFLIGHT_MISSING" in captured.err
    assert not (runner / "baseline.json").exists()
    assert not (runner / "key").exists()


def test_indirect_project_scopes_are_not_skipped() -> None:
    assert attest._table_scope(False, True) == "project_id"
    assert attest._table_scope(True, True) == "tenant_id"
    assert attest._table_scope(True, False) == "tenant_id"
    with pytest.raises(attest.AttestationFailure, match="UNSCOPED"):
        attest._table_scope(False, False)
    assert {"extractions", "knowledge_graph_nodes", "procurement_bom_items"}.issubset(
        attest.REQUIRED_PROJECT_TABLES
    )


def test_project_fingerprint_joins_scoped_projects() -> None:
    sql = attest._fingerprint_sql(
        "extractions", ["id", "project_id", "data_json"], "project_id"
    )
    assert 't."project_id" IN (SELECT p.id FROM public.projects AS p' in sql
    assert "p.tenant_id = :tenant_id" in sql
    assert 't."data_json"' in sql
    assert "row_to_json(scoped)" in sql
    assert "row_to_json(t)" not in sql


def test_column_level_grants_limit_hashed_projection() -> None:
    columns, missing = attest._selectable_columns(
        [("document_id", True), ("tenant_id", True),
         ("stage", True), ("secret_payload", False)], "tenant_id"
    )
    assert columns == ["document_id", "tenant_id", "stage"]
    assert missing == 1
    sql = attest._fingerprint_sql("document_processing_operations", columns, "tenant_id")
    assert "secret_payload" not in sql
    assert 't."tenant_id" = :tenant_id' in sql
    with pytest.raises(attest.AttestationFailure, match="SCOPE_COLUMN"):
        attest._selectable_columns([("tenant_id", False)], "tenant_id")


def test_all_schema_defined_project_only_rls_tables_are_mandatory() -> None:
    # 20260315000200 + 20260319000300 migrations: missing catalog visibility
    # must fail rather than attest an incomplete, tenant-scoped snapshot.
    assert {
        "extractions",
        "procurement_bom_items",
        "procurement_budget_items",
        "procurement_wbs_items",
        "bom_revisions",
        "knowledge_graph_edges",
        "knowledge_graph_nodes",
        "procurement_plan_snapshots",
        "stakeholder_alerts",
    } == attest.REQUIRED_PROJECT_TABLES


def _complete_synthetic_coverage() -> tuple[
    list[tuple[str, str]], dict[str, tuple[bool, bool]]
]:
    """Offline fixture of allowlisted table names; no production connection."""
    required = attest.REQUIRED_TABLES | attest.REQUIRED_PROJECT_TABLES
    catalog = {
        name: (name not in attest.REQUIRED_PROJECT_TABLES, True)
        for name in required
    }
    scoped = [
        (name, "project_id" if name in attest.REQUIRED_PROJECT_TABLES else "tenant_id")
        for name in sorted(required)
    ]
    return scoped, catalog


def test_schema_coverage_complete_is_not_failed() -> None:
    scoped, catalog = _complete_synthetic_coverage()
    assert attest._coverage_error(scoped, catalog) is None


@pytest.mark.parametrize("missing", ["projects", "procurement_bom_items"])
def test_missing_deployed_mandatory_table_fails_closed(missing: str) -> None:
    scoped, catalog = _complete_synthetic_coverage()
    catalog.pop(missing)
    assert attest._coverage_error(scoped, catalog) == "REQUIRED_TABLE_NOT_DEPLOYED"


@pytest.mark.parametrize("unreadable", ["clauses", "procurement_budget_items"])
def test_required_table_hidden_from_verifier_fails_closed(unreadable: str) -> None:
    scoped, catalog = _complete_synthetic_coverage()
    scoped = [(name, scope) for name, scope in scoped if name != unreadable]
    assert attest._coverage_error(scoped, catalog) == (
        "REQUIRED_TABLE_NOT_VISIBLE_TO_VERIFIER"
    )


def test_required_project_column_missing_fails_closed() -> None:
    scoped, catalog = _complete_synthetic_coverage()
    catalog["extractions"] = (True, False)
    # Real information_schema can still show a table with only tenant_id.
    # The protected catalog must identify the absent project_id first.
    scoped = [(name, scope) for name, scope in scoped if name != "extractions"]
    assert attest._coverage_error(scoped, catalog) == "REQUIRED_PROJECT_COLUMN_MISSING"


def test_required_scope_columns_missing_fails_before_visibility_check() -> None:
    scoped, catalog = _complete_synthetic_coverage()
    catalog["clauses"] = (False, False)
    scoped = [(name, scope) for name, scope in scoped if name != "clauses"]
    assert attest._coverage_error(scoped, catalog) == "REQUIRED_SCOPE_COLUMN_MISSING"


def test_required_project_scope_mismatch_fails_closed() -> None:
    scoped, catalog = _complete_synthetic_coverage()
    scoped = [
        (name, "tenant_id" if name == "extractions" else scope)
        for name, scope in scoped
    ]
    assert attest._coverage_error(scoped, catalog) == "REQUIRED_PROJECT_SCOPE_MISMATCH"


def test_too_many_scoped_tables_fails_even_if_required_coverage_present() -> None:
    scoped, catalog = _complete_synthetic_coverage()
    scoped += [
        (f"nonmandatory_extra_{index}", "tenant_id")
        for index in range(attest.MAX_TABLES + 1)
    ]
    assert attest._coverage_error(scoped, catalog) == "TOO_MANY_SCOPED_TABLES"
