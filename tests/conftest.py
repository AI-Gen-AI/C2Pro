
import os
import time
from pathlib import Path
import sys
import asyncio
from types import SimpleNamespace


def _conftest_checkpoint(label: str) -> None:
    stamp = time.perf_counter()
    print(f"[conftest] {label} @ {stamp:.3f}", flush=True)
    try:
        with open("tests/integration/stakeholder_flow_debug.log", "a", encoding="utf-8") as log_file:
            log_file.write(f"{stamp:.3f} conftest:{label}\n")
    except OSError:
        pass

import pytest
from httpx import AsyncClient
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.compiler import compiles

# Legacy standalone root-level TDD spike files are not part of the maintained
# AGENT test inventory. They use placeholder imports/classes and should not
# block suite execution.
collect_ignore = [
    "legacy",
    "test_i2_ocr_and_table_parsing.py",
    "test_i3_clause_extraction_and_normalization.py",
    "test_i4_hybrid_rag_retrieval.py",
    "test_i5_graph_schema_and_integrity.py",
    "test_i6_coherence_rule_engine.py",
    "test_i7_risk_scoring_aggregation.py",
    "test_i8_wbs_bom_generation.py",
    "test_i9_procurement_planning.py",
    "test_i10_raci_inference.py",
    "test_i11_hitl_enforcement.py",
    "test_i12_observability_and_evaluation.py",
    "test_i13_decision_intelligence_flow.py",
    "test_i14_safety_hardening.py",
    "test_canonical_ingestion.py",
]


if "celery" not in sys.modules:
    class _DummyConf(dict):
        def __getattr__(self, name):
            return self.get(name)

        def __setattr__(self, name, value):
            self[name] = value

    class _DummyCelery:
        def __init__(self, *args, **kwargs) -> None:
            self.conf = _DummyConf()

        def task(self, *args, **kwargs):
            def decorator(fn):
                fn.delay = lambda *a, **k: SimpleNamespace(id="test-task")
                return fn
            return decorator

        def start(self):
            return None

    sys.modules["celery"] = SimpleNamespace(Celery=_DummyCelery)


@compiles(PGUUID, "sqlite")
def _compile_pg_uuid_sqlite(_type, _compiler, **_kwargs):
    return "CHAR(36)"


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kwargs):
    return "JSON"

# Minimal env defaults so importing the app does not fail.
_conftest_checkpoint("env_setup:start")
repo_root = Path(__file__).resolve().parents[1]
api_root = repo_root / "apps" / "api"
if str(api_root) not in sys.path:
    sys.path.insert(0, str(api_root))
if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault("SUPABASE_ANON_KEY", "test")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test")
os.environ.setdefault("JWT_SECRET_KEY", "testsecretkeytestsecretkeytestsecretkey")
os.environ.setdefault("REDIS_URL", "")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test")
os.environ.setdefault("C2PRO_AI_MOCK", "1")
os.environ.setdefault("C2PRO_TEST_LIGHT", "1")
_conftest_checkpoint("env_setup:done")

_conftest_checkpoint("import_app:start")
from src.main import app
_conftest_checkpoint("import_app:done")

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

@pytest.fixture(scope="session")
async def async_client() -> AsyncClient:
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

def pytest_configure(config):
    _conftest_checkpoint("pytest_configure:start")
    config.addinivalue_line("markers", "e2e: mark as end-to-end test.")
    config.addinivalue_line("markers", "tdd: mark tests that enforce TDD workflow")
    from src.config import settings
    settings.celery_task_always_eager = True
    _conftest_checkpoint("pytest_configure:done")


def pytest_sessionstart(session):
    _conftest_checkpoint("pytest_sessionstart")


def pytest_runtest_setup(item):
    _conftest_checkpoint(f"pytest_runtest_setup:{item.name}")
