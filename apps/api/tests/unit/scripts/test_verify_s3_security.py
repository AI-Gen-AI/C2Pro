"""S3 security hardening regression. Place in apps/api/tests/unit/scripts/.

One fixed output target, never caller-controlled; no symlink escapes; identical
report schema. No worktree, real DB, provider, UAT or credentials required.
"""
import asyncio
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

# In the repo: apps/api/tests/unit/scripts/ -> apps/api/scripts/.
# A local standalone copy has scripts in the parent test directory instead.
SCRIPT_DIR = Path(__file__).resolve().parents[3] / "scripts"
if not SCRIPT_DIR.is_dir():
    SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

import verify_s3_technical_health_pg as s3  # noqa: E402


@pytest.fixture
def apps_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "apps"
    root.mkdir()
    (root / "web").mkdir()
    monkeypatch.setattr(s3, "_TRUSTED_APPS_ROOT", root)
    return root


def test_fixed_existing_workflow_output_is_accepted() -> None:
    s3._require_fixed_output_argument(
        Path("../web/playwright-report/s3-technical-health-postgres.json")
    )


@pytest.mark.parametrize("bad", [
    "/tmp/exfiltrate.json",
    "../../../../tmp/exfiltrate.json",
    "../web/playwright-report/../exfiltrate.json",
    "../web/playwright-report/not-the-s3-report.json",
    "./s3-technical-health-postgres.json",
    r"C:\\tmp\\exfiltrate.json",
])
def test_arbitrary_absolute_or_traversal_output_rejected(bad: str) -> None:
    bad_path = Path(bad)
    with pytest.raises(ValueError, match="fixed to the authorized"):
        s3._require_fixed_output_argument(bad_path)


def test_persisted_json_matches_contract_and_is_atomic(apps_root: Path) -> None:
    report = {
        "gate": "S3-TECHNICAL-SOURCE-HEALTH", "result": "PASS",
        "technical_requirement_sections": ["4.1.2", "4.2"],
        "technical_assessment": "UNVERIFIED", "technical_score": None,
        "overall_score": None, "numeric_coherence_rows": 0,
        "human_source_approval_bound": True, "trusted_source": True,
    }
    s3.write_s3_report(report)
    path = apps_root / "web" / "playwright-report" / s3._OUTPUT_FILE_NAME
    assert path.read_text() == json.dumps(report, sort_keys=True, indent=2) + "\n"
    assert path.is_file()
    assert not path.is_symlink()
    assert not list(path.parent.glob(".s3-evidence-*.tmp"))
    # Genuine re-run replaces only the one authorized regular report.
    report["result"] = "PASS"
    s3.write_s3_report(report)
    assert json.loads(path.read_text()) == report


def test_reject_symlinked_web_root(apps_root: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (apps_root / "web").rmdir()
    (apps_root / "web").symlink_to(outside, target_is_directory=True)
    with pytest.raises(OSError):
        s3.write_s3_report({"score": None})
    assert not list(outside.iterdir())


def test_reject_symlinked_report_directory(apps_root: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (apps_root / "web" / "playwright-report").symlink_to(outside, target_is_directory=True)
    with pytest.raises(OSError):
        s3.write_s3_report({"score": None})
    assert not list(outside.iterdir())


def test_reject_symlinked_report_file(apps_root: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside.json"
    outside.write_text('"untouched"')
    outdir = apps_root / "web" / "playwright-report"
    outdir.mkdir()
    (outdir / s3._OUTPUT_FILE_NAME).symlink_to(outside)
    with pytest.raises(ValueError, match="regular file"):
        s3.write_s3_report({"score": None})
    assert outside.read_text() == '"untouched"'


def test_cannot_retarget_report_via_process_cwd(apps_root: Path, tmp_path: Path, monkeypatch) -> None:
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.chdir(other)
    s3.write_s3_report({"overall_score": None})
    assert not list(other.iterdir())
    assert (apps_root / "web" / "playwright-report" / s3._OUTPUT_FILE_NAME).exists()


class _Result:
    def __init__(self, value):
        self.value = value
    def one_or_none(self): return self.value
    def all(self): return self.value
    def scalar_one(self): return self.value


class _FakeConnection:
    def __init__(self, tenant, project, document, revision):
        self.tenant = tenant
        self.project = project
        self.document = document
        self.revision = revision
        self.calls = []
        self.fail_score = False
        self.fail_binding = False
        self.missing_document = False
    async def __aenter__(self): return self
    async def __aexit__(self, *args): return False
    async def execute(self, stmt, params=None):
        sql = str(stmt)
        self.calls.append((sql, params))
        if "SET TRANSACTION READ ONLY" in sql:
            return _Result(None)
        if "FROM documents d" in sql:
            if self.missing_document:
                return _Result(None)
            return _Result(SimpleNamespace(
                tenant_id=self.tenant, project_id=self.project,
                type="technical_spec", status="analyzed", parsing_error=None,
                metadata={"technical_requirement_count":2},
            ))
        if "FROM clauses c" in sql:
            return _Result([SimpleNamespace(
                clause_code=code,
                full_text=f"Section {code} requirement",
                revision_id=self.revision,
                entities={
                    "technical_requirement": {"source_section":code,"verification_status":"unverified"},
                    "evidence_location":{"revision_id":str(self.revision)},
                },
                extraction_confidence=None, manually_verified=False,
            ) for code in ("4.1.2","4.2")])
        if "FROM document_artifacts" in sql:
            return _Result([SimpleNamespace(
                trust_state="trusted", lifecycle_status="active",
                artifact_id="a1", artifact_hash="h1",
            )])
        if "FROM review_items" in sql:
            return _Result([SimpleNamespace(
                status="APPROVED", approved_by="test-human",
                approved_at="2026-10-30T00:00:00Z",
                bound_id="a1", bound_hash="h2" if self.fail_binding else "h1",
            )])
        if "FROM coherence_results" in sql:
            return _Result(1 if self.fail_score else 0)
        raise AssertionError(sql)


class _FakeEngine:
    def __init__(self, conn): self.conn = conn; self.disposed = False
    def connect(self): return self.conn
    async def dispose(self): self.disposed = True


def _fake_env(monkeypatch):
    ids = [uuid4() for _ in range(4)]
    conn = _FakeConnection(*ids[:3], ids[3])
    engine = _FakeEngine(conn)
    monkeypatch.setattr(s3, "local_test_dsn", lambda value: "test-only-url")
    monkeypatch.setattr(s3, "create_async_engine", lambda _: engine)
    return conn, engine, ids


def test_successful_verifier_preserves_exact_report_schema(monkeypatch):
    conn, engine, (tenant, project, document, revision) = _fake_env(monkeypatch)
    report = asyncio.run(s3.verify("test", project, document, revision))
    assert report == {
        "gate": "S3-TECHNICAL-SOURCE-HEALTH", "result": "PASS",
        "project_id": str(project), "technical_document_id": str(document),
        "technical_revision_id": str(revision),
        "technical_requirement_sections": ["4.1.2", "4.2"],
        "trusted_source": True, "human_source_approval_bound": True,
        "analysis_status": "analyzed", "technical_assessment": "UNVERIFIED",
        "technical_score": None, "overall_score": None, "numeric_coherence_rows": 0,
    }
    assert engine.disposed
    assert conn.calls[0][0] == "SET TRANSACTION READ ONLY"


def test_verifier_rejects_missing_document_before_attribute_access(monkeypatch):
    conn, engine, (_, project, document, revision) = _fake_env(monkeypatch)
    conn.missing_document = True
    verification = s3.verify("test", project, document, revision)
    with pytest.raises(ValueError, match="technical document/project identity mismatch"):
        asyncio.run(verification)
    assert engine.disposed


@pytest.mark.parametrize("failure,expected", [
    ("fail_score", "fabricated numeric Health"),
    ("fail_binding", "matching human approval"),
])
def test_verifier_fail_closed_on_missing_authority_or_numeric_score(monkeypatch, failure, expected):
    conn, engine, (_, project, document, revision) = _fake_env(monkeypatch)
    setattr(conn, failure, True)
    verification = s3.verify("test", project, document, revision)
    with pytest.raises(ValueError, match=expected):
        asyncio.run(verification)
    assert engine.disposed

@pytest.mark.parametrize("bad", [
    "/tmp/s3-report.json",
    "../../../../../tmp/s3-report.json",
])
def test_actual_cli_rejects_unsafe_output_before_any_input_read(bad, tmp_path):
    import subprocess
    # Input files intentionally do not exist: fail-closed --output must be
    # validated before reading fixture paths or opening a DB connection.
    command = Path(s3.__file__)
    proc = subprocess.run([
        sys.executable, str(command),
        "--playwright-json", str(tmp_path / "nonexistent-report.json"),
        "--manifest", str(tmp_path / "nonexistent-manifest.json"),
        "--fixture-dir", str(tmp_path),
        "--output", bad,
    ], capture_output=True, text=True, timeout=20, check=False)
    assert proc.returncode != 0
    assert "fixed to the authorized Playwright evidence file" in proc.stderr
    assert not (tmp_path / "s3-report.json").exists()
